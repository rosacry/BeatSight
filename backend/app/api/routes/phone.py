"""Phone verification API routes.

Handles:
- Sending verification codes via SMS
- Verifying phone numbers
- Rate limiting to prevent abuse
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.phone_verification import PhoneVerificationAttempt, PhoneVerificationCode
from app.models.user import User
from app.services.sms import get_sms_service
from app.services.map_accuracy import MapAccuracyService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/phone", tags=["phone-verification"])

# Rate limits
MAX_SMS_PER_HOUR = 3  # Max SMS sends per user per hour
MAX_VERIFICATION_ATTEMPTS = 5  # Max verification attempts per code


class SendCodeRequest(BaseModel):
    """Request to send a verification code."""
    
    phone_number: str = Field(
        ...,
        description="Phone number in E.164 format (e.g., +14155551234)",
        min_length=10,
        max_length=20,
    )

    @field_validator("phone_number")
    @classmethod
    def validate_phone_format(cls, v: str) -> str:
        """Validate phone number format."""
        sms_service = get_sms_service()
        is_valid, error = sms_service.validate_phone_number(v)
        if not is_valid:
            raise ValueError(error)
        return sms_service.normalize_phone_number(v)


class VerifyCodeRequest(BaseModel):
    """Request to verify a code."""
    
    code: str = Field(
        ...,
        description="6-digit verification code",
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
    )


class PhoneStatusResponse(BaseModel):
    """Response with phone verification status."""
    
    phone_number: str | None
    phone_verified: bool
    can_send_code: bool
    next_send_allowed_at: datetime | None = None
    message: str | None = None


class SendCodeResponse(BaseModel):
    """Response after sending a verification code."""
    
    success: bool
    message: str
    expires_at: datetime | None = None


class VerifyCodeResponse(BaseModel):
    """Response after verifying a code."""
    
    success: bool
    message: str
    phone_verified: bool
    karma_bonus_awarded: bool = False
    karma_bonus_amount: int = 0


def _hash_code(code: str) -> str:
    """Hash a verification code for secure storage."""
    return hashlib.sha256(code.encode()).hexdigest()


async def _check_rate_limit(
    session: AsyncSession,
    user_id: str,
    phone_number: str,
) -> tuple[bool, datetime | None]:
    """Check if user is rate limited for sending SMS.
    
    Returns:
        Tuple of (is_allowed, next_allowed_at)
    """
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    
    # Count attempts in the last hour
    result = await session.execute(
        select(func.count(PhoneVerificationAttempt.id))
        .where(PhoneVerificationAttempt.user_id == user_id)
        .where(PhoneVerificationAttempt.created_at > one_hour_ago)
    )
    count = result.scalar() or 0
    
    if count >= MAX_SMS_PER_HOUR:
        # Find the oldest attempt to determine when rate limit resets
        oldest = await session.execute(
            select(PhoneVerificationAttempt.created_at)
            .where(PhoneVerificationAttempt.user_id == user_id)
            .where(PhoneVerificationAttempt.created_at > one_hour_ago)
            .order_by(PhoneVerificationAttempt.created_at.asc())
            .limit(1)
        )
        oldest_time = oldest.scalar()
        if oldest_time:
            next_allowed = oldest_time + timedelta(hours=1)
            return False, next_allowed
        return False, None
    
    return True, None


@router.get("/status", response_model=PhoneStatusResponse)
async def get_phone_status(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> PhoneStatusResponse:
    """Get current phone verification status.
    
    Returns the user's phone number (masked), verification status,
    and whether they can send a new verification code.
    """
    can_send, next_allowed = await _check_rate_limit(
        session,
        str(current_user.id),
        current_user.phone_number or "",
    )
    
    # Mask phone number for privacy (show last 4 digits)
    masked_phone = None
    if current_user.phone_number:
        masked_phone = "***" + current_user.phone_number[-4:]
    
    return PhoneStatusResponse(
        phone_number=masked_phone,
        phone_verified=current_user.phone_verified,
        can_send_code=can_send and not current_user.phone_verified,
        next_send_allowed_at=next_allowed,
    )


@router.post("/send-code", response_model=SendCodeResponse)
async def send_verification_code(
    request: SendCodeRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> SendCodeResponse:
    """Send a verification code to the user's phone.
    
    Rate limited to 3 attempts per hour per user.
    Each code is valid for 10 minutes.
    """
    sms_service = get_sms_service()
    
    # Check if already verified with this number
    if current_user.phone_verified and current_user.phone_number == request.phone_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This phone number is already verified",
        )
    
    # Check rate limit
    can_send, next_allowed = await _check_rate_limit(
        session,
        str(current_user.id),
        request.phone_number,
    )
    
    if not can_send:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many verification attempts. Please try again after {next_allowed.isoformat() if next_allowed else 'an hour'}.",
        )
    
    # Delete any existing pending codes for this user
    await session.execute(
        delete(PhoneVerificationCode)
        .where(PhoneVerificationCode.user_id == current_user.id)
    )
    
    # Generate new code
    code = sms_service.generate_verification_code()
    expires_at = sms_service.get_code_expiry()
    
    # Store hashed code
    verification_code = PhoneVerificationCode(
        user_id=current_user.id,
        phone_number=request.phone_number,
        code_hash=_hash_code(code),
        expires_at=expires_at,
    )
    session.add(verification_code)
    
    # Record the attempt
    attempt = PhoneVerificationAttempt(
        user_id=current_user.id,
        phone_number=request.phone_number,
        ip_address=http_request.client.host if http_request.client else None,
    )
    session.add(attempt)
    
    # Update user's phone number (unverified)
    current_user.phone_number = request.phone_number
    current_user.phone_verified = False
    
    await session.commit()
    
    # Send SMS
    success = await sms_service.send_verification_code(request.phone_number, code)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification code. Please try again.",
        )
    
    logger.info(f"Verification code sent to user {current_user.id}")
    
    return SendCodeResponse(
        success=True,
        message="Verification code sent! Check your phone.",
        expires_at=expires_at,
    )


@router.post("/verify", response_model=VerifyCodeResponse)
async def verify_code(
    request: VerifyCodeRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> VerifyCodeResponse:
    """Verify a phone verification code.
    
    After successful verification:
    - User's phone_verified is set to true
    - If email is also verified, user receives karma bonus (200 karma)
    
    This enables the user to participate in beatmap accuracy voting.
    """
    # Check for existing pending code
    result = await session.execute(
        select(PhoneVerificationCode)
        .where(PhoneVerificationCode.user_id == current_user.id)
        .where(PhoneVerificationCode.is_used.is_(False))
        .order_by(PhoneVerificationCode.created_at.desc())
        .limit(1)
    )
    pending_code = result.scalar_one_or_none()
    
    if not pending_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending verification code. Please request a new code.",
        )
    
    # Check if expired
    if pending_code.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired. Please request a new code.",
        )
    
    # Check attempts
    if pending_code.attempts >= MAX_VERIFICATION_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Too many failed attempts. Please request a new code.",
        )
    
    # Increment attempts
    pending_code.attempts += 1
    
    # Verify code
    if _hash_code(request.code) != pending_code.code_hash:
        await session.commit()
        remaining = MAX_VERIFICATION_ATTEMPTS - pending_code.attempts
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid verification code. {remaining} attempts remaining.",
        )
    
    # Mark code as used
    pending_code.is_used = True
    
    # Update user
    current_user.phone_number = pending_code.phone_number
    current_user.phone_verified = True
    
    # Record successful attempt
    attempt = PhoneVerificationAttempt(
        user_id=current_user.id,
        phone_number=pending_code.phone_number,
        ip_address=http_request.client.host if http_request.client else None,
        success=True,
    )
    session.add(attempt)
    
    await session.commit()
    
    # Check if user now qualifies for karma bonus (email + phone verified)
    karma_bonus_awarded = False
    karma_bonus_amount = 0
    
    if current_user.email_verified:
        accuracy_service = MapAccuracyService(session)
        try:
            awarded = await accuracy_service.award_verification_bonus(current_user.id)
            if awarded:
                karma_bonus_awarded = True
                from app.models.map_accuracy import VERIFIED_USER_KARMA_BONUS
                karma_bonus_amount = VERIFIED_USER_KARMA_BONUS
                logger.info(f"Awarded {karma_bonus_amount} karma to user {current_user.id} for dual verification")
        except Exception as e:
            logger.warning(f"Failed to award karma bonus: {e}")
    
    logger.info(f"Phone verified for user {current_user.id}")
    
    message = "Phone number verified successfully!"
    if karma_bonus_awarded:
        message += f" You've earned {karma_bonus_amount} karma for verifying both email and phone!"
    
    return VerifyCodeResponse(
        success=True,
        message=message,
        phone_verified=True,
        karma_bonus_awarded=karma_bonus_awarded,
        karma_bonus_amount=karma_bonus_amount,
    )


@router.delete("/remove")
async def remove_phone_number(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Remove the user's phone number.
    
    This will also remove their verified status.
    Note: This may affect their ability to vote on beatmap accuracy.
    """
    if not current_user.phone_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No phone number to remove",
        )
    
    # Delete pending verification codes
    await session.execute(
        delete(PhoneVerificationCode)
        .where(PhoneVerificationCode.user_id == current_user.id)
    )
    
    # Clear phone info
    current_user.phone_number = None
    current_user.phone_verified = False
    
    await session.commit()
    
    logger.info(f"Phone number removed for user {current_user.id}")
    
    return {"message": "Phone number removed successfully"}
