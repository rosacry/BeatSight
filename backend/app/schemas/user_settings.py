"""Schemas for user settings."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.user_settings import ReEvaluationPolicy, UploadVisibility


class UserSettingsRead(BaseModel):
    """User settings response schema."""

    id: uuid.UUID
    user_id: uuid.UUID

    # Privacy settings
    default_upload_visibility: UploadVisibility
    show_activity_on_profile: bool
    show_statistics_on_profile: bool
    hide_from_leaderboards: bool
    hide_from_public_queues: bool

    # AI re-evaluation settings
    re_evaluation_policy: ReEvaluationPolicy
    last_acknowledged_model_version: Optional[str]

    # Notification settings
    notify_job_complete: bool
    notify_map_verified: bool
    notify_re_evaluation_available: bool
    notify_weekly_summary: bool

    # Timestamps
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserSettingsUpdate(BaseModel):
    """User settings update request schema.
    
    All fields are optional - only provided fields will be updated.
    """

    # Privacy settings
    default_upload_visibility: Optional[UploadVisibility] = Field(
        default=None,
        description="Default visibility for new uploads (public, anonymous, private)",
    )
    show_activity_on_profile: Optional[bool] = Field(
        default=None,
        description="Show recent activity on public profile",
    )
    show_statistics_on_profile: Optional[bool] = Field(
        default=None,
        description="Show statistics on public profile",
    )
    hide_from_leaderboards: Optional[bool] = Field(
        default=None,
        description="Hide from public leaderboards (anonymous mode)",
    )
    hide_from_public_queues: Optional[bool] = Field(
        default=None,
        description="Hide jobs from public queue view (anonymous mode)",
    )

    # AI re-evaluation settings
    re_evaluation_policy: Optional[ReEvaluationPolicy] = Field(
        default=None,
        description="How to handle AI model upgrades for your maps",
    )

    # Notification settings
    notify_job_complete: Optional[bool] = Field(
        default=None,
        description="Notify when AI job completes",
    )
    notify_map_verified: Optional[bool] = Field(
        default=None,
        description="Notify when map is verified",
    )
    notify_re_evaluation_available: Optional[bool] = Field(
        default=None,
        description="Notify when AI model upgrade is available",
    )
    notify_weekly_summary: Optional[bool] = Field(
        default=None,
        description="Receive weekly activity summary",
    )
