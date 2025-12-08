"""User account management API routes."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from io import BytesIO
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from PIL import Image
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.services.storage import get_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])

# Maximum avatar file size: 5MB
MAX_AVATAR_SIZE = 5 * 1024 * 1024
# Avatar dimensions after processing
AVATAR_SIZE = (256, 256)
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


class UserUpdateRequest(BaseModel):
    """User profile update request."""

    display_name: Optional[str] = Field(None, min_length=2, max_length=120)


class UserResponse(BaseModel):
    """User info response."""

    id: uuid.UUID
    email: str
    display_name: str
    email_verified: bool
    phone_number: Optional[str] = None
    phone_verified: bool = False
    avatar_url: Optional[str] = None
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


@router.post("/me/avatar", response_model=UserResponse)
async def upload_avatar(
    file: Annotated[
        UploadFile, File(description="Avatar image (JPEG, PNG, WebP, GIF)")
    ],
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    """
    Upload a new avatar image.

    The image will be resized to 256x256 pixels.
    Supported formats: JPEG, PNG, WebP, GIF
    Maximum file size: 5MB
    """
    # Validate content type
    content_type = file.content_type or ""
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported image type. Allowed: JPEG, PNG, WebP, GIF",
        )

    # Read and validate file size
    content = await file.read()
    if len(content) > MAX_AVATAR_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Avatar file too large. Maximum size: 5MB",
        )

    try:
        # SECURITY: Limit max pixels to prevent decompression bomb attacks
        # Malicious images can have small file sizes but enormous dimensions
        Image.MAX_IMAGE_PIXELS = 10_000_000  # 10 megapixels max

        # Process image with Pillow
        img = Image.open(BytesIO(content))

        # Validate dimensions BEFORE any processing
        if img.width > 4096 or img.height > 4096:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image dimensions too large. Maximum 4096x4096 pixels.",
            )

        # Convert to RGB if necessary (for PNG with alpha, etc.)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Resize with aspect ratio preservation and center crop
        img.thumbnail(
            (AVATAR_SIZE[0] * 2, AVATAR_SIZE[1] * 2), Image.Resampling.LANCZOS
        )

        # Center crop to square
        width, height = img.size
        left = (width - min(width, height)) // 2
        top = (height - min(width, height)) // 2
        right = left + min(width, height)
        bottom = top + min(width, height)
        img = img.crop((left, top, right, bottom))

        # Final resize to target size
        img = img.resize(AVATAR_SIZE, Image.Resampling.LANCZOS)

        # Save to buffer as JPEG
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=85, optimize=True)
        buffer.seek(0)

    except Exception as e:
        logger.error(f"Failed to process avatar image: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to process image. Please upload a valid image file.",
        )

    # Upload to storage
    try:
        storage = get_storage()
        avatar_key = f"avatars/{current_user.id}.jpg"

        # Store directly
        await storage.store(avatar_key, buffer.read(), "image/jpeg")

        # Generate URL (could be presigned URL or public URL depending on storage config)
        avatar_url = f"/api/storage/avatars/{current_user.id}"

    except Exception as e:
        logger.error(f"Failed to upload avatar to storage: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store avatar. Please try again.",
        )

    # Update user record
    current_user.avatar_url = avatar_url
    session.add(current_user)
    await session.commit()
    await session.refresh(current_user)

    logger.info(f"User {current_user.id} uploaded new avatar")

    return UserResponse.model_validate(current_user)


@router.delete("/me/avatar", response_model=UserResponse)
async def delete_avatar(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    """
    Delete the current user's avatar.

    Resets to default (initials-based) avatar.
    """
    if not current_user.avatar_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No avatar to delete",
        )

    # Remove from storage
    try:
        storage = get_storage()
        avatar_key = f"avatars/{current_user.id}.jpg"
        await storage.delete(avatar_key)
    except Exception as e:
        logger.warning(f"Failed to delete avatar from storage: {e}")
        # Continue anyway - user should still be able to reset their avatar_url

    # Clear avatar URL
    current_user.avatar_url = None
    session.add(current_user)
    await session.commit()
    await session.refresh(current_user)

    logger.info(f"User {current_user.id} deleted their avatar")

    return UserResponse.model_validate(current_user)


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
