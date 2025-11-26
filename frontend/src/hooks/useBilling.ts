/**
 * React hooks for billing and subscription management.
 */

import { useQuery, useMutation } from '@tanstack/react-query'
import { billingApi } from '@/api/billing'
import type { SubscriptionPlan } from '@/types/billing'
import { toast } from '@/components/Toast'

/**
 * Hook to fetch Stripe configuration.
 */
export function useStripeConfig() {
    return useQuery({
        queryKey: ['stripe-config'],
        queryFn: () => billingApi.getConfig(),
        staleTime: 1000 * 60 * 60, // 1 hour - config rarely changes
    })
}

/**
 * Hook to fetch current subscription status.
 */
export function useSubscription() {
    return useQuery({
        queryKey: ['subscription'],
        queryFn: () => billingApi.getSubscription(),
        staleTime: 1000 * 60 * 5, // 5 minutes
    })
}

/**
 * Hook to upgrade subscription.
 */
export function useUpgradeSubscription() {
    return useMutation({
        mutationFn: async (plan: SubscriptionPlan) => {
            await billingApi.redirectToCheckout(plan)
        },
        onError: (error) => {
            toast.error(`Upgrade failed: ${error.message}`)
        },
    })
}

/**
 * Hook to open customer portal.
 */
export function useManageSubscription() {
    return useMutation({
        mutationFn: async () => {
            await billingApi.redirectToPortal()
        },
        onError: (error) => {
            toast.error(`Failed to open billing portal: ${error.message}`)
        },
    })
}

/**
 * Hook to check if user has Pro subscription.
 */
export function useIsPro(): boolean {
    const { data: subscription } = useSubscription()
    return subscription?.plan === 'pro_monthly' || subscription?.plan === 'pro_yearly'
}

/**
 * Hook to get remaining AI quota.
 */
export function useAiQuota(): { remaining: number; isLoading: boolean } {
    const { data: subscription, isLoading } = useSubscription()
    return {
        remaining: subscription?.ai_quota_remaining ?? 3,
        isLoading,
    }
}
