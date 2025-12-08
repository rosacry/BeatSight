"""Verification bonus service.

Implements a tiered verification bonus system:
- Email verification only: 50 karma
- Phone verification only: 50 karma  
- Both email AND phone verified: Additional 100 karma (total: 200 karma)

This tiered approach encourages users to complete full verification
while still rewarding partial verification.

The system tracks which bonuses have been awarded to prevent duplicate awards.
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.karma import KarmaReason
from app.models.user import User
from app.services.karma import KarmaService, KARMA_REWARDS


class VerificationBonusTracker:
    """
    Tracks verification bonus awards.
    
    Stored in a simple model to track which bonuses each user has received.
    """
    pass


class VerificationBonusService:
    """
    Service for managing verification bonuses.
    
    Karma Structure:
    - Email verified: +50 karma (one-time)
    - Phone verified: +50 karma (one-time)
    - Both verified: +100 karma bonus (one-time, on top of the individual bonuses)
    
    Total possible: 200 karma for full verification
    """
    
    # Bonus amounts (these match KARMA_REWARDS for consistency)
    EMAIL_BONUS = KARMA_REWARDS.get(KarmaReason.EMAIL_VERIFIED_BONUS, 50)
    PHONE_BONUS = KARMA_REWARDS.get(KarmaReason.PHONE_VERIFIED_BONUS, 50)
    FULL_VERIFICATION_BONUS = KARMA_REWARDS.get(KarmaReason.FULL_VERIFICATION_BONUS, 100)
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self._karma_service: Optional[KarmaService] = None
    
    @property
    def karma_service(self) -> KarmaService:
        """Lazy-load karma service."""
        if self._karma_service is None:
            self._karma_service = KarmaService(self.session)
        return self._karma_service
    
    async def check_and_award_email_bonus(self, user_id: uuid.UUID) -> dict:
        """
        Check if user should receive email verification bonus and award it.
        
        Returns:
            dict with:
                - awarded: bool - whether bonus was awarded
                - amount: int - amount awarded (0 if already awarded)
                - reason: str - explanation
        """
        # Get user
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user is None:
            return {"awarded": False, "amount": 0, "reason": "User not found"}
        
        if not user.email_verified:
            return {"awarded": False, "amount": 0, "reason": "Email not verified"}
        
        # Check if already awarded by looking at karma ledger
        from app.models.karma import KarmaLedger
        
        existing = await self.session.execute(
            select(KarmaLedger).where(
                KarmaLedger.user_id == user_id,
                KarmaLedger.reason_code == KarmaReason.EMAIL_VERIFIED_BONUS,
            )
        )
        if existing.scalar_one_or_none():
            return {"awarded": False, "amount": 0, "reason": "Email bonus already awarded"}
        
        # Award the bonus
        await self.karma_service.award_karma(
            user_id=user_id,
            reason=KarmaReason.EMAIL_VERIFIED_BONUS,
            delta=self.EMAIL_BONUS,
            related_entity_type="email_verification",
        )
        
        # Check if they now qualify for the full verification bonus
        await self._check_full_verification_bonus(user_id)
        
        return {
            "awarded": True,
            "amount": self.EMAIL_BONUS,
            "reason": "Email verification bonus awarded",
        }
    
    async def check_and_award_phone_bonus(self, user_id: uuid.UUID) -> dict:
        """
        Check if user should receive phone verification bonus and award it.
        
        Returns:
            dict with:
                - awarded: bool - whether bonus was awarded
                - amount: int - amount awarded (0 if already awarded)
                - reason: str - explanation
        """
        # Get user
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user is None:
            return {"awarded": False, "amount": 0, "reason": "User not found"}
        
        if not user.phone_verified:
            return {"awarded": False, "amount": 0, "reason": "Phone not verified"}
        
        # Check if already awarded
        from app.models.karma import KarmaLedger
        
        existing = await self.session.execute(
            select(KarmaLedger).where(
                KarmaLedger.user_id == user_id,
                KarmaLedger.reason_code == KarmaReason.PHONE_VERIFIED_BONUS,
            )
        )
        if existing.scalar_one_or_none():
            return {"awarded": False, "amount": 0, "reason": "Phone bonus already awarded"}
        
        # Award the bonus
        await self.karma_service.award_karma(
            user_id=user_id,
            reason=KarmaReason.PHONE_VERIFIED_BONUS,
            delta=self.PHONE_BONUS,
            related_entity_type="phone_verification",
        )
        
        # Check if they now qualify for the full verification bonus
        await self._check_full_verification_bonus(user_id)
        
        return {
            "awarded": True,
            "amount": self.PHONE_BONUS,
            "reason": "Phone verification bonus awarded",
        }
    
    async def _check_full_verification_bonus(self, user_id: uuid.UUID) -> dict:
        """
        Check if user qualifies for the full verification bonus.
        
        Requires BOTH email AND phone to be verified.
        """
        # Get user verification status
        result = await self.session.execute(
            select(User.email_verified, User.phone_verified).where(User.id == user_id)
        )
        row = result.one_or_none()
        
        if row is None:
            return {"awarded": False, "amount": 0, "reason": "User not found"}
        
        email_verified, phone_verified = row
        
        if not (email_verified and phone_verified):
            return {"awarded": False, "amount": 0, "reason": "Not fully verified"}
        
        # Check if already awarded
        from app.models.karma import KarmaLedger
        
        existing = await self.session.execute(
            select(KarmaLedger).where(
                KarmaLedger.user_id == user_id,
                KarmaLedger.reason_code == KarmaReason.FULL_VERIFICATION_BONUS,
            )
        )
        if existing.scalar_one_or_none():
            return {"awarded": False, "amount": 0, "reason": "Full verification bonus already awarded"}
        
        # Award the full verification bonus
        await self.karma_service.award_karma(
            user_id=user_id,
            reason=KarmaReason.FULL_VERIFICATION_BONUS,
            delta=self.FULL_VERIFICATION_BONUS,
            related_entity_type="full_verification",
        )
        
        return {
            "awarded": True,
            "amount": self.FULL_VERIFICATION_BONUS,
            "reason": "Full verification bonus awarded",
        }
    
    async def get_verification_status(self, user_id: uuid.UUID) -> dict:
        """
        Get a user's verification status and bonus history.
        
        Returns:
            dict with:
                - email_verified: bool
                - phone_verified: bool
                - fully_verified: bool
                - bonuses: dict with awarded amounts for each type
                - total_bonus: int - total karma from verification
                - potential_bonus: int - remaining karma available
        """
        # Get user
        result = await self.session.execute(
            select(User.email_verified, User.phone_verified).where(User.id == user_id)
        )
        row = result.one_or_none()
        
        if row is None:
            return {"error": "User not found"}
        
        email_verified, phone_verified = row
        
        # Check what bonuses have been awarded
        from app.models.karma import KarmaLedger
        
        ledger_result = await self.session.execute(
            select(KarmaLedger.reason_code, KarmaLedger.delta).where(
                KarmaLedger.user_id == user_id,
                KarmaLedger.reason_code.in_([
                    KarmaReason.EMAIL_VERIFIED_BONUS,
                    KarmaReason.PHONE_VERIFIED_BONUS,
                    KarmaReason.FULL_VERIFICATION_BONUS,
                    KarmaReason.VERIFIED_USER_BONUS,  # Legacy
                ])
            )
        )
        awarded_bonuses = {str(row.reason_code.value): row.delta for row in ledger_result.all()}
        
        total_awarded = sum(awarded_bonuses.values())
        
        # Calculate potential remaining bonus
        potential = 0
        if email_verified and "email_verified_bonus" not in awarded_bonuses:
            potential += self.EMAIL_BONUS
        if phone_verified and "phone_verified_bonus" not in awarded_bonuses:
            potential += self.PHONE_BONUS
        if email_verified and phone_verified and "full_verification_bonus" not in awarded_bonuses:
            potential += self.FULL_VERIFICATION_BONUS
        
        return {
            "email_verified": email_verified,
            "phone_verified": phone_verified,
            "fully_verified": email_verified and phone_verified,
            "bonuses": {
                "email": awarded_bonuses.get("email_verified_bonus", 0),
                "phone": awarded_bonuses.get("phone_verified_bonus", 0),
                "full": awarded_bonuses.get("full_verification_bonus", 0),
                "legacy": awarded_bonuses.get("verified_user_bonus", 0),
            },
            "total_bonus": total_awarded,
            "potential_bonus": potential,
            "max_possible_bonus": self.EMAIL_BONUS + self.PHONE_BONUS + self.FULL_VERIFICATION_BONUS,
        }
    
    async def claim_pending_bonuses(self, user_id: uuid.UUID) -> dict:
        """
        Claim all pending verification bonuses for a user.
        
        This is useful for:
        - Users who verified before the tiered system was implemented
        - Ensuring users get all bonuses they're eligible for
        
        Returns:
            dict with total karma awarded and breakdown
        """
        total_awarded = 0
        breakdown = []
        
        # Get user
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user is None:
            return {"error": "User not found", "total_awarded": 0, "breakdown": []}
        
        # Try to award email bonus
        if user.email_verified:
            email_result = await self.check_and_award_email_bonus(user_id)
            if email_result["awarded"]:
                total_awarded += email_result["amount"]
                breakdown.append({
                    "type": "email",
                    "amount": email_result["amount"],
                    "reason": email_result["reason"],
                })
        
        # Try to award phone bonus
        if user.phone_verified:
            phone_result = await self.check_and_award_phone_bonus(user_id)
            if phone_result["awarded"]:
                total_awarded += phone_result["amount"]
                breakdown.append({
                    "type": "phone",
                    "amount": phone_result["amount"],
                    "reason": phone_result["reason"],
                })
        
        # Full verification bonus is checked automatically in the above methods
        
        return {
            "total_awarded": total_awarded,
            "breakdown": breakdown,
            "status": await self.get_verification_status(user_id),
        }
