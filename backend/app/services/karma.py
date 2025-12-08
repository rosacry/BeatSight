"""Karma service for managing user reputation."""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.karma import KarmaLedger, KarmaReason
from app.models.role import Role, UserRole
from app.models.user import User


class KarmaError(Exception):
    """Base exception for karma operations."""

    pass


class InsufficientKarmaError(KarmaError):
    """Raised when user lacks required karma."""

    def __init__(self, required: int, current: int):
        self.required = required
        self.current = current
        super().__init__(f"Insufficient karma: requires {required}, user has {current}")


class RoleCode(str, Enum):
    """Standard role codes in the system."""

    FIXER = "fixer"
    VERIFIER = "verifier"
    CURATOR = "curator"
    ADMIN = "admin"


# Karma thresholds for role eligibility
ROLE_KARMA_THRESHOLDS = {
    RoleCode.FIXER: 100,
    RoleCode.VERIFIER: 500,
    RoleCode.CURATOR: 2000,
    RoleCode.ADMIN: 10000,
}

# Karma awards/penalties for various actions
KARMA_REWARDS = {
    KarmaReason.FIX_ACCEPTED: 25,
    KarmaReason.FIX_REJECTED: -10,
    KarmaReason.VERIFICATION_COMPLETE: 10,
    KarmaReason.VERIFICATION_REJECTED: -15,
    KarmaReason.SUBSCRIPTION_BONUS: 50,
    KarmaReason.MAP_UPVOTED: 5,  # Small reward for receiving upvotes
    KarmaReason.MAP_DOWNVOTED: -3,  # Small penalty for receiving downvotes
    KarmaReason.CONTRIBUTION_APPROVED: 15,  # Reward for approved training contribution
    KarmaReason.CONTRIBUTION_REJECTED: -5,  # Penalty for rejected contribution
    
    # Tiered verification bonuses
    KarmaReason.EMAIL_VERIFIED_BONUS: 50,  # Email only verification
    KarmaReason.PHONE_VERIFIED_BONUS: 50,  # Phone only verification
    KarmaReason.FULL_VERIFICATION_BONUS: 100,  # Extra bonus for both (total: 50+50+100=200)
    KarmaReason.VERIFIED_USER_BONUS: 200,  # Legacy: brings verified users to 200 karma
    
    # Accuracy verification participation rewards
    KarmaReason.ACCURACY_VOTE_CAST: 5,  # Small reward for participating in verification
    KarmaReason.ACCURACY_CONSENSUS_CONTRIBUTOR: 10,  # Extra if vote matches final consensus
    
    # Forum karma rewards/penalties
    KarmaReason.FORUM_POST_UPVOTED: 3,  # Smaller than map upvotes
    KarmaReason.FORUM_POST_DOWNVOTED: -2,  # Smaller penalty
    KarmaReason.FORUM_TOPIC_UPVOTED: 5,  # Topics get slightly more
    KarmaReason.FORUM_TOPIC_DOWNVOTED: -3,
    KarmaReason.FORUM_HELPFUL_ANSWER: 15,  # Significant reward for being helpful
    KarmaReason.FORUM_SPAM_PENALTY: -25,  # Significant penalty for spam
}

# Daily AI generation quotas by karma tier
AI_GENERATION_QUOTAS = {
    0: 3,  # New users: 3 per day
    100: 5,  # Fixer: 5 per day
    500: 10,  # Verifier: 10 per day
    2000: 25,  # Curator: 25 per day
    10000: -1,  # Admin: unlimited (-1)
}


