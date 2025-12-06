"""
Feature Flags API Endpoint

Server-side feature flag management with user targeting
and gradual rollout support.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query, Depends
from pydantic import BaseModel, Field

from app.auth.dependencies import get_optional_current_user
from app.models.user import User

router = APIRouter(prefix="/feature-flags", tags=["Feature Flags"])


# ============================================================================
# Models
# ============================================================================


class FeatureFlag(BaseModel):
    """A feature flag configuration."""

    key: str
    enabled: bool
    variant: str | None = None
    payload: dict[str, Any] | None = None


class FeatureFlagResponse(BaseModel):
    """Response containing all feature flags."""

    flags: list[FeatureFlag]
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# Feature Flag Definitions
# ============================================================================


class FeatureFlagDefinition:
    """Definition for a feature flag with targeting rules."""

    def __init__(
        self,
        key: str,
        default_enabled: bool = False,
        description: str = "",
        variants: list[str] | None = None,
        rollout_percentage: float = 100.0,
        allowed_plans: list[str] | None = None,
        allowed_user_ids: list[str] | None = None,
        payload: dict[str, Any] | None = None,
    ):
        self.key = key
        self.default_enabled = default_enabled
        self.description = description
        self.variants = variants or []
        self.rollout_percentage = rollout_percentage
        self.allowed_plans = allowed_plans
        self.allowed_user_ids = allowed_user_ids
        self.payload = payload

    def is_enabled_for_user(
        self,
        user_id: str | None = None,
        plan: str | None = None,
    ) -> bool:
        """Check if flag is enabled for a specific user."""
        if not self.default_enabled:
            return False

        # Check allowed user IDs (always allow listed users)
        if self.allowed_user_ids and user_id in self.allowed_user_ids:
            return True

        # Check plan restrictions
        if self.allowed_plans and plan:
            if plan not in self.allowed_plans:
                return False

        # Gradual rollout based on user ID hash
        if self.rollout_percentage < 100.0 and user_id:
            hash_value = int(
                hashlib.md5(f"{self.key}:{user_id}".encode()).hexdigest(), 16
            )
            bucket = (hash_value % 100) + 1
            if bucket > self.rollout_percentage:
                return False

        return True

    def get_variant_for_user(self, user_id: str | None = None) -> str | None:
        """Get the variant assigned to a user (for A/B testing)."""
        if not self.variants:
            return None

        if not user_id:
            return self.variants[0]

        # Consistent variant assignment based on user ID
        hash_value = int(
            hashlib.md5(f"{self.key}:variant:{user_id}".encode()).hexdigest(), 16
        )
        variant_index = hash_value % len(self.variants)
        return self.variants[variant_index]


# ============================================================================
# Flag Registry
# ============================================================================

# Define all feature flags here
FLAG_DEFINITIONS: dict[str, FeatureFlagDefinition] = {
    "new_dashboard": FeatureFlagDefinition(
        key="new_dashboard",
        default_enabled=False,
        description="New analytics dashboard UI",
        rollout_percentage=10.0,  # 10% rollout
    ),
    "ai_suggestions": FeatureFlagDefinition(
        key="ai_suggestions",
        default_enabled=True,
        description="AI-powered beatmap suggestions",
        allowed_plans=["pro", "enterprise"],
    ),
    "social_features": FeatureFlagDefinition(
        key="social_features",
        default_enabled=False,
        description="Social features like following and activity feed",
        rollout_percentage=25.0,
    ),
    "advanced_editor": FeatureFlagDefinition(
        key="advanced_editor",
        default_enabled=True,
        description="Advanced beatmap editor with automation lanes",
        variants=["basic", "advanced", "pro"],
        allowed_plans=["pro", "enterprise"],
    ),
    "dark_mode_v2": FeatureFlagDefinition(
        key="dark_mode_v2",
        default_enabled=True,
        description="New dark mode color scheme",
        rollout_percentage=50.0,
    ),
    "credits_system": FeatureFlagDefinition(
        key="credits_system",
        default_enabled=True,
        description="Credits-based transcription system",
    ),
    "bulk_upload": FeatureFlagDefinition(
        key="bulk_upload",
        default_enabled=False,
        description="Bulk song upload feature",
        allowed_plans=["pro", "enterprise"],
    ),
    "realtime_collaboration": FeatureFlagDefinition(
        key="realtime_collaboration",
        default_enabled=False,
        description="Real-time collaborative editing",
        allowed_plans=["enterprise"],
        rollout_percentage=0.0,  # Not yet released
    ),
    "beta_features": FeatureFlagDefinition(
        key="beta_features",
        default_enabled=False,
        description="Access to beta features",
        # Specific users can be added here for beta testing
        allowed_user_ids=[],
    ),
}


# ============================================================================
# Endpoints
# ============================================================================


@router.get("", response_model=FeatureFlagResponse)
async def get_feature_flags(
    user_id: str | None = Query(None, description="User ID for targeting"),
    plan: str | None = Query(None, description="User's subscription plan"),
    current_user: User | None = Depends(get_optional_current_user),
) -> FeatureFlagResponse:
    """
    Get all feature flags evaluated for the current context.

    Flags are evaluated based on:
    - User ID (for gradual rollouts)
    - Subscription plan (for plan-specific features)
    - Allowed user lists (for beta testing)
    """
    # Use authenticated user if available
    if current_user:
        user_id = str(current_user.id)
        plan = (
            current_user.subscription_tier
            if hasattr(current_user, "subscription_tier")
            else plan
        )

    flags: list[FeatureFlag] = []

    for definition in FLAG_DEFINITIONS.values():
        enabled = definition.is_enabled_for_user(user_id, plan)
        variant = definition.get_variant_for_user(user_id) if enabled else None

        flags.append(
            FeatureFlag(
                key=definition.key,
                enabled=enabled,
                variant=variant,
                payload=definition.payload if enabled else None,
            )
        )

    return FeatureFlagResponse(flags=flags)


@router.get("/{flag_key}")
async def get_feature_flag(
    flag_key: str,
    user_id: str | None = Query(None),
    plan: str | None = Query(None),
    current_user: User | None = Depends(get_optional_current_user),
) -> FeatureFlag:
    """Get a single feature flag by key."""
    if flag_key not in FLAG_DEFINITIONS:
        return FeatureFlag(key=flag_key, enabled=False)

    # Use authenticated user if available
    if current_user:
        user_id = str(current_user.id)
        plan = (
            current_user.subscription_tier
            if hasattr(current_user, "subscription_tier")
            else plan
        )

    definition = FLAG_DEFINITIONS[flag_key]
    enabled = definition.is_enabled_for_user(user_id, plan)
    variant = definition.get_variant_for_user(user_id) if enabled else None

    return FeatureFlag(
        key=definition.key,
        enabled=enabled,
        variant=variant,
        payload=definition.payload if enabled else None,
    )
