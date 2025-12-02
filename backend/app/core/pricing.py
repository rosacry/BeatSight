"""
BeatSight Pricing Configuration

Centralized pricing and quota configuration for all subscription tiers.
This file is the source of truth for pricing across the platform.

Pricing Strategy (December 2025):
- FREE: 5 songs/month - Hook users, demonstrate value
- BASIC ($8/mo): 30 songs/month - Casual drummers learning songs
- PRO ($15/mo): Unlimited - Serious musicians, teachers, content creators

Revenue Model:
- Target: 5% conversion from free to paid
- Expected ARPU: ~$11/mo (mix of Basic and Pro)
- Gross margin: 85%+ (AI costs ~$0.05/song)
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.subscription import SubscriptionPlan


@dataclass(frozen=True)
class TierConfig:
    """Configuration for a subscription tier."""

    plan: SubscriptionPlan
    name: str
    monthly_quota: int  # -1 = unlimited
    price_monthly_cents: int
    price_yearly_cents: int
    model_tier: str  # v5-tiny, v5-distilled, v5-full
    priority: int  # Processing queue priority (higher = faster)
    features: tuple[str, ...]

    @property
    def price_monthly_dollars(self) -> float:
        return self.price_monthly_cents / 100

    @property
    def price_yearly_dollars(self) -> float:
        return self.price_yearly_cents / 100

    @property
    def yearly_savings_percent(self) -> int:
        if self.price_monthly_cents == 0:
            return 0
        yearly_if_monthly = self.price_monthly_cents * 12
        return int((1 - self.price_yearly_cents / yearly_if_monthly) * 100)

    @property
    def is_unlimited(self) -> bool:
        return self.monthly_quota < 0


# =============================================================================
# TIER DEFINITIONS
# =============================================================================

FREE_TIER = TierConfig(
    plan=SubscriptionPlan.FREE,
    name="Free",
    monthly_quota=5,
    price_monthly_cents=0,
    price_yearly_cents=0,
    model_tier="v5-distilled",  # Good quality, cost-effective
    priority=1,
    features=(
        "5 songs per month",
        "AI drum transcription",
        "Basic playback modes",
        "Community beatmaps",
    ),
)

BASIC_TIER = TierConfig(
    plan=SubscriptionPlan.BASIC_MONTHLY,
    name="Basic",
    monthly_quota=30,
    price_monthly_cents=800,  # $8/month
    price_yearly_cents=6400,  # $64/year (2 months free)
    model_tier="v5-distilled",
    priority=5,
    features=(
        "30 songs per month",
        "AI drum transcription",
        "All playback modes",
        "Technique detection",
        "Priority processing",
        "Offline access",
    ),
)

PRO_TIER = TierConfig(
    plan=SubscriptionPlan.PRO_MONTHLY,
    name="Pro",
    monthly_quota=-1,  # Unlimited
    price_monthly_cents=1500,  # $15/month
    price_yearly_cents=12000,  # $120/year (2 months free)
    model_tier="v5-full",  # Best quality
    priority=10,
    features=(
        "Unlimited songs",
        "AI drum transcription",
        "All playback modes",
        "Full technique detection",
        "Highest priority processing",
        "Offline access",
        "Advanced practice tools",
        "Export to MIDI/MusicXML",
        "Commercial use license",
    ),
)

# Map plans to their configurations
TIER_CONFIGS: dict[SubscriptionPlan, TierConfig] = {
    SubscriptionPlan.FREE: FREE_TIER,
    SubscriptionPlan.BASIC_MONTHLY: BASIC_TIER,
    SubscriptionPlan.BASIC_YEARLY: BASIC_TIER,  # Same features, different billing
    SubscriptionPlan.PRO_MONTHLY: PRO_TIER,
    SubscriptionPlan.PRO_YEARLY: PRO_TIER,
}


def get_tier_config(plan: SubscriptionPlan) -> TierConfig:
    """Get configuration for a subscription plan."""
    return TIER_CONFIGS.get(plan, FREE_TIER)


def get_monthly_quota(plan: SubscriptionPlan) -> int:
    """Get monthly AI job quota for a plan. Returns -1 for unlimited."""
    return get_tier_config(plan).monthly_quota


def get_model_tier(plan: SubscriptionPlan) -> str:
    """Get the AI model tier to use for a plan."""
    return get_tier_config(plan).model_tier


def get_processing_priority(plan: SubscriptionPlan) -> int:
    """Get processing queue priority. Higher = processed first."""
    return get_tier_config(plan).priority


# =============================================================================
# PRICING TABLE (for frontend display)
# =============================================================================


def get_pricing_table() -> dict:
    """
    Get pricing table for frontend display.

    Returns a dict that can be serialized to JSON for the pricing page.
    """
    return {
        "tiers": [
            {
                "id": "free",
                "name": "Free",
                "description": "Get started with AI drum transcription",
                "price_monthly": 0,
                "price_yearly": 0,
                "quota": FREE_TIER.monthly_quota,
                "features": list(FREE_TIER.features),
                "cta": "Get Started",
                "popular": False,
            },
            {
                "id": "basic",
                "name": "Basic",
                "description": "For casual drummers learning songs",
                "price_monthly": BASIC_TIER.price_monthly_dollars,
                "price_yearly": BASIC_TIER.price_yearly_dollars,
                "quota": BASIC_TIER.monthly_quota,
                "features": list(BASIC_TIER.features),
                "cta": "Start Free Trial",
                "popular": True,
                "savings_percent": BASIC_TIER.yearly_savings_percent,
            },
            {
                "id": "pro",
                "name": "Pro",
                "description": "For serious musicians and teachers",
                "price_monthly": PRO_TIER.price_monthly_dollars,
                "price_yearly": PRO_TIER.price_yearly_dollars,
                "quota": "Unlimited",
                "features": list(PRO_TIER.features),
                "cta": "Start Free Trial",
                "popular": False,
                "savings_percent": PRO_TIER.yearly_savings_percent,
            },
        ],
        "currency": "USD",
        "trial_days": 7,
        "annual_discount_months": 2,  # "2 months free" messaging
    }


# =============================================================================
# COST ANALYSIS (internal metrics)
# =============================================================================

# Per-song processing cost on Modal L40S (~$0.005-0.05 depending on model)
COST_PER_SONG_FREE = 0.008  # v5-distilled, lower priority
COST_PER_SONG_BASIC = 0.008  # v5-distilled
COST_PER_SONG_PRO = 0.015  # v5-full, highest quality


def calculate_unit_economics(monthly_songs: int, plan: SubscriptionPlan) -> dict:
    """
    Calculate unit economics for a user.

    Args:
        monthly_songs: Average songs processed per month
        plan: User's subscription plan

    Returns:
        Dict with revenue, cost, and margin metrics
    """
    tier = get_tier_config(plan)
    revenue = tier.price_monthly_cents / 100

    if plan == SubscriptionPlan.FREE:
        cost_per_song = COST_PER_SONG_FREE
    elif plan in (SubscriptionPlan.BASIC_MONTHLY, SubscriptionPlan.BASIC_YEARLY):
        cost_per_song = COST_PER_SONG_BASIC
    else:
        cost_per_song = COST_PER_SONG_PRO

    total_cost = monthly_songs * cost_per_song
    gross_profit = revenue - total_cost
    margin = (gross_profit / revenue * 100) if revenue > 0 else 0

    return {
        "revenue": revenue,
        "ai_cost": total_cost,
        "gross_profit": gross_profit,
        "margin_percent": margin,
        "cost_per_song": cost_per_song,
    }
