"""
BeatSight Pricing Configuration

Centralized pricing and quota configuration for all subscription tiers.
This file is the source of truth for pricing across the platform.

Pricing Strategy (December 2025) - Simplified 2-Tier + Credits:
- FREE: 3 songs/month - Just enough to experience value
- PRO ($12/mo): 50 songs/month - Covers 99% of drummers
- CREDITS: $0.35/song - Universal fallback for everyone

Why no Basic tier:
- Simplifies pricing page (2 choices vs 3)
- Eliminates "stuck in the middle" frustration
- Credits fill the gap for casual users who don't want Pro

Revenue Model:
- Target: 12% conversion from free to paid
- Expected ARPU: ~$12.50/mo (Pro + credit upsells)
- Gross margin: 95%+ (AI costs ~$0.008/song on Modal L40S)
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.subscription import SubscriptionPlan


@dataclass(frozen=True)
class TierConfig:
    """Configuration for a subscription tier."""

    plan: SubscriptionPlan
    name: str
    monthly_quota: int  # -1 = unlimited, positive = capped
    price_monthly_cents: int
    price_yearly_cents: int
    model_tier: str  # v5-distilled or v5-full
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
# TIER DEFINITIONS (Simplified: Free + Pro only)
# =============================================================================

FREE_TIER = TierConfig(
    plan=SubscriptionPlan.FREE,
    name="Free",
    monthly_quota=3,  # Reduced from 5 to encourage upgrades
    price_monthly_cents=0,
    price_yearly_cents=0,
    model_tier="v5-distilled",  # Good quality, cost-effective
    priority=1,
    features=(
        "3 AI transcriptions per month",
        "V5 Distilled model quality",
        "Basic playback modes",
        "Community beatmaps",
        "Buy credits anytime",
    ),
)

# Note: Basic tier removed - credits fill this gap for casual users
# Legacy BASIC_MONTHLY/YEARLY plans will map to PRO for existing subscribers

PRO_TIER = TierConfig(
    plan=SubscriptionPlan.PRO_MONTHLY,
    name="Pro",
    monthly_quota=50,  # Changed from unlimited - 50 covers 99% of users
    price_monthly_cents=1200,  # $12/month (was $15)
    price_yearly_cents=9600,  # $96/year = $8/mo (2 months free)
    model_tier="v5-full",  # Best quality
    priority=10,
    features=(
        "50 AI transcriptions per month",
        "V5 Full model (highest accuracy)",
        "Priority processing queue",
        "All playback modes",
        "Full technique detection",
        "Advanced practice tools",
        "Export to MIDI/MusicXML",
        "Buy credits if you need more",
    ),
)

# Map plans to their configurations
# Legacy BASIC plans map to PRO for backwards compatibility
TIER_CONFIGS: dict[SubscriptionPlan, TierConfig] = {
    SubscriptionPlan.FREE: FREE_TIER,
    SubscriptionPlan.BASIC_MONTHLY: PRO_TIER,  # Legacy: map to Pro
    SubscriptionPlan.BASIC_YEARLY: PRO_TIER,   # Legacy: map to Pro
    SubscriptionPlan.PRO_MONTHLY: PRO_TIER,
    SubscriptionPlan.PRO_YEARLY: PRO_TIER,
}


def get_tier_config(plan: SubscriptionPlan) -> TierConfig:
    """Get configuration for a subscription plan."""
    return TIER_CONFIGS.get(plan, FREE_TIER)


def get_monthly_quota(plan: SubscriptionPlan) -> int:
    """Get monthly AI job quota for a plan."""
    return get_tier_config(plan).monthly_quota


def get_model_tier(plan: SubscriptionPlan) -> str:
    """Get the AI model tier to use for a plan."""
    return get_tier_config(plan).model_tier


def get_processing_priority(plan: SubscriptionPlan) -> int:
    """Get processing queue priority. Higher = processed first."""
    return get_tier_config(plan).priority


# =============================================================================
# CREDIT PACKS (for pay-per-use)
# =============================================================================

CREDIT_PACK_STARTER = {
    "id": "starter",
    "name": "Starter Pack",
    "credits": 5,
    "price_cents": 175,
    "per_credit_cents": 35,
}

CREDIT_PACK_VALUE = {
    "id": "value",
    "name": "Value Pack",
    "credits": 15,
    "price_cents": 450,
    "per_credit_cents": 30,
    "savings_percent": 14,
}

CREDIT_PACK_POWER = {
    "id": "power",
    "name": "Power Pack",
    "credits": 40,
    "price_cents": 1000,
    "per_credit_cents": 25,
    "savings_percent": 29,
}

CREDIT_PACKS = [CREDIT_PACK_STARTER, CREDIT_PACK_VALUE, CREDIT_PACK_POWER]


# =============================================================================
# PRICING TABLE (for frontend display)
# =============================================================================


def get_pricing_table() -> dict:
    """
    Get pricing table for frontend display.

    Returns a dict that can be serialized to JSON for the pricing page.
    Simplified to 2 tiers: Free and Pro (no Basic tier).
    """
    return {
        "tiers": [
            {
                "id": "free",
                "name": "Free",
                "description": "Try BeatSight with 3 songs per month",
                "price_monthly": 0,
                "price_yearly": 0,
                "quota": FREE_TIER.monthly_quota,
                "features": list(FREE_TIER.features),
                "cta": "Get Started",
                "popular": False,
            },
            {
                "id": "pro",
                "name": "Pro",
                "description": "For drummers who practice regularly",
                "price_monthly": PRO_TIER.price_monthly_dollars,
                "price_yearly": PRO_TIER.price_yearly_dollars,
                "quota": PRO_TIER.monthly_quota,
                "features": list(PRO_TIER.features),
                "cta": "Go Pro",
                "popular": True,
                "savings_percent": PRO_TIER.yearly_savings_percent,
            },
        ],
        "credit_packs": CREDIT_PACKS,
        "currency": "USD",
        "trial_days": 7,
        "annual_discount_months": 2,  # "2 months free" messaging
    }


# =============================================================================
# COST ANALYSIS (internal metrics)
# =============================================================================

# Per-song processing cost on Modal L40S with FP8+Sparse
COST_PER_SONG_FREE = 0.008  # v5-distilled
COST_PER_SONG_PRO = 0.008   # v5-full (same cost, optimized)
COST_PER_CREDIT = 0.008     # Credits use v5-full


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

    cost_per_song = COST_PER_SONG_PRO if plan != SubscriptionPlan.FREE else COST_PER_SONG_FREE

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
