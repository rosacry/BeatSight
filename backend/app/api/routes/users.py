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
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_current_user_optional, get_db_session
from app.models.user import User
from app.models.user_tag import UserTag
from app.models.song import Song
from app.models.forum import ForumPost
from app.models.role import UserRole
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


class UserTagResponse(BaseModel):
    """User tag response (like osu!'s DEV, VIP, etc.)."""
    
    id: int
    name: str
    background_color: str
    text_color: Optional[str] = None
    
    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    """User info response."""

    id: uuid.UUID
    user_number: int  # Human-friendly ID like osu! (e.g., 1000001)
    email: str
    display_name: str
    email_verified: bool
    phone_number: Optional[str] = None
    phone_verified: bool = False
    avatar_url: Optional[str] = None
    karma_score: int
    created_at: datetime
    tags: list[UserTagResponse] = []  # Custom profile tags

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
    """Get the current user's profile including custom tags."""
    # Build tags list from loaded relationship
    tags = [
        UserTagResponse(
            id=tag.id,
            name=tag.name,
            background_color=tag.background_color,
            text_color=tag.text_color,
        )
        for tag in sorted(current_user.tags, key=lambda t: t.display_order)
    ] if current_user.tags else []
    
    return UserResponse(
        id=current_user.id,
        user_number=current_user.user_number,
        email=current_user.email,
        display_name=current_user.display_name,
        email_verified=current_user.email_verified,
        phone_number=current_user.phone_number,
        phone_verified=current_user.phone_verified,
        avatar_url=current_user.avatar_url,
        karma_score=current_user.karma_score,
        created_at=current_user.created_at,
        tags=tags,
    )


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


class ProfileTag(BaseModel):
    """A custom tag displayed on user profiles (like osu!'s DEV, VIP, etc.)."""
    
    id: int
    name: str
    background_color: str
    text_color: Optional[str] = None
    
    model_config = {"from_attributes": True}


class PublicUserProfile(BaseModel):
    """Public user profile response."""
    
    id: str
    user_number: int  # Human-friendly ID like osu! (e.g., 1)
    display_name: str
    avatar_url: Optional[str] = None
    banner_url: Optional[str] = None
    karma_score: int
    created_at: datetime
    role: str
    is_verified: bool
    country_code: Optional[str] = None
    bio: Optional[str] = None
    # Custom profile tags (like osu!'s DEV, VIP, etc.)
    tags: list[ProfileTag] = []
    # Leaderboard rankings (null if user has hidden from leaderboards)
    karma_rank: Optional[int] = None
    contribution_rank: Optional[int] = None
    # Stats
    songs_uploaded: int
    maps_generated: int
    maps_verified: int
    achievements_count: int
    forum_posts: int
    contribution_count: int = 0  # Total contributions
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


async def _get_user_for_profile(
    user_identifier: str,
    session: AsyncSession,
) -> User | None:
    """
    Fetch user by either UUID or user_number.
    Returns None if not found or banned.
    """
    # Try to parse as UUID first
    try:
        user_uuid = uuid.UUID(user_identifier)
        result = await session.execute(
            select(User)
            .options(
                selectinload(User.roles).selectinload(UserRole.role),
                selectinload(User.tags),  # Load custom tags
            )
            .where(
                User.id == user_uuid,
                User.restriction_level != 'banned'
            )
        )
        return result.scalar_one_or_none()
    except ValueError:
        pass
    
    # Try to parse as integer (user_number)
    try:
        user_number = int(user_identifier)
        result = await session.execute(
            select(User)
            .options(
                selectinload(User.roles).selectinload(UserRole.role),
                selectinload(User.tags),  # Load custom tags
            )
            .where(
                User.user_number == user_number,
                User.restriction_level != 'banned'
            )
        )
        return result.scalar_one_or_none()
    except ValueError:
        return None


