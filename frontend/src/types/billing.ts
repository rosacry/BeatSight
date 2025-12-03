/**
 * Stripe and billing type definitions.
 * Must match backend app/models/subscription.py
 */

// Updated to 2-tier model (Free + Pro)
// Basic tier removed - see docs/MONETIZATION_STRATEGY.md
export type SubscriptionPlan = 'free' | 'pro_monthly' | 'pro_yearly'
export type SubscriptionStatus = 'active' | 'past_due' | 'cancelled'

export interface StripeConfig {
    publishable_key: string | null
    is_configured: boolean
}

export interface Subscription {
    plan: SubscriptionPlan
    status: SubscriptionStatus
    ai_quota_remaining: number
    current_period_end: string | null
    is_active: boolean
}

export interface CheckoutResponse {
    session_id: string
    checkout_url: string
}

export interface PortalResponse {
    portal_url: string
}

export interface PricingPlan {
    id: SubscriptionPlan
    name: string
    description: string
    priceMonthly: number
    priceYearly?: number
    monthlyQuota: number | null  // null = check credits
    features: string[]
    highlighted?: boolean
    cta: string
}

// 2-tier pricing: Free (3 songs) + Pro (50 songs @ $12/mo)
// Credits available as universal fallback for all users
export const PRICING_PLANS: PricingPlan[] = [
    {
        id: 'free',
        name: 'Free',
        description: 'Perfect for trying out BeatSight',
        priceMonthly: 0,
        monthlyQuota: 3,
        features: [
            '3 AI beatmap generations/month',
            'V5-Distilled model',
            'Export to .osu format',
            'Community support',
            'Buy credits for extra songs',
        ],
        cta: 'Get Started',
    },
    {
        id: 'pro_monthly',
        name: 'Pro',
        description: 'For serious drummers and creators',
        priceMonthly: 12,
        priceYearly: 8,  // $96/year = $8/month
        monthlyQuota: 50,
        features: [
            '50 AI beatmap generations/month',
            'V5-Full premium model',
            'Priority processing queue',
            'All export formats',
            'Cloud sync across devices',
            'Priority email support',
            'Early access to new features',
            'Buy credits for extra songs',
        ],
        highlighted: true,
        cta: 'Upgrade to Pro',
    },
]

