/**
 * React hooks for credit system management.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { creditsApi } from '@/api/credits'
import type { CreditPackType, AutoTopupConfig } from '@/types/credits'
import { toast } from '@/components/Toast'
import { useAuthStore } from '@/stores/authStore'

/**
 * Hook to fetch current credit balance.
 * Only fetches when user is authenticated to avoid 401 errors.
 */
export function useCreditBalance() {
    const isAuthenticated = useAuthStore((state) => state.isAuthenticated)

    return useQuery({
        queryKey: ['credit-balance'],
        queryFn: () => creditsApi.getBalance(),
        staleTime: 1000 * 60, // 1 minute - balance can change after jobs
        enabled: isAuthenticated, // Only fetch when authenticated
    })
}

/**
 * Hook to fetch available credit packs.
 */
export function useCreditPacks() {
    return useQuery({
        queryKey: ['credit-packs'],
        queryFn: () => creditsApi.getPacks(),
        staleTime: 1000 * 60 * 60, // 1 hour - packs rarely change
    })
}

/**
 * Hook to purchase a credit pack.
 * Opens Stripe checkout for payment.
 */
export function usePurchaseCredits() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: async ({
            packType,
            successUrl,
            cancelUrl,
        }: {
            packType: CreditPackType
            successUrl?: string
            cancelUrl?: string
        }) => {
            const response = await creditsApi.purchasePack(packType, {
                successUrl,
                cancelUrl,
            })
            // Redirect to Stripe checkout
            window.location.href = response.checkout_url
            return response
        },
        onError: (error: Error) => {
            toast.error(`Purchase failed: ${error.message}`)
        },
        onSuccess: () => {
            // Invalidate balance after successful purchase initiation
            queryClient.invalidateQueries({ queryKey: ['credit-balance'] })
        },
    })
}

/**
 * Hook to get credit transaction history.
 */
export function useCreditHistory(params?: { limit?: number; offset?: number }) {
    return useQuery({
        queryKey: ['credit-history', params],
        queryFn: () => creditsApi.getHistory(params),
        staleTime: 1000 * 30, // 30 seconds
    })
}

/**
 * Hook to configure auto-topup.
 */
export function useConfigureAutoTopup() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (config: AutoTopupConfig) => creditsApi.configureAutoTopup(config),
        onSuccess: (newBalance) => {
            queryClient.setQueryData(['credit-balance'], newBalance)
            toast.success(
                newBalance.auto_topup_enabled
                    ? 'Auto-topup enabled successfully'
                    : 'Auto-topup disabled'
            )
        },
        onError: (error: Error) => {
            toast.error(`Failed to update auto-topup: ${error.message}`)
        },
    })
}

/**
 * Hook to disable auto-topup.
 */
export function useDisableAutoTopup() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: () => creditsApi.disableAutoTopup(),
        onSuccess: (newBalance) => {
            queryClient.setQueryData(['credit-balance'], newBalance)
            toast.success('Auto-topup disabled')
        },
        onError: (error: Error) => {
            toast.error(`Failed to disable auto-topup: ${error.message}`)
        },
    })
}

/**
 * Convenience hook for checking credit availability.
 */
export function useHasCredits(): boolean {
    const { data: balance } = useCreditBalance()
    return (balance?.total_credits ?? 0) > 0
}

/**
 * Hook to get credit count for display.
 */
export function useCreditCount(): { credits: number; isLoading: boolean; isError: boolean } {
    const { data: balance, isLoading, isError } = useCreditBalance()
    return {
        credits: balance?.total_credits ?? 0,
        isLoading,
        isError,
    }
}

/**
 * Hook to check if user can perform an action (has quota or credits).
 * Combines subscription quota check with credit balance.
 */
export function useCanPerformAiAction(): {
    canPerform: boolean
    willUseCredit: boolean
    creditsAvailable: number
    isLoading: boolean
} {
    const { data: balance, isLoading: loadingCredits } = useCreditBalance()

    // In a real implementation, you'd also check the quota status
    // For now, we just check if credits are available
    return {
        canPerform: (balance?.total_credits ?? 0) > 0,
        willUseCredit: true, // Simplified - would need quota context
        creditsAvailable: balance?.total_credits ?? 0,
        isLoading: loadingCredits,
    }
}

/**
 * Refresh credit balance.
 * Useful after completing AI jobs.
 */
export function useRefreshCreditBalance() {
    const queryClient = useQueryClient()
    return () => queryClient.invalidateQueries({ queryKey: ['credit-balance'] })
}
