"""
Session verification API routes.

Implements osu!-style sensitive action verification where users must
verify their identity via email code or link before accessing settings,
credit balances, and other sensitive areas.

Endpoints:
- GET  /verify/status    - Check if current session is verified
- POST /verify/initiate  - Start verification (sends email)
- POST /verify/code      - Verify using code
- GET  /verify/link      - Verify using link (from email)
- POST /verify/reissue   - Reissue verification code
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.services.email import get_email_service
from app.services.session_verification import get_session_verification_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/verify", tags=["verification"])


# =============================================================================
# Request/Response Models
# =============================================================================


class VerificationStatusResponse(BaseModel):
    """Response for verification status check."""
    
    is_verified: bool
    requires_verification: bool = False
    message: str | None = None


class VerificationInitiateResponse(BaseModel):
    """Response when verification is initiated."""
    
    success: bool
    obscured_email: str
    message: str


class VerificationCodeRequest(BaseModel):
    """Request to verify using a code."""
    
    verification_code: str = Field(
        ..., 
        description="8-character verification code from email",
        min_length=8,
        max_length=16,  # Allow spaces
    )


class VerificationCodeResponse(BaseModel):
    """Response for code verification attempt."""
    
    success: bool
    message: str | None = None


class ReissueCodeResponse(BaseModel):
    """Response when code is reissued."""
    
    success: bool
    message: str


class VerificationLinkResponse(BaseModel):
    """Response for link verification (shown in browser)."""
    
    success: bool
    message: str


# =============================================================================
# Helper Functions
# =============================================================================


def _get_client_info(request: Request) -> tuple[str | None, str | None]:
    """Extract client IP and country from request."""
    client_ip = request.client.host if request.client else None
    
    # Try to get country from CF headers or similar
    # In production, this would come from Cloudflare or a GeoIP service
    country = request.headers.get("CF-IPCountry")
    if not country:
        country = request.headers.get("X-Country-Code")
    
    return (client_ip, country)


def _get_token_from_request(request: Request) -> str | None:
    """Extract the access token from Authorization header."""
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


# =============================================================================
# API Endpoints
# =============================================================================


@router.get("/status", response_model=VerificationStatusResponse)
async def get_verification_status(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> VerificationStatusResponse:
    """
    Check if the current session is verified for sensitive actions.
    
    Returns verification status. If not verified, the frontend should
    redirect to verification flow before allowing access to sensitive areas.
    """
    token = _get_token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No access token provided",
        )
    
    verification_service = get_session_verification_service(session)
    is_verified = await verification_service.is_session_verified(current_user, token)
    
    return VerificationStatusResponse(
        is_verified=is_verified,
        requires_verification=not is_verified,
        message=None if is_verified else "Session verification required",
    )


@router.post("/initiate", response_model=VerificationInitiateResponse)
async def initiate_verification(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> VerificationInitiateResponse:
    """
    Initiate session verification by sending a verification email.
    
    This is called when a user tries to access a sensitive area (settings,
    credits, etc.) and their session is not verified.
    
    Sends an email with:
    - 8-character verification code
    - One-click verification link
    """
    token = _get_token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No access token provided",
        )
    
    client_ip, country = _get_client_info(request)
    
    verification_service = get_session_verification_service(session)
    
    # Generate verification code and link
    code, link_key, obscured_email = await verification_service.initiate_verification(
        user=current_user,
        access_token=token,
        request_ip=client_ip,
        request_country=country,
    )
    
    # Send verification email in background
    email_service = get_email_service()
    background_tasks.add_task(
        email_service.send_session_verification,
        email=current_user.email,
        display_name=current_user.display_name,
        verification_code=code,
        link_key=link_key,
        request_country=country,
    )
    
    logger.info(f"Initiated verification for user {current_user.id} from {country or 'unknown'}")
    
    return VerificationInitiateResponse(
        success=True,
        obscured_email=obscured_email,
        message=f"An email has been sent to {obscured_email} with a verification code. Enter the code.",
    )


@router.post("/code", response_model=VerificationCodeResponse)
async def verify_with_code(
    request: Request,
    body: VerificationCodeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> VerificationCodeResponse:
    """
    Verify the session using the code from the email.
    
    The code is 8 hex characters (e.g., "b8672ff1" or "b867 2ff1").
    Spaces are automatically stripped.
    """
    token = _get_token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No access token provided",
        )
    
    verification_service = get_session_verification_service(session)
    success, error_message = await verification_service.verify_code(
        user=current_user,
        access_token=token,
        submitted_code=body.verification_code,
    )
    
    if success:
        logger.info(f"User {current_user.id} verified session via code")
        return VerificationCodeResponse(
            success=True,
            message="Verification successful",
        )
    
    # If error indicates reissue, send new email
    if error_message and "new code has been sent" in error_message.lower():
        # The service already reissued - we need to send a new email
        code, link_key = await verification_service.reissue_code(current_user, token)
        
        # Get client info for the email
        client_ip, country = _get_client_info(request)
        
        email_service = get_email_service()
        await email_service.send_session_verification(
            email=current_user.email,
            display_name=current_user.display_name,
            verification_code=code,
            link_key=link_key,
            request_country=country,
        )
    
    return VerificationCodeResponse(
        success=False,
        message=error_message or "Verification failed",
    )


@router.get("/link")
async def verify_with_link(
    key: str = Query(..., description="Verification key from email link"),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Verify the session using the one-click link from the email.
    
    This endpoint is accessed directly from the email link.
    On success, redirects to a success page. On failure, redirects to error page.
    
    Note: This verifies the session that initiated the verification,
    not necessarily the current browser session.
    """
    verification_service = get_session_verification_service(session)
    success, user_id, error_message = await verification_service.verify_link(key)
    
    email_service = get_email_service()
    frontend_url = email_service.frontend_url
    
    if success:
        logger.info(f"User {user_id} verified session via link")
        # Redirect to success page
        return RedirectResponse(
            url=f"{frontend_url}/account/verify/success",
            status_code=status.HTTP_302_FOUND,
        )
    
    # Redirect to error page
    logger.warning(f"Failed link verification: {error_message}")
    return RedirectResponse(
        url=f"{frontend_url}/account/verify/invalid",
        status_code=status.HTTP_302_FOUND,
    )


@router.post("/reissue", response_model=ReissueCodeResponse)
async def reissue_verification_code(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ReissueCodeResponse:
    """
    Request a new verification code.
    
    Use this if the previous code expired or was not received.
    """
    token = _get_token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No access token provided",
        )
    
    verification_service = get_session_verification_service(session)
    
    # Check if already verified
    is_verified = await verification_service.is_session_verified(current_user, token)
    if is_verified:
        return ReissueCodeResponse(
            success=False,
            message="Session is already verified",
        )
    
    client_ip, country = _get_client_info(request)
    
    # Reissue code
    code, link_key = await verification_service.reissue_code(current_user, token)
    
    # Send new verification email
    email_service = get_email_service()
    background_tasks.add_task(
        email_service.send_session_verification,
        email=current_user.email,
        display_name=current_user.display_name,
        verification_code=code,
        link_key=link_key,
        request_country=country,
    )
    
    logger.info(f"Reissued verification code for user {current_user.id}")
    
    return ReissueCodeResponse(
        success=True,
        message="A new verification code has been sent to your email",
    )
