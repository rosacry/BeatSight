/**
 * Billing API service for Stripe integration.
 */

import type {
    StripeConfig,
    Subscription,
    CheckoutResponse,
    PortalResponse,
    SubscriptionPlan
} from '@/types/billing'
import { getAccessToken } from '@/stores/authStore'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

async function billingRequest<T>(
    endpoint: string,
    options: RequestInit = {}
): Promise<T> {
    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
    }

    const token = getAccessToken()
    if (token) {
        headers['Authorization'] = `Bearer ${token}`
    }

    const response = await fetch(`${API_BASE}/api/billing${endpoint}`, {
        ...options,
        headers: { ...headers, ...options.headers as Record<string, string> },
    })

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Request failed' }))
        throw new Error(error.detail || `HTTP ${response.status}`)
    }

    return response.json()
}

export const billingApi = {
    /**
     * Get public Stripe configuration.
     * No auth required.
     */
    async getConfig(): Promise<StripeConfig> {
        return billingRequest<StripeConfig>('/config')
    },

    /**
     * Get current user's subscription status.
     */
    async getSubscription(): Promise<Subscription> {
        return billingRequest<Subscription>('/subscription')
    },

    /**
     * Create a checkout session for upgrading to a plan.
     */
    async createCheckout(plan: SubscriptionPlan): Promise<CheckoutResponse> {
        return billingRequest<CheckoutResponse>('/checkout', {
            method: 'POST',
            body: JSON.stringify({ plan }),
        })
    },

    /**
     * Create a customer portal session for managing subscription.
     */
    async createPortalSession(): Promise<PortalResponse> {
        return billingRequest<PortalResponse>('/portal', {
            method: 'POST',
        })
    },

    /**
     * Redirect to Stripe checkout.
     */
    async redirectToCheckout(plan: SubscriptionPlan): Promise<void> {
        const { checkout_url } = await this.createCheckout(plan)
        window.location.href = checkout_url
    },

    /**
     * Redirect to Stripe customer portal.
     */
    async redirectToPortal(): Promise<void> {
        const { portal_url } = await this.createPortalSession()
        window.location.href = portal_url
    },
}
