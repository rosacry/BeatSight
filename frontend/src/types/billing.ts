/**
 * Stripe and billing type definitions.
 * Must match backend app/models/subscription.py
 */

export type SubscriptionPlan = 'free' | 'basic_monthly' | 'basic_yearly' | 'pro_monthly' | 'pro_yearly'
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
    features: string[]
    highlighted?: boolean
    cta: string
}

export const PRICING_PLANS: PricingPlan[] = [
    {
        id: 'free',
        name: 'Free',
        description: 'Perfect for trying out BeatSight',
        priceMonthly: 0,
        features: [
            '5 AI beatmap generations/month',
            'Basic drum detection',
            'Export to .osu format',
            'Community support',
        ],
        cta: 'Get Started',
    },
    {
        id: 'basic_monthly',
        name: 'Basic',
        description: 'For casual drummers',
        priceMonthly: 8,
        priceYearly: 6,
        features: [
            '30 AI beatmap generations/month',
            'Advanced drum detection',
            'All export formats',
            'Email support',
        ],
        cta: 'Upgrade to Basic',
    },
    {
        id: 'pro_monthly',
        name: 'Pro',
        description: 'For serious drummers and creators',
        priceMonthly: 15,
        priceYearly: 12,
        features: [
            'Unlimited AI beatmap generations',
            'Advanced 19-class drum detection',
            'Priority processing queue',
            'All export formats',
            'Cloud sync across devices',
            'Priority email support',
            'Early access to new features',
        ],
        highlighted: true,
        cta: 'Upgrade to Pro',
    },
]
