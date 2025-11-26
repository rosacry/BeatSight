/**
 * Stripe and billing type definitions.
 */

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
            '3 AI beatmap generations/month',
            'Basic drum detection',
            'Export to .osu format',
            'Community support',
        ],
        cta: 'Get Started',
    },
    {
        id: 'pro_monthly',
        name: 'Pro',
        description: 'For serious drummers and creators',
        priceMonthly: 9.99,
        priceYearly: 7.99,
        features: [
            '100 AI beatmap generations/month',
            'Advanced 19-class drum detection',
            'Priority processing queue',
            'All export formats',
            'Cloud sync across devices',
            'Email support',
            'Early access to new features',
        ],
        highlighted: true,
        cta: 'Upgrade to Pro',
    },
]
