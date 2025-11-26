"""Quota service for managing user AI generation limits.

Handles:
- Subscription plan quota definitions
- Usage tracking per billing period
- Quota enforcement and remaining checks
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis import get_redis, get_quota_usage, increment_quota_usage
from app.models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus


class QuotaExceededError(Exception):
    """Raised when user has exceeded their AI generation quota."""
    
    def __init__(self, limit: int, used: int, resets_at: datetime | None = None):
        self.limit = limit
        self.used = used
        self.resets_at = resets_at
        super().__init__(f"Quota exceeded: {used}/{limit} jobs used")


class JobPriority(IntEnum):
    """Job priority levels based on subscription tier."""
    LOW = 1       # Anonymous users
    STANDARD = 5  # Free tier
    HIGH = 10     # Pro tier


@dataclass
class QuotaLimits:
    """Quota limits for a subscription plan."""
    jobs_per_month: int
    jobs_per_day: int
    max_concurrent: int
    priority: JobPriority
    
    @classmethod
    def for_plan(cls, plan: SubscriptionPlan) -> "QuotaLimits":
        """Get quota limits for a subscription plan."""
        match plan:
            case SubscriptionPlan.FREE:
                return cls(
                    jobs_per_month=10,
                    jobs_per_day=3,
                    max_concurrent=1,
                    priority=JobPriority.STANDARD,
                )
            case SubscriptionPlan.PRO_MONTHLY | SubscriptionPlan.PRO_YEARLY:
                return cls(
                    jobs_per_month=100,
                    jobs_per_day=20,
                    max_concurrent=3,
                    priority=JobPriority.HIGH,
                )
            case _:
                # Default to free tier limits
                return cls(
                    jobs_per_month=10,
                    jobs_per_day=3,
                    max_concurrent=1,
                    priority=JobPriority.STANDARD,
                )
    
    @classmethod
    def anonymous(cls) -> "QuotaLimits":
        """Get quota limits for anonymous (unauthenticated) users."""
        return cls(
            jobs_per_month=3,
            jobs_per_day=1,
            max_concurrent=1,
            priority=JobPriority.LOW,
        )


@dataclass
class QuotaStatus:
    """Current quota status for a user."""
    plan: SubscriptionPlan | None
    limits: QuotaLimits
    used_this_month: int
    used_today: int
    remaining_month: int
    remaining_today: int
    resets_at: datetime | None
    
    @property
    def can_enqueue(self) -> bool:
        """Check if user can enqueue a new job."""
        return self.remaining_month > 0 and self.remaining_today > 0


class QuotaService:
    """Service for checking and managing AI generation quotas."""
    
    def __init__(self, session: AsyncSession):
        self._session = session
    
    async def get_user_subscription(self, user_id: uuid.UUID) -> Subscription | None:
        """Get active subscription for a user."""
        result = await self._session.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .where(Subscription.status == SubscriptionStatus.ACTIVE)
            .order_by(Subscription.current_period_end.desc())
        )
        return result.scalar_one_or_none()
    
    async def get_quota_status(self, user_id: uuid.UUID | None) -> QuotaStatus:
        """Get current quota status for a user."""
        now = datetime.now(timezone.utc)
        month_key = now.strftime("%Y-%m")
        day_key = now.strftime("%Y-%m-%d")
        
        # Anonymous users
        if user_id is None:
            limits = QuotaLimits.anonymous()
            return QuotaStatus(
                plan=None,
                limits=limits,
                used_this_month=0,
                used_today=0,
                remaining_month=limits.jobs_per_month,
                remaining_today=limits.jobs_per_day,
                resets_at=None,
            )
        
        # Get subscription
        subscription = await self.get_user_subscription(user_id)
        plan = subscription.plan_code if subscription else SubscriptionPlan.FREE
        limits = QuotaLimits.for_plan(plan)
        
        # Get usage from Redis
        redis = await get_redis()
        used_month = await get_quota_usage(redis, user_id, month_key)
        used_day = await get_quota_usage(redis, user_id, day_key)
        
        # Calculate resets_at (end of current billing period or end of month for free)
        if subscription:
            resets_at = subscription.current_period_end
        else:
            # Free tier resets at end of month
            if now.month == 12:
                resets_at = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
            else:
                resets_at = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
        
        return QuotaStatus(
            plan=plan,
            limits=limits,
            used_this_month=used_month,
            used_today=used_day,
            remaining_month=max(0, limits.jobs_per_month - used_month),
            remaining_today=max(0, limits.jobs_per_day - used_day),
            resets_at=resets_at,
        )
    
    async def check_quota(self, user_id: uuid.UUID | None) -> QuotaStatus:
        """Check if user can enqueue a job. Raises QuotaExceededError if not."""
        status = await self.get_quota_status(user_id)
        
        if not status.can_enqueue:
            raise QuotaExceededError(
                limit=status.limits.jobs_per_month,
                used=status.used_this_month,
                resets_at=status.resets_at,
            )
        
        return status
    
    async def consume_quota(self, user_id: uuid.UUID) -> QuotaStatus:
        """Consume one quota unit for a user. Call after successfully enqueuing a job."""
        now = datetime.now(timezone.utc)
        month_key = now.strftime("%Y-%m")
        day_key = now.strftime("%Y-%m-%d")
        
        redis = await get_redis()
        
        # Increment both monthly and daily counters
        await increment_quota_usage(redis, user_id, month_key, ttl_seconds=2678400)  # ~31 days
        await increment_quota_usage(redis, user_id, day_key, ttl_seconds=86400)  # 24 hours
        
        return await self.get_quota_status(user_id)
    
    async def get_priority(self, user_id: uuid.UUID | None) -> JobPriority:
        """Get job priority based on user's subscription."""
        if user_id is None:
            return JobPriority.LOW
        
        subscription = await self.get_user_subscription(user_id)
        plan = subscription.plan_code if subscription else SubscriptionPlan.FREE
        limits = QuotaLimits.for_plan(plan)
        return limits.priority
