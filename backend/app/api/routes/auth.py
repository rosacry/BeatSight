"""Authentication API routes."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.services.auth import AuthService
from app.services.email import get_email_service
from app.services.account_security import get_account_security_service
from app.utils.password_validation import validate_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=2, max_length=120)


class LoginRequest(BaseModel):
    """User login request."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """User info response."""

    id: uuid.UUID
    email: str
    display_name: str
    email_verified: bool
    karma_score: int
    created_at: datetime

    model_config = {"from_attributes": True}


class RefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    """Forgot password request."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Reset password request."""

    token: str
    new_password: str = Field(min_length=8, max_length=128)


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    request: RegisterRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """
    Register a new user account.

    Returns access and refresh tokens upon successful registration.
    """
    auth_service = AuthService(session)

    # Validate password strength
    password_result = validate_password(
        request.password,
        email=request.email,
        display_name=request.display_name,
    )
    if not password_result.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=password_result.error_message,
        )

    # Check if email already exists
    existing_user = await auth_service.get_user_by_email(request.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    # Create new user
    user = User(
        email=request.email,
        display_name=request.display_name,
        hashed_password=auth_service.hash_password(request.password),
        auth_provider_id=f"local:{uuid.uuid4()}",  # Local auth provider
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Send welcome email in background
    email_service = get_email_service()
    background_tasks.add_task(email_service.send_welcome, user.email, user.display_name)

    # Generate tokens
    access_token = auth_service.create_access_token(user.id)
    refresh_token = auth_service.create_refresh_token(user.id)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    http_request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """
    Authenticate a user and return tokens.

    Validates email and password, returns access and refresh tokens.
    Implements account lockout after multiple failed attempts.
    """
    security_service = get_account_security_service()

    # Check if account is locked
    is_locked, lockout_until = await security_service.is_account_locked(request.email)
    if is_locked:
        # Calculate remaining lockout time
        from datetime import timezone

        remaining = lockout_until - datetime.now(timezone.utc)
        minutes_remaining = max(1, int(remaining.total_seconds() / 60))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account temporarily locked due to multiple failed login attempts. Try again in {minutes_remaining} minutes.",
            headers={"Retry-After": str(int(remaining.total_seconds()))},
        )

    auth_service = AuthService(session)
    user = await auth_service.authenticate_user(request.email, request.password)

    if user is None:
        # Record failed attempt
        client_ip = http_request.client.host if http_request.client else "unknown"
        attempt_result = await security_service.record_failed_attempt(
            request.email, client_ip
        )

        if attempt_result["locked"]:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Account locked due to multiple failed login attempts. Try again later.",
                headers={"Retry-After": "900"},  # 15 minutes
            )

        # Include remaining attempts hint (but don't reveal if email exists)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Successful login - clear any failed attempts
    await security_service.clear_failed_attempts(request.email)

    access_token = auth_service.create_access_token(user.id)
    refresh_token = auth_service.create_refresh_token(user.id)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    request: RefreshRequest,
    session: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """
    Refresh access token using a valid refresh token.

    Returns new access and refresh tokens.
    """
    auth_service = AuthService(session)
    payload = auth_service.decode_token(request.refresh_token)

    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identifier",
        )

    user = await auth_service.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    access_token = auth_service.create_access_token(user.id)
    refresh_token = auth_service.create_refresh_token(user.id)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """
    Get current authenticated user's profile.

    Requires valid access token.
    """
    return UserResponse.model_validate(current_user)


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    request: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    """
    Request a password reset email.

    Always returns success to prevent email enumeration attacks.
    """
    auth_service = AuthService(session)
    user = await auth_service.get_user_by_email(request.email)

    if user:
        # Send reset email in background
        email_service = get_email_service()
        background_tasks.add_task(
            email_service.send_password_reset,
            user.id,
            user.email,
            user.display_name,
        )
        logger.info(f"Password reset requested for {request.email}")
    else:
        # Don't reveal that email doesn't exist
        logger.info(f"Password reset requested for non-existent email: {request.email}")

    # Always return success to prevent email enumeration
    return MessageResponse(
        message="If an account exists with that email, you will receive a password reset link"
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    request: ResetPasswordRequest,
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    """
    Reset password using a valid reset token.
    """
    # Validate password strength first (before token verification)
    password_result = validate_password(request.new_password)
    if not password_result.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=password_result.error_message,
        )

    email_service = get_email_service()
    payload = email_service.verify_password_reset_token(request.token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token payload",
        )

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token payload",
        )

    auth_service = AuthService(session)
    user = await auth_service.get_user_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found",
        )

    # Verify email matches token (extra security)
    if user.email != payload.get("email"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token does not match user",
        )

    # Update password
    user.hashed_password = auth_service.hash_password(request.new_password)
    await session.commit()

    logger.info(f"Password reset completed for user {user_id}")

    return MessageResponse(message="Password has been reset successfully")
