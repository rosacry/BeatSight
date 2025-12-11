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
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_current_user_optional, get_db_session
from app.models.user import User
from app.models.song import Song
from app.models.forum import ForumPost
from app.schemas.user_settings import UserSettingsRead, UserSettingsUpdate
from app.services.storage import get_storage
from app.services.user_settings import UserSettingsService

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


# =============================================================================
# User Settings Endpoints
# =============================================================================


@router.get("/me/settings", response_model=UserSettingsRead)
async def get_user_settings(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> UserSettingsRead:
    """Get the current user's settings.
    
    Creates default settings if none exist yet.
    """
    service = UserSettingsService(session)
    settings = await service.get_or_create_settings(current_user.id)
    return UserSettingsRead.model_validate(settings)


@router.patch("/me/settings", response_model=UserSettingsRead)
async def update_user_settings(
    request: UserSettingsUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> UserSettingsRead:
    """Update the current user's settings.
    
    Only provided fields will be updated. Omitted fields remain unchanged.
    
    **Privacy Settings:**
    - `default_upload_visibility`: public, anonymous, or private
    - `show_activity_on_profile`: Show uploads/edits on public profile
    - `show_statistics_on_profile`: Show stats on public profile
    - `hide_from_leaderboards`: Hide from all public leaderboards (anonymous mode)
    - `hide_from_public_queues`: Hide jobs from public queue view (anonymous mode)
    
    **AI Re-evaluation Settings:**
    - `re_evaluation_policy`: auto_free, opt_in, or opt_out
      - auto_free: Automatically improve maps when model updates (free, recommended)
      - opt_in: Only re-evaluate when you request it
      - opt_out: Never re-evaluate, keep original maps
    
    **Notification Settings:**
    - `notify_job_complete`: Notify when AI job finishes
    - `notify_map_verified`: Notify when community verifies your map
    - `notify_re_evaluation_available`: Notify about new model versions
    - `notify_weekly_summary`: Receive weekly activity digest
    """
    service = UserSettingsService(session)
    settings = await service.update_settings(
        current_user.id,
        default_upload_visibility=request.default_upload_visibility,
        show_activity_on_profile=request.show_activity_on_profile,
        show_statistics_on_profile=request.show_statistics_on_profile,
        hide_from_leaderboards=request.hide_from_leaderboards,
        hide_from_public_queues=request.hide_from_public_queues,
        re_evaluation_policy=request.re_evaluation_policy,
        notify_job_complete=request.notify_job_complete,
        notify_map_verified=request.notify_map_verified,
        notify_re_evaluation_available=request.notify_re_evaluation_available,
        notify_weekly_summary=request.notify_weekly_summary,
    )
    return UserSettingsRead.model_validate(settings)


# =============================================================================
# Public User Profile Endpoint
# =============================================================================


class PublicUserProfile(BaseModel):
    """Public user profile response."""
    
    id: str
    display_name: str
    avatar_url: Optional[str] = None
    banner_url: Optional[str] = None
    karma_score: int
    created_at: datetime
    role: str
    is_verified: bool
    country_code: Optional[str] = None
    bio: Optional[str] = None
    # Stats
    songs_uploaded: int
    maps_generated: int
    maps_verified: int
    achievements_count: int
    forum_posts: int
    # Activity
    last_active: Optional[datetime] = None


class UserMapItem(BaseModel):
    """User's map item for listing."""
    
    id: str
    song_id: str
    title: str
    artist: str
    cover_url: Optional[str] = None
    is_verified: bool
    created_at: datetime
    play_count: int


class UserMapsResponse(BaseModel):
    """Response for user's maps."""
    
    items: list[UserMapItem]
    total: int


@router.get("/{user_id}/profile", response_model=PublicUserProfile)
async def get_public_user_profile(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> PublicUserProfile:
    """
    Get a user's public profile.
    
    Returns public information about a user including their stats and activity.
    """
    # Fetch the user (User model uses restriction_level, not deleted_at)
    result = await session.execute(
        select(User)
        .options(selectinload(User.roles))
        .where(
            User.id == user_id,
            User.restriction_level != 'banned'
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Get song count
    songs_result = await session.execute(
        select(func.count()).select_from(Song).where(
            Song.created_by_id == user_id
        )
    )
    songs_count = songs_result.scalar() or 0
    
    # Get forum posts count
    try:
        posts_result = await session.execute(
            select(func.count()).select_from(ForumPost).where(
                ForumPost.author_id == user_id,
                ForumPost.deleted_at.is_(None)
            )
        )
        forum_posts = posts_result.scalar() or 0
    except Exception:
        forum_posts = 0
    
    # Determine role
    role = "user"
    if user.roles:
        role_names = [r.name for r in user.roles]
        if "admin" in role_names:
            role = "admin"
        elif "staff" in role_names:
            role = "staff"
        elif "verifier" in role_names:
            role = "verifier"
    
    return PublicUserProfile(
        id=str(user.id),
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        banner_url=getattr(user, 'banner_url', None),
        karma_score=user.karma_score or 0,
        created_at=user.created_at,
        role=role,
        is_verified=user.email_verified or False,
        country_code=getattr(user, 'country_code', None),
        bio=getattr(user, 'bio', None),
        songs_uploaded=songs_count,
        maps_generated=songs_count,  # Approximate - should count maps
        maps_verified=0,  # TODO: Count verified maps
        achievements_count=0,  # TODO: Count achievements
        forum_posts=forum_posts,
        last_active=getattr(user, 'last_active_at', None),
    )


@router.get("/{user_id}/maps", response_model=UserMapsResponse)
async def get_user_maps(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> UserMapsResponse:
    """
    Get a user's public beatmaps.
    """
    # Verify user exists (User model uses restriction_level instead of deleted_at)
    result = await session.execute(
        select(User).where(
            User.id == user_id,
            User.restriction_level != 'banned'
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Fetch user's songs
    songs_result = await session.execute(
        select(Song)
        .where(
            Song.created_by_id == user_id
        )
        .order_by(Song.created_at.desc())
        .limit(50)
    )
    songs = songs_result.scalars().all()
    
    items = [
        UserMapItem(
            id=str(s.id),
            song_id=str(s.id),
            title=s.title,
            artist=s.artist or "Unknown Artist",
            cover_url=getattr(s, 'cover_url', None),
            is_verified=getattr(s, 'is_verified', False),
            created_at=s.created_at,
            play_count=0,  # TODO: Track play counts
        )
        for s in songs
    ]
    
    return UserMapsResponse(items=items, total=len(items))