@router.get("/{user_id}/profile", response_model=PublicUserProfile)
async def get_public_user_profile(
    user_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> PublicUserProfile:
    """
    Get a user's public profile.
    
    Supports lookup by either UUID or user_number (e.g., /users/1/profile).
    Returns public information about a user including their stats and activity.
    """
    from app.models.user_settings import UserSettings
    from app.models.training_contribution import TrainingContribution
    
    user = await _get_user_for_profile(user_id, session)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Get song count
    songs_result = await session.execute(
        select(func.count()).select_from(Song).where(
            Song.created_by_id == user.id
        )
    )
    songs_count = songs_result.scalar() or 0
    
    # Get forum posts count
    try:
        posts_result = await session.execute(
            select(func.count()).select_from(ForumPost).where(
                ForumPost.author_id == user.id,
                ForumPost.deleted_at.is_(None)
            )
        )
        forum_posts = posts_result.scalar() or 0
    except Exception:
        forum_posts = 0
    
    # Get contribution count
    contribution_count = 0
    try:
        contrib_result = await session.execute(
            select(func.count()).select_from(TrainingContribution).where(
                TrainingContribution.user_id == user.id
            )
        )
        contribution_count = contrib_result.scalar() or 0
    except Exception:
        pass
    
    # Determine role
    role = "user"
    if user.roles:
        role_codes = [r.role.code for r in user.roles if r.role]
        if "admin" in role_codes:
            role = "admin"
        elif "staff" in role_codes:
            role = "staff"
        elif "verifier" in role_codes:
            role = "verifier"
    
    # Build profile tags list
    profile_tags = [
        ProfileTag(
            id=tag.id,
            name=tag.name,
            background_color=tag.background_color,
            text_color=tag.text_color,
        )
        for tag in sorted(user.tags, key=lambda t: t.display_order)
    ] if user.tags else []
    
    # Calculate leaderboard ranks for ALL users (including hidden users viewing their own profile)
    # Hidden users still have ranks - they just appear anonymously on the leaderboard
    # Ranks include ALL non-banned users to be consistent with leaderboard display
    karma_rank = None
    contribution_rank = None
    
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Karma rank: count users with more karma, or same karma but reached it earlier
        # Tie-breaker: whoever reached the current score FIRST ranks higher
        # Include ALL non-banned users (even hidden ones) so ranks match leaderboard
        karma_rank_result = await session.execute(
            select(func.count())
            .select_from(User)
            .where(
                User.restriction_level != 'banned',
                or_(
                    User.karma_score > (user.karma_score or 0),
                    # Tie-breaker: whoever reached the same score FIRST ranks higher
                    and_(
                        User.karma_score == (user.karma_score or 0),
                        # Earlier karma_score_achieved_at = higher rank
                        # Use COALESCE to handle NULL (treat as very late date for legacy data)
                        func.coalesce(User.karma_score_achieved_at, User.created_at) < 
                        func.coalesce(user.karma_score_achieved_at, user.created_at)
                    )
                )
            )
        )
        users_above_karma = karma_rank_result.scalar() or 0
        karma_rank = users_above_karma + 1
        
        # Contribution rank: count users with more contributions
        # For ties, whoever got their Nth contribution approved FIRST ranks higher
        
        # First get user's approved contribution count
        user_contrib_result = await session.execute(
            select(func.count())
            .select_from(TrainingContribution)
            .where(
                TrainingContribution.user_id == user.id,
                TrainingContribution.status.in_(['approved', 'exported'])
            )
        )
        user_approved_count = user_contrib_result.scalar() or 0
        
        # Get the timestamp of the user's Nth (most recent) approved contribution
        # This is used for tie-breaking - whoever got to N contributions first ranks higher
        user_nth_contrib_result = await session.execute(
            select(TrainingContribution.reviewed_at)
            .where(
                TrainingContribution.user_id == user.id,
                TrainingContribution.status.in_(['approved', 'exported'])
            )
            .order_by(TrainingContribution.reviewed_at.desc())
            .limit(1)
        )
        user_nth_contrib_at = user_nth_contrib_result.scalar_one_or_none()
        
        # Build subquery to get each user's contribution count AND their Nth contribution timestamp
        contrib_subquery = (
            select(
                TrainingContribution.user_id,
                func.count().label('approved_count'),
                func.max(TrainingContribution.reviewed_at).label('latest_contrib_at')
            )
            .where(TrainingContribution.status.in_(['approved', 'exported']))
            .group_by(TrainingContribution.user_id)
            .subquery()
        )
        
        # Count users with more contributions (include ALL non-banned users)
        # Only calculate contribution rank if user has at least 1 contribution
        if user_approved_count > 0:
            contrib_rank_result = await session.execute(
                select(func.count())
                .select_from(User)
                .outerjoin(contrib_subquery, User.id == contrib_subquery.c.user_id)
                .where(
                    User.restriction_level != 'banned',
                    or_(
                        func.coalesce(contrib_subquery.c.approved_count, 0) > user_approved_count,
                        # Tie-breaker: whoever reached the same count FIRST ranks higher
                        and_(
                            func.coalesce(contrib_subquery.c.approved_count, 0) == user_approved_count,
                            # Earlier timestamp = higher rank
                            func.coalesce(contrib_subquery.c.latest_contrib_at, User.created_at) < 
                            func.coalesce(user_nth_contrib_at, user.created_at)
                        )
                    )
                )
            )
            users_above_contrib = contrib_rank_result.scalar() or 0
            contribution_rank = users_above_contrib + 1
        # else: contribution_rank stays None (user has no contributions)
        
        logger.info(f"Profile rank calc for user {user.user_number}: "
                   f"karma_rank={karma_rank}, contribution_rank={contribution_rank}")
    except Exception as e:
        # If there's an issue calculating ranks, leave them null
        logger.exception(f"Error calculating ranks for user {user.id}: {e}")
    
    return PublicUserProfile(
        id=str(user.id),
        user_number=user.user_number,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        banner_url=getattr(user, 'banner_url', None),
        karma_score=user.karma_score or 0,
        created_at=user.created_at,
        role=role,
        is_verified=user.email_verified or False,
        country_code=getattr(user, 'country_code', None),
        bio=getattr(user, 'bio', None),
        tags=profile_tags,
        karma_rank=karma_rank,
        contribution_rank=contribution_rank,
        songs_uploaded=songs_count,
        maps_generated=songs_count,  # Approximate - should count maps
        maps_verified=0,  # TODO: Count verified maps
        achievements_count=0,  # TODO: Count achievements
        forum_posts=forum_posts,
        contribution_count=contribution_count,
        last_active=getattr(user, 'last_active_at', None),
    )


async def _get_user_by_identifier(
    user_identifier: str,
    session: AsyncSession,
) -> User | None:
    """
    Fetch user by either UUID or user_number (no eager loading).
    Returns None if not found or banned.
    """
    # Try to parse as UUID first
    try:
        user_uuid = uuid.UUID(user_identifier)
        result = await session.execute(
            select(User).where(
                User.id == user_uuid,
                User.restriction_level != 'banned'
            )
        )
        return result.scalar_one_or_none()
    except ValueError:
        pass
    
    # Try to parse as integer (user_number)
    try:
        user_number = int(user_identifier)
        result = await session.execute(
            select(User).where(
                User.user_number == user_number,
                User.restriction_level != 'banned'
            )
        )
        return result.scalar_one_or_none()
    except ValueError:
        return None


# =============================================================================
# Hover Card Endpoint (Lightweight user info for tooltips)
# =============================================================================


class UserHoverCardResponse(BaseModel):
    """Lightweight user data for hover card tooltips (osu!-style)."""
    
    id: str
    user_number: int
    display_name: str
    avatar_url: Optional[str] = None
    banner_url: Optional[str] = None
    karma_score: int
    is_online: bool = False  # TODO: Implement online status tracking
    last_active: Optional[datetime] = None
    role: str
    country_code: Optional[str] = None


@router.get("/{user_id}/hover-card", response_model=UserHoverCardResponse)
async def get_user_hover_card(
    user_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> UserHoverCardResponse:
    """
    Get lightweight user data for hover card tooltips.
    
    This is a faster endpoint than the full profile, designed for
    quick user previews when hovering over usernames (similar to osu!'s user cards).
    
    Supports lookup by either UUID or user_number (e.g., /users/1/hover-card).
    """
    user = await _get_user_by_identifier(user_id, session)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Determine role
    role = "user"
    if user.roles:
        role_codes = [r.role.code for r in user.roles if r.role]
        if "admin" in role_codes:
            role = "admin"
        elif "staff" in role_codes:
            role = "staff"
        elif "verifier" in role_codes:
            role = "verifier"
    
    return UserHoverCardResponse(
        id=str(user.id),
        user_number=user.user_number,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        banner_url=getattr(user, 'banner_url', None),
        karma_score=user.karma_score or 0,
        is_online=False,  # TODO: Implement real online status
        last_active=getattr(user, 'last_active_at', None),
        role=role,
        country_code=getattr(user, 'country_code', None),
    )


@router.get("/{user_id}/maps", response_model=UserMapsResponse)
async def get_user_maps(
    user_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> UserMapsResponse:
    """
    Get a user's public beatmaps.
    
    Supports lookup by either UUID or user_number.
    """
    user = await _get_user_by_identifier(user_id, session)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Fetch user's songs
    songs_result = await session.execute(
        select(Song)
        .where(
            Song.created_by_id == user.id
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