class KarmaService:
    """Service for managing user karma and related features."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_karma(self, user_id: uuid.UUID) -> int:
        """Get a user's current karma score."""
        result = await self.session.execute(
            select(User.karma_score).where(User.id == user_id)
        )
        karma = result.scalar_one_or_none()
        return karma if karma is not None else 0

    async def award_karma(
        self,
        user_id: uuid.UUID,
        reason: KarmaReason,
        delta: Optional[int] = None,
        related_entity_type: Optional[str] = None,
        related_entity_id: Optional[uuid.UUID] = None,
    ) -> int:
        """
        Award or deduct karma from a user.

        Args:
            user_id: The user to adjust karma for.
            reason: The reason code for the adjustment.
            delta: Override the default karma amount (optional).
            related_entity_type: Type of related entity (map, proposal, etc.).
            related_entity_id: ID of the related entity.

        Returns:
            The user's new karma score.
        """
        # Determine karma amount
        if delta is None:
            delta = KARMA_REWARDS.get(reason, 0)

        if delta == 0:
            # No change needed
            return await self.get_user_karma(user_id)

        # Create ledger entry
        ledger_entry = KarmaLedger(
            user_id=user_id,
            delta=delta,
            reason_code=reason,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        )
        self.session.add(ledger_entry)

        # Update user's aggregate karma score
        result = await self.session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if user is None:
            raise KarmaError(f"User {user_id} not found")

        user.karma_score = max(0, user.karma_score + delta)  # Floor at 0
        new_karma = user.karma_score

        await self.session.commit()

        # Check for role eligibility changes
        await self._update_role_eligibility(user_id, new_karma)

        # Check for karma-related achievements
        from app.services.achievements import check_karma_achievements

        await check_karma_achievements(self.session, user_id, new_karma)

        return new_karma

    async def get_karma_history(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[KarmaLedger]:
        """Get a user's karma history, most recent first."""
        result = await self.session.execute(
            select(KarmaLedger)
            .where(KarmaLedger.user_id == user_id)
            .order_by(KarmaLedger.recorded_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_karma_history_count(self, user_id: uuid.UUID) -> int:
        """Get total count of karma history entries for a user."""
        from sqlalchemy import func

        result = await self.session.execute(
            select(func.count(KarmaLedger.id)).where(KarmaLedger.user_id == user_id)
        )
        return result.scalar_one()

    async def get_daily_ai_quota(self, user_id: uuid.UUID) -> int:
        """
        Get the user's daily AI generation quota based on karma.

        Returns:
            Number of AI generations allowed per day (-1 for unlimited).
        """
        karma = await self.get_user_karma(user_id)

        # Find the highest threshold the user meets
        quota = AI_GENERATION_QUOTAS[0]  # Default
        for threshold, allowed in sorted(AI_GENERATION_QUOTAS.items()):
            if karma >= threshold:
                quota = allowed

        return quota

    async def check_karma_requirement(
        self,
        user_id: uuid.UUID,
        required_karma: int,
    ) -> bool:
        """Check if a user meets a karma requirement."""
        karma = await self.get_user_karma(user_id)
        return karma >= required_karma

    async def require_karma(
        self,
        user_id: uuid.UUID,
        required_karma: int,
    ) -> None:
        """
        Require a minimum karma level, raising an exception if not met.

        Raises:
            InsufficientKarmaError: If user doesn't have enough karma.
        """
        karma = await self.get_user_karma(user_id)
        if karma < required_karma:
            raise InsufficientKarmaError(required_karma, karma)

    async def get_eligible_roles(self, user_id: uuid.UUID) -> list[str]:
        """Get list of role codes the user is eligible for based on karma."""
        karma = await self.get_user_karma(user_id)

        # Get user verification status
        result = await self.session.execute(
            select(User.phone_verified).where(User.id == user_id)
        )
        phone_verified = result.scalar_one_or_none() or False

        # Get all roles
        result = await self.session.execute(select(Role))
        roles = result.scalars().all()

        eligible = []
        for role in roles:
            if karma >= role.min_karma:
                if role.requires_phone_verification and not phone_verified:
                    continue
                eligible.append(role.code)

        return eligible

    async def get_user_roles(self, user_id: uuid.UUID) -> list[str]:
        """Get list of role codes currently assigned to the user."""
        result = await self.session.execute(
            select(Role.code)
            .join(UserRole, Role.id == UserRole.role_id)
            .where(UserRole.user_id == user_id)
        )
        return list(result.scalars().all())

    async def has_role(self, user_id: uuid.UUID, role_code: str) -> bool:
        """Check if a user has a specific role."""
        roles = await self.get_user_roles(user_id)
        return role_code in roles

    async def assign_role(self, user_id: uuid.UUID, role_code: str) -> bool:
        """
        Assign a role to a user if they're eligible.

        Returns:
            True if role was assigned, False if already had it or ineligible.
        """
        # Check eligibility
        eligible_roles = await self.get_eligible_roles(user_id)
        if role_code not in eligible_roles:
            return False

        # Check if already has role
        current_roles = await self.get_user_roles(user_id)
        if role_code in current_roles:
            return False

        # Get role ID
        result = await self.session.execute(
            select(Role.id).where(Role.code == role_code)
        )
        role_id = result.scalar_one_or_none()

        if role_id is None:
            return False

        # Assign role
        user_role = UserRole(user_id=user_id, role_id=role_id)
        self.session.add(user_role)
        await self.session.commit()

        return True

    async def remove_role(self, user_id: uuid.UUID, role_code: str) -> bool:
        """
        Remove a role from a user.

        Returns:
            True if role was removed, False if user didn't have it.
        """
        result = await self.session.execute(
            select(UserRole)
            .join(Role, Role.id == UserRole.role_id)
            .where(UserRole.user_id == user_id, Role.code == role_code)
        )
        user_role = result.scalar_one_or_none()

        if user_role is None:
            return False

        await self.session.delete(user_role)
        await self.session.commit()

        return True

    async def _update_role_eligibility(self, user_id: uuid.UUID, karma: int) -> None:
        """
        Update role assignments based on karma changes.

        Automatically assigns roles when thresholds are crossed (upward)
        and removes roles when karma drops below minimum (downward).
        """
        eligible_roles = await self.get_eligible_roles(user_id)
        current_roles = await self.get_user_roles(user_id)

        # Auto-assign newly eligible roles
        for role_code in eligible_roles:
            if role_code not in current_roles:
                await self.assign_role(user_id, role_code)

        # Remove roles user is no longer eligible for
        for role_code in current_roles:
            if role_code not in eligible_roles:
                await self.remove_role(user_id, role_code)

    async def get_karma_leaderboard(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[tuple[uuid.UUID, str, int]]:
        """
        Get the karma leaderboard.

        Returns:
            List of tuples: (user_id, display_name, karma_score)
        """
        result = await self.session.execute(
            select(User.id, User.display_name, User.karma_score)
            .order_by(User.karma_score.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.all())

    async def get_karma_stats(self, user_id: uuid.UUID) -> dict:
        """
        Get detailed karma statistics for a user.

        OPTIMIZED: Fetches all data in minimal queries instead of 9+ separate calls.

        Returns:
            Dictionary with karma breakdown by reason.
        """
        # Query 1: Get user info (karma_score, phone_verified) in one shot
        user_result = await self.session.execute(
            select(User.karma_score, User.phone_verified).where(User.id == user_id)
        )
        user_row = user_result.one_or_none()
        karma = user_row.karma_score if user_row else 0
        phone_verified = user_row.phone_verified if user_row else False

        # Query 2: Get breakdown by reason AND rank in a single round-trip using subquery
        # (Breakdown)
        breakdown_result = await self.session.execute(
            select(
                KarmaLedger.reason_code,
                func.sum(KarmaLedger.delta).label("total"),
                func.count().label("count"),
            )
            .where(KarmaLedger.user_id == user_id)
            .group_by(KarmaLedger.reason_code)
        )
        breakdown = {
            row.reason_code.value: {"total": row.total, "count": row.count}
            for row in breakdown_result.all()
        }

        # Query 3: Get rank
        rank_result = await self.session.execute(
            select(func.count()).select_from(User).where(User.karma_score > karma)
        )
        rank = (rank_result.scalar() or 0) + 1

        # Query 4: Get all roles (for eligibility check)
        roles_result = await self.session.execute(select(Role))
        all_roles = roles_result.scalars().all()

        # Query 5: Get user's current roles
        user_roles_result = await self.session.execute(
            select(Role.code)
            .join(UserRole, Role.id == UserRole.role_id)
            .where(UserRole.user_id == user_id)
        )
        current_roles = list(user_roles_result.scalars().all())

        # Compute eligible roles in-memory (no extra query!)
        eligible = []
        for role in all_roles:
            if karma >= role.min_karma:
                if role.requires_phone_verification and not phone_verified:
                    continue
                eligible.append(role.code)

        # Compute daily AI quota in-memory (no extra query!)
        quota = AI_GENERATION_QUOTAS[0]  # Default
        for threshold, allowed in sorted(AI_GENERATION_QUOTAS.items()):
            if karma >= threshold:
                quota = allowed

        return {
            "current_score": karma,
            "rank": rank,
            "breakdown": breakdown,
            "eligible_roles": eligible,
            "current_roles": current_roles,
            "daily_ai_quota": quota,
        }
