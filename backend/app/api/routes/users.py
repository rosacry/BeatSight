"""User account management API routes."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


class UserUpdateRequest(BaseModel):
    """User profile update request."""

    display_name: Optional[str] = Field(None, min_length=2, max_length=120)


class UserResponse(BaseModel):
    """User info response."""

    id: uuid.UUID
    email: str
    display_name: str
    email_verified: bool
    karma_score: int
    created_at: datetime

    model_config = {"from_attributes": True}


class PasswordChangeRequest(BaseModel):
    """Password change request."""

    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


class DeleteAccountRequest(BaseModel):
    """Account deletion confirmation request."""

    confirmation: str = Field(
        ..., description="Must be exactly 'DELETE' to confirm account deletion"
    )
    password: str = Field(..., description="Current password for verification")


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Get the current user's profile."""
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    request: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    """
    Update the current user's profile.

    Updatable fields:
    - display_name: User's display name

    Note: For preferences, use /api/sync/preferences instead.
    """
    # Update fields if provided
    if request.display_name is not None:
        current_user.display_name = request.display_name

    session.add(current_user)
    await session.commit()
    await session.refresh(current_user)

    logger.info(f"User {current_user.id} updated their profile")

    return UserResponse.model_validate(current_user)


@router.post("/me/password", response_model=MessageResponse)
async def change_password(
    request: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    """
    Change the current user's password.

    Requires the current password for verification.
    Note: Only available for users with password-based auth, not OAuth.
    """
    # Check if user has a password set (not OAuth-only user)
    if not current_user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password change not available for OAuth users",
        )

    # Verify current password using bcrypt
    import bcrypt

    if not bcrypt.checkpw(
        request.current_password.encode("utf-8"),
        current_user.hashed_password.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    # Validate new password is different
    if request.current_password == request.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )

    # Hash and update password
    new_hash = bcrypt.hashpw(
        request.new_password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")
    current_user.hashed_password = new_hash
    session.add(current_user)
    await session.commit()

    logger.info(f"User {current_user.id} changed their password")

    return MessageResponse(message="Password changed successfully")


@router.delete("/me", response_model=MessageResponse)
async def delete_account(
    request: DeleteAccountRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    """
    Delete the current user's account.

    This is a destructive operation that:
    1. Deletes all user data
    2. Removes all associated songs, beatmaps, and jobs
    3. Cannot be undone

    Requires typing 'DELETE' and password confirmation.
    Note: For OAuth users without password, password field can be empty but
    confirmation text is still required.
    """
    # Verify confirmation text
    if request.confirmation != "DELETE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please type 'DELETE' to confirm account deletion",
        )

    # Verify password if user has one
    if current_user.hashed_password:
        import bcrypt

        if not bcrypt.checkpw(
            request.password.encode("utf-8"),
            current_user.hashed_password.encode("utf-8"),
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password is incorrect",
            )

    user_id = current_user.id
    user_email = current_user.email

    # Delete the user (cascade should handle related records)
    await session.delete(current_user)
    await session.commit()

    logger.warning(f"User {user_id} ({user_email}) deleted their account")

    return MessageResponse(message="Account deleted successfully")
