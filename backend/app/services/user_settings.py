"""Service layer for user settings operations."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_settings import (
    ReEvaluationPolicy,
    UploadVisibility,
    UserSettings,
)


class UserSettingsService:
    """Service for managing user settings."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create_settings(self, user_id: uuid.UUID) -> UserSettings:
        """Get user settings, creating default settings if none exist.
        
        Args:
            user_id: The user ID to get settings for.
            
        Returns:
            The user's settings (existing or newly created).
        """
        result = await self._session.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        settings = result.scalar_one_or_none()
        
        if settings is None:
            settings = UserSettings(user_id=user_id)
            self._session.add(settings)
            await self._session.commit()
            await self._session.refresh(settings)
        
        return settings

    async def get_settings(self, user_id: uuid.UUID) -> UserSettings | None:
        """Get user settings if they exist.
        
        Args:
            user_id: The user ID to get settings for.
            
        Returns:
            The user's settings, or None if not found.
        """
        result = await self._session.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def update_settings(
        self,
        user_id: uuid.UUID,
        *,
        default_upload_visibility: Optional[UploadVisibility] = None,
        show_activity_on_profile: Optional[bool] = None,
        show_statistics_on_profile: Optional[bool] = None,
        re_evaluation_policy: Optional[ReEvaluationPolicy] = None,
        notify_job_complete: Optional[bool] = None,
        notify_map_verified: Optional[bool] = None,
        notify_re_evaluation_available: Optional[bool] = None,
        notify_weekly_summary: Optional[bool] = None,
    ) -> UserSettings:
        """Update user settings.
        
        Only updates fields that are explicitly provided (not None).
        
        Args:
            user_id: The user ID to update settings for.
            **kwargs: Settings fields to update.
            
        Returns:
            The updated user settings.
        """
        settings = await self.get_or_create_settings(user_id)
        
        if default_upload_visibility is not None:
            settings.default_upload_visibility = default_upload_visibility
        if show_activity_on_profile is not None:
            settings.show_activity_on_profile = show_activity_on_profile
        if show_statistics_on_profile is not None:
            settings.show_statistics_on_profile = show_statistics_on_profile
        if re_evaluation_policy is not None:
            settings.re_evaluation_policy = re_evaluation_policy
        if notify_job_complete is not None:
            settings.notify_job_complete = notify_job_complete
        if notify_map_verified is not None:
            settings.notify_map_verified = notify_map_verified
        if notify_re_evaluation_available is not None:
            settings.notify_re_evaluation_available = notify_re_evaluation_available
        if notify_weekly_summary is not None:
            settings.notify_weekly_summary = notify_weekly_summary
        
        await self._session.commit()
        await self._session.refresh(settings)
        return settings

    async def acknowledge_model_version(
        self,
        user_id: uuid.UUID,
        model_version: str,
    ) -> UserSettings:
        """Mark a model version as acknowledged by the user.
        
        This is used to stop showing "new model available" notifications
        for a specific version after the user has seen it.
        
        Args:
            user_id: The user ID.
            model_version: The model version to acknowledge.
            
        Returns:
            The updated user settings.
        """
        settings = await self.get_or_create_settings(user_id)
        settings.last_acknowledged_model_version = model_version
        await self._session.commit()
        await self._session.refresh(settings)
        return settings
