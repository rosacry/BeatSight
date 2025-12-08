"""Map Accuracy Verification Service.

This service implements the multi-verifier consensus system for beatmap accuracy.
It handles:
1. Awarding karma bonus to users with both email and phone verified
2. Recording accuracy votes from verified users
3. Computing consensus based on vote counts
4. Rewarding verifiers who contribute to consensus

Design Philosophy:
- Quality through quantity: Multiple independent verifiers provide better accuracy
- Incentivize participation: Karma rewards for voting encourage community engagement
- Fair consensus: No single verifier can unilaterally approve/reject a beatmap
- Transparency: All votes are recorded and auditable
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.karma import KarmaReason
from app.models.map_accuracy import (
    AccuracyVoteType,
    MapAccuracyConsensus,
    MapAccuracyStatus,
    MapAccuracyVote,
    UserVerificationBonus,
    REQUIRED_VERIFIERS_FOR_ACCURACY,
    MIN_APPROVAL_RATIO,
    VERIFIED_USER_KARMA_BONUS,
)
from app.models.map_version import MapVersion
from app.models.user import User
from app.services.karma import KarmaService


class MapAccuracyError(Exception):
    """Base exception for map accuracy verification errors."""
    pass


class NotEligibleError(MapAccuracyError):
    """User is not eligible to vote on map accuracy."""
    pass


class AlreadyVotedError(MapAccuracyError):
    """User has already voted on this map version."""
    pass


class MapVersionNotFoundError(MapAccuracyError):
    """Map version does not exist."""
    pass


class MapAccuracyService:
    """Service for managing map accuracy verification and consensus."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._karma_service: Optional[KarmaService] = None

    @property
    def karma_service(self) -> KarmaService:
        """Lazy-load karma service."""
        if self._karma_service is None:
            self._karma_service = KarmaService(self.session)
        return self._karma_service

    # =========================================================================
    # Verified User Karma Bonus
    # =========================================================================

    async def check_and_award_verification_bonus(self, user_id: uuid.UUID) -> bool:
        """
        Check if user qualifies for verification bonus and award it.
        
        A user qualifies when they have BOTH:
        - Verified email address
        - Verified phone number
        
        The bonus is a one-time award of 200 karma points, designed to bring
        users past the 100 karma threshold needed for the "fixer" role.
        
        Returns:
            True if bonus was awarded, False if already awarded or not eligible.
        """
        # Get user info
        result = await self.session.execute(
            select(User.email_verified, User.phone_verified).where(User.id == user_id)
        )
        row = result.one_or_none()
        
        if row is None:
            return False
        
        email_verified, phone_verified = row
        
        # Must have both verified
        if not (email_verified and phone_verified):
            return False
        
        # Check if already awarded
        bonus_result = await self.session.execute(
            select(UserVerificationBonus).where(
                UserVerificationBonus.user_id == user_id
            )
        )
        existing_bonus = bonus_result.scalar_one_or_none()
        
        now = datetime.now(timezone.utc)
        
        if existing_bonus:
            if existing_bonus.bonus_awarded:
                return False  # Already awarded
            
            # Update existing record and award bonus
            existing_bonus.email_verified_at = now
            existing_bonus.phone_verified_at = now
            existing_bonus.bonus_awarded = True
            existing_bonus.awarded_at = now
        else:
            # Create new bonus record
            bonus = UserVerificationBonus(
                user_id=user_id,
                email_verified_at=now,
                phone_verified_at=now,
                bonus_awarded=True,
                bonus_amount=VERIFIED_USER_KARMA_BONUS,
                awarded_at=now,
            )
            self.session.add(bonus)
        
        # Award the karma
        await self.karma_service.award_karma(
            user_id=user_id,
            reason=KarmaReason.VERIFIED_USER_BONUS,
            delta=VERIFIED_USER_KARMA_BONUS,
            related_entity_type="verification_bonus",
        )
        
        await self.session.commit()
        return True

    async def is_eligible_to_vote(self, user_id: uuid.UUID) -> tuple[bool, str]:
        """
        Check if a user is eligible to vote on map accuracy.
        
        Requirements:
        1. Both email and phone must be verified
        2. Must have karma >= 100 (fixer threshold)
        
        Returns:
            Tuple of (is_eligible, reason_if_not_eligible)
        """
        result = await self.session.execute(
            select(
                User.email_verified,
                User.phone_verified,
                User.karma_score,
            ).where(User.id == user_id)
        )
        row = result.one_or_none()
        
        if row is None:
            return False, "User not found"
        
        email_verified, phone_verified, karma_score = row
        
        if not email_verified:
            return False, "Email must be verified to vote on map accuracy"
        
        if not phone_verified:
            return False, "Phone must be verified to vote on map accuracy"
        
        # Minimum karma threshold (same as fixer role)
        if karma_score < 100:
            return False, f"Minimum 100 karma required. Current: {karma_score}"
        
        return True, ""

    # =========================================================================
    # Accuracy Voting
    # =========================================================================

    async def cast_accuracy_vote(
        self,
        map_version_id: uuid.UUID,
        verifier_id: uuid.UUID,
        vote: AccuracyVoteType,
        confidence_level: int = 3,
        notes: Optional[str] = None,
        timestamp_markers: Optional[str] = None,
    ) -> MapAccuracyVote:
        """
        Cast a vote on a map version's accuracy.
        
        Args:
            map_version_id: The map version being evaluated
            verifier_id: The user casting the vote
            vote: The accuracy assessment
            confidence_level: 1-5 scale (1=uncertain, 5=very confident)
            notes: Optional explanation for the vote
            timestamp_markers: Optional JSON of timestamps where issues were found
            
        Returns:
            The created vote record
            
        Raises:
            NotEligibleError: If user doesn't meet voting requirements
            AlreadyVotedError: If user already voted on this map version
            MapVersionNotFoundError: If map version doesn't exist
        """
        # Validate confidence level
        confidence_level = max(1, min(5, confidence_level))
        
        # Check map version exists
        mv_result = await self.session.execute(
            select(MapVersion.id).where(MapVersion.id == map_version_id)
        )
        if mv_result.scalar_one_or_none() is None:
            raise MapVersionNotFoundError(f"Map version {map_version_id} not found")
        
        # Check eligibility
        is_eligible, reason = await self.is_eligible_to_vote(verifier_id)
        if not is_eligible:
            raise NotEligibleError(reason)
        
        # Check if already voted
        existing_vote = await self.session.execute(
            select(MapAccuracyVote).where(
                and_(
                    MapAccuracyVote.map_version_id == map_version_id,
                    MapAccuracyVote.verifier_id == verifier_id,
                )
            )
        )
        if existing_vote.scalar_one_or_none():
            raise AlreadyVotedError(
                "You have already voted on this map version. "
                "Use update_accuracy_vote to change your vote."
            )
        
        # Create the vote
        accuracy_vote = MapAccuracyVote(
            map_version_id=map_version_id,
            verifier_id=verifier_id,
            vote=vote,
            confidence_level=confidence_level,
            notes=notes,
            timestamp_markers=timestamp_markers,
        )
        self.session.add(accuracy_vote)
        
        # Award karma for participating
        await self.karma_service.award_karma(
            user_id=verifier_id,
            reason=KarmaReason.ACCURACY_VOTE_CAST,
            related_entity_type="map_version",
            related_entity_id=map_version_id,
        )
        
        await self.session.commit()
        await self.session.refresh(accuracy_vote)
        
        # Update consensus after new vote
        await self._update_consensus(map_version_id)
        
        return accuracy_vote

    async def update_accuracy_vote(
        self,
        map_version_id: uuid.UUID,
        verifier_id: uuid.UUID,
        vote: AccuracyVoteType,
        confidence_level: int = 3,
        notes: Optional[str] = None,
        timestamp_markers: Optional[str] = None,
    ) -> MapAccuracyVote:
        """
        Update an existing accuracy vote.
        
        Users can change their vote until consensus is reached.
        """
        # Get existing vote
        result = await self.session.execute(
            select(MapAccuracyVote).where(
                and_(
                    MapAccuracyVote.map_version_id == map_version_id,
                    MapAccuracyVote.verifier_id == verifier_id,
                )
            )
        )
        existing_vote = result.scalar_one_or_none()
        
        if not existing_vote:
            # If no existing vote, create new one
            return await self.cast_accuracy_vote(
                map_version_id=map_version_id,
                verifier_id=verifier_id,
                vote=vote,
                confidence_level=confidence_level,
                notes=notes,
                timestamp_markers=timestamp_markers,
            )
        
        # Check if consensus already reached
        consensus = await self.get_consensus(map_version_id)
        if consensus and consensus.status != MapAccuracyStatus.PENDING:
            raise MapAccuracyError(
                f"Cannot change vote after consensus reached (status: {consensus.status.value})"
            )
        
        # Update the vote
        existing_vote.vote = vote
        existing_vote.confidence_level = max(1, min(5, confidence_level))
        existing_vote.notes = notes
        existing_vote.timestamp_markers = timestamp_markers
        existing_vote.voted_at = datetime.now(timezone.utc)
        
        await self.session.commit()
        await self.session.refresh(existing_vote)
        
        # Update consensus
        await self._update_consensus(map_version_id)
        
        return existing_vote

    async def get_user_vote(
        self,
        map_version_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Optional[MapAccuracyVote]:
        """Get a user's vote on a map version, if any."""
        result = await self.session.execute(
            select(MapAccuracyVote).where(
                and_(
                    MapAccuracyVote.map_version_id == map_version_id,
                    MapAccuracyVote.verifier_id == user_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_map_version_votes(
        self,
        map_version_id: uuid.UUID,
    ) -> list[MapAccuracyVote]:
        """Get all votes for a map version."""
        result = await self.session.execute(
            select(MapAccuracyVote)
            .where(MapAccuracyVote.map_version_id == map_version_id)
            .order_by(MapAccuracyVote.voted_at.desc())
        )
        return list(result.scalars().all())

    # =========================================================================
    # Consensus Management
    # =========================================================================

    async def get_consensus(
        self,
        map_version_id: uuid.UUID,
    ) -> Optional[MapAccuracyConsensus]:
        """Get the consensus status for a map version."""
        result = await self.session.execute(
            select(MapAccuracyConsensus).where(
                MapAccuracyConsensus.map_version_id == map_version_id
            )
        )
        return result.scalar_one_or_none()

    async def _update_consensus(self, map_version_id: uuid.UUID) -> MapAccuracyConsensus:
        """
        Update consensus status based on current votes.
        
        Consensus rules:
        1. Need at least REQUIRED_VERIFIERS_FOR_ACCURACY (3) non-abstain votes
        2. If >= MIN_APPROVAL_RATIO (67%) vote "accurate" → VERIFIED
        3. If >= MIN_APPROVAL_RATIO vote "inaccurate" → REJECTED
        4. If >= MIN_APPROVAL_RATIO vote "needs_work" → NEEDS_REVISION
        5. Otherwise → DISPUTED (no clear consensus)
        """
        # Get or create consensus record
        consensus = await self.get_consensus(map_version_id)
        if consensus is None:
            consensus = MapAccuracyConsensus(
                map_version_id=map_version_id,
                status=MapAccuracyStatus.PENDING,
            )
            self.session.add(consensus)
        
        # Aggregate vote counts
        vote_counts = await self.session.execute(
            select(
                MapAccuracyVote.vote,
                func.count().label("count"),
            )
            .where(MapAccuracyVote.map_version_id == map_version_id)
            .group_by(MapAccuracyVote.vote)
        )
        
        counts = {row.vote: row.count for row in vote_counts.all()}
        
        accurate = counts.get(AccuracyVoteType.ACCURATE, 0)
        inaccurate = counts.get(AccuracyVoteType.INACCURATE, 0)
        needs_work = counts.get(AccuracyVoteType.NEEDS_WORK, 0)
        abstain = counts.get(AccuracyVoteType.ABSTAIN, 0)
        
        total = accurate + inaccurate + needs_work + abstain
        non_abstain = accurate + inaccurate + needs_work
        
        # Update vote counts
        consensus.total_votes = total
        consensus.accurate_votes = accurate
        consensus.inaccurate_votes = inaccurate
        consensus.needs_work_votes = needs_work
        consensus.abstain_votes = abstain
        
        # Calculate average confidence
        avg_conf_result = await self.session.execute(
            select(func.avg(MapAccuracyVote.confidence_level)).where(
                MapAccuracyVote.map_version_id == map_version_id
            )
        )
        consensus.average_confidence = avg_conf_result.scalar()
        
        # Determine consensus status
        old_status = consensus.status
        
        if non_abstain < REQUIRED_VERIFIERS_FOR_ACCURACY:
            # Not enough votes yet
            consensus.status = MapAccuracyStatus.PENDING
        else:
            # Calculate ratios
            accurate_ratio = accurate / non_abstain
            inaccurate_ratio = inaccurate / non_abstain
            needs_work_ratio = needs_work / non_abstain
            
            if accurate_ratio >= MIN_APPROVAL_RATIO:
                consensus.status = MapAccuracyStatus.VERIFIED
            elif inaccurate_ratio >= MIN_APPROVAL_RATIO:
                consensus.status = MapAccuracyStatus.REJECTED
            elif needs_work_ratio >= MIN_APPROVAL_RATIO:
                consensus.status = MapAccuracyStatus.NEEDS_REVISION
            else:
                consensus.status = MapAccuracyStatus.DISPUTED
        
        # If consensus just reached, record timestamp and award bonuses
        if (
            old_status == MapAccuracyStatus.PENDING
            and consensus.status != MapAccuracyStatus.PENDING
        ):
            consensus.consensus_reached_at = datetime.now(timezone.utc)
            
            # Award bonus karma to verifiers who voted with consensus
            await self._award_consensus_bonuses(map_version_id, consensus.status)
        
        consensus.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(consensus)
        
        return consensus

    async def _award_consensus_bonuses(
        self,
        map_version_id: uuid.UUID,
        final_status: MapAccuracyStatus,
    ) -> None:
        """Award bonus karma to verifiers whose votes aligned with consensus."""
        # Determine which vote type matches consensus
        matching_vote: Optional[AccuracyVoteType] = None
        if final_status == MapAccuracyStatus.VERIFIED:
            matching_vote = AccuracyVoteType.ACCURATE
        elif final_status == MapAccuracyStatus.REJECTED:
            matching_vote = AccuracyVoteType.INACCURATE
        elif final_status == MapAccuracyStatus.NEEDS_REVISION:
            matching_vote = AccuracyVoteType.NEEDS_WORK
        
        if matching_vote is None:
            return  # DISPUTED status - no clear consensus, no bonuses
        
        # Find verifiers who voted with consensus
        result = await self.session.execute(
            select(MapAccuracyVote.verifier_id).where(
                and_(
                    MapAccuracyVote.map_version_id == map_version_id,
                    MapAccuracyVote.vote == matching_vote,
                )
            )
        )
        
        verifier_ids = [row[0] for row in result.all()]
        
        # Award consensus contributor bonus to each
        for verifier_id in verifier_ids:
            await self.karma_service.award_karma(
                user_id=verifier_id,
                reason=KarmaReason.ACCURACY_CONSENSUS_CONTRIBUTOR,
                related_entity_type="map_version",
                related_entity_id=map_version_id,
            )

    # =========================================================================
    # Query Methods
    # =========================================================================

    async def get_maps_needing_verification(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[tuple[uuid.UUID, int]]:
        """
        Get map versions that need more votes for consensus.
        
        Returns:
            List of tuples: (map_version_id, current_vote_count)
        """
        result = await self.session.execute(
            select(
                MapAccuracyConsensus.map_version_id,
                MapAccuracyConsensus.total_votes,
            )
            .where(MapAccuracyConsensus.status == MapAccuracyStatus.PENDING)
            .order_by(MapAccuracyConsensus.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.all())

    async def get_verified_maps_count(self) -> int:
        """Get count of maps that have reached verified consensus."""
        result = await self.session.execute(
            select(func.count()).where(
                MapAccuracyConsensus.status == MapAccuracyStatus.VERIFIED
            )
        )
        return result.scalar() or 0

    async def get_user_verification_stats(
        self,
        user_id: uuid.UUID,
    ) -> dict:
        """
        Get verification statistics for a user.
        
        Returns dict with:
        - total_votes: Total accuracy votes cast
        - consensus_matches: Votes that matched final consensus
        - by_vote_type: Breakdown by vote type
        """
        # Total votes by type
        votes_result = await self.session.execute(
            select(
                MapAccuracyVote.vote,
                func.count().label("count"),
            )
            .where(MapAccuracyVote.verifier_id == user_id)
            .group_by(MapAccuracyVote.vote)
        )
        
        by_type = {row.vote.value: row.count for row in votes_result.all()}
        total_votes = sum(by_type.values())
        
        # Count consensus matches
        # This is complex - need to join votes with consensus to check alignment
        consensus_matches = await self.session.execute(
            select(func.count())
            .select_from(MapAccuracyVote)
            .join(
                MapAccuracyConsensus,
                MapAccuracyVote.map_version_id == MapAccuracyConsensus.map_version_id,
            )
            .where(
                and_(
                    MapAccuracyVote.verifier_id == user_id,
                    # Match accurate votes with verified status
                    (
                        (
                            MapAccuracyVote.vote == AccuracyVoteType.ACCURATE
                        ) & (
                            MapAccuracyConsensus.status == MapAccuracyStatus.VERIFIED
                        )
                    ) | (
                        (
                            MapAccuracyVote.vote == AccuracyVoteType.INACCURATE
                        ) & (
                            MapAccuracyConsensus.status == MapAccuracyStatus.REJECTED
                        )
                    ) | (
                        (
                            MapAccuracyVote.vote == AccuracyVoteType.NEEDS_WORK
                        ) & (
                            MapAccuracyConsensus.status == MapAccuracyStatus.NEEDS_REVISION
                        )
                    )
                )
            )
        )
        
        return {
            "total_votes": total_votes,
            "consensus_matches": consensus_matches.scalar() or 0,
            "by_vote_type": by_type,
        }
