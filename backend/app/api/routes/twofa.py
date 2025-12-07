"""
Two-Factor Authentication (2FA) API routes.

Provides endpoints for setting up and managing TOTP-based 2FA.
"""

from __future__ import annotations

import base64
from io import BytesIO
from typing import Annotated

import qrcode
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.user import User
from app.api.deps import get_current_user
from app.services.totp import (
    disable_totp,
    enable_totp,
    get_remaining_backup_codes_count,
    regenerate_backup_codes,
    setup_totp,
    verify_totp_for_login,
)

router = APIRouter(prefix="/auth/2fa", tags=["2fa"])


# =============================================================================
# Response Models
# =============================================================================


class TwoFactorSetupResponse(BaseModel):
    """Response when initiating 2FA setup."""
    
    provisioning_uri: str
    qr_code_base64: str  # Base64 encoded QR code PNG
    backup_codes: list[str]
    message: str


class TwoFactorStatusResponse(BaseModel):
    """Response with current 2FA status."""
    
    enabled: bool
    backup_codes_remaining: int
    enabled_at: str | None


class TwoFactorEnableRequest(BaseModel):
    """Request to enable 2FA with verification code."""
    
    verification_code: str


class TwoFactorDisableRequest(BaseModel):
    """Request to disable 2FA."""
    
    password: str  # Require password for security


class TwoFactorVerifyRequest(BaseModel):
    """Request to verify a 2FA code."""
    
    code: str


class BackupCodesResponse(BaseModel):
    """Response with regenerated backup codes."""
    
    backup_codes: list[str]
    message: str


class MessageResponse(BaseModel):
    """Simple message response."""
    
    success: bool
    message: str


# =============================================================================
# Helper Functions
# =============================================================================


def generate_qr_code_base64(provisioning_uri: str) -> str:
    """
    Generate a QR code image as base64 string.
    
    Args:
        provisioning_uri: The otpauth:// URI
    
    Returns:
        Base64 encoded PNG image
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(provisioning_uri)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    
    return base64.b64encode(buffer.getvalue()).decode()


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "/status",
    response_model=TwoFactorStatusResponse,
    summary="Get 2FA status",
    description="Get the current 2FA status for the authenticated user.",
)
async def get_2fa_status(
    current_user: Annotated[User, Depends(get_current_user)],
) -> TwoFactorStatusResponse:
    """Get current 2FA status."""
    return TwoFactorStatusResponse(
        enabled=current_user.totp_enabled,
        backup_codes_remaining=get_remaining_backup_codes_count(
            current_user.totp_backup_codes
        ),
        enabled_at=(
            current_user.totp_enabled_at.isoformat()
            if current_user.totp_enabled_at
            else None
        ),
    )


@router.post(
    "/setup",
    response_model=TwoFactorSetupResponse,
    summary="Set up 2FA",
    description="Initiate 2FA setup. Returns QR code and backup codes.",
)
async def setup_2fa(
    db: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TwoFactorSetupResponse:
    """Set up 2FA for the current user."""
    if current_user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is already enabled. Disable it first to reconfigure.",
        )
    
    secret, provisioning_uri, backup_codes = await setup_totp(db, current_user)
    qr_code_base64 = generate_qr_code_base64(provisioning_uri)
    
    return TwoFactorSetupResponse(
        provisioning_uri=provisioning_uri,
        qr_code_base64=qr_code_base64,
        backup_codes=backup_codes,
        message="Scan the QR code with your authenticator app, then verify to enable 2FA.",
    )


@router.post(
    "/enable",
    response_model=MessageResponse,
    summary="Enable 2FA",
    description="Enable 2FA after verifying with a code from your authenticator app.",
)
async def enable_2fa(
    request: TwoFactorEnableRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MessageResponse:
    """Enable 2FA with verification code."""
    if current_user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is already enabled.",
        )
    
    if not current_user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please set up 2FA first using the /setup endpoint.",
        )
    
    success = await enable_totp(db, current_user, request.verification_code)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code. Please try again.",
        )
    
    return MessageResponse(
        success=True,
        message="Two-factor authentication has been enabled successfully.",
    )


@router.post(
    "/disable",
    response_model=MessageResponse,
    summary="Disable 2FA",
    description="Disable 2FA. Requires password verification for security.",
)
async def disable_2fa(
    request: TwoFactorDisableRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MessageResponse:
    """Disable 2FA."""
    if not current_user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is not enabled.",
        )
    
    # Verify password
    from app.utils.crypto import verify_password
    
    if not current_user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot disable 2FA for OAuth-only accounts.",
        )
    
    if not verify_password(request.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password.",
        )
    
    await disable_totp(db, current_user)
    
    return MessageResponse(
        success=True,
        message="Two-factor authentication has been disabled.",
    )


@router.post(
    "/verify",
    response_model=MessageResponse,
    summary="Verify 2FA code",
    description="Verify a 2FA code. Used during login when 2FA is enabled.",
)
async def verify_2fa_code(
    request: TwoFactorVerifyRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MessageResponse:
    """Verify a 2FA code."""
    is_valid, error = await verify_totp_for_login(db, current_user, request.code)
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error or "Invalid verification code.",
        )
    
    return MessageResponse(
        success=True,
        message="Verification successful.",
    )


@router.post(
    "/backup-codes/regenerate",
    response_model=BackupCodesResponse,
    summary="Regenerate backup codes",
    description="Generate new backup codes. Old codes will be invalidated.",
)
async def regenerate_backup_codes_endpoint(
    db: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> BackupCodesResponse:
    """Regenerate backup codes."""
    if not current_user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is not enabled. Enable 2FA first.",
        )
    
    backup_codes = await regenerate_backup_codes(db, current_user)
    
    return BackupCodesResponse(
        backup_codes=backup_codes,
        message="New backup codes generated. Save them in a secure location.",
    )
