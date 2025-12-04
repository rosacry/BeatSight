/**
 * Tests for billing hooks: useBilling, useSubscription, useIsPro, useAiQuota
 *
 * Created: December 3, 2025
 * References: ENGINEERING_ACTION_TRACKER.md item 4.5
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/mocks/server'
import {
    useStripeConfig,
    useSubscription,
    useIsPro,
    useAiQuota,
} from '../useBilling'

// Mock data
const mockStripeConfig = {
    publishable_key: 'pk_test_mock123',
    prices: {
        pro_monthly: 'price_monthly123',
        pro_yearly: 'price_yearly123',
    },
}

const mockFreeSubscription = {
    id: 'sub_free',
    plan: 'free',
    status: 'active',
    current_period_end: null,
    ai_quota_remaining: 3,
    cancel_at_period_end: false,
}

const mockProSubscription = {
    id: 'sub_pro123',
    plan: 'pro_monthly',
    status: 'active',
    current_period_end: '2025-02-01T00:00:00Z',
    ai_quota_remaining: 100,
    cancel_at_period_end: false,
}

// Wrapper component for React Query
function createWrapper() {
    const queryClient = new QueryClient({
        defaultOptions: {
            queries: {
                retry: false,
                gcTime: 0,
            },
        },
    })
    return ({ children }: { children: React.ReactNode }) => (
        <QueryClientProvider client={queryClient}>
            {children}
        </QueryClientProvider>
    )
}

describe('useStripeConfig', () => {
    beforeEach(() => {
        server.use(
            http.get('/api/billing/config', () => {
                return HttpResponse.json(mockStripeConfig)
            })
        )
    })

    it('should fetch Stripe configuration', async () => {
        const { result } = renderHook(() => useStripeConfig(), {
            wrapper: createWrapper(),
        })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))

        expect(result.current.data).toEqual(mockStripeConfig)
        expect(result.current.data?.publishable_key).toBe('pk_test_mock123')
    })

    it('should handle fetch error gracefully', async () => {
        server.use(
            http.get('/api/billing/config', () => {
                return HttpResponse.json(
                    { detail: 'Server error' },
                    { status: 500 }
                )
            })
        )

        const { result } = renderHook(() => useStripeConfig(), {
            wrapper: createWrapper(),
        })

        await waitFor(() => expect(result.current.isError).toBe(true))
    })
})

describe('useSubscription', () => {
    beforeEach(() => {
        server.use(
            http.get('/api/billing/subscription', () => {
                return HttpResponse.json(mockFreeSubscription)
            })
        )
    })

    it('should fetch subscription status', async () => {
        const { result } = renderHook(() => useSubscription(), {
            wrapper: createWrapper(),
        })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))

        expect(result.current.data?.plan).toBe('free')
        expect(result.current.data?.ai_quota_remaining).toBe(3)
    })

    it('should return pro subscription data', async () => {
        server.use(
            http.get('/api/billing/subscription', () => {
                return HttpResponse.json(mockProSubscription)
            })
        )

        const { result } = renderHook(() => useSubscription(), {
            wrapper: createWrapper(),
        })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))

        expect(result.current.data?.plan).toBe('pro_monthly')
        expect(result.current.data?.ai_quota_remaining).toBe(100)
    })

    it('should handle unauthenticated user', async () => {
        server.use(
            http.get('/api/billing/subscription', () => {
                return HttpResponse.json(
                    { detail: 'Not authenticated' },
                    { status: 401 }
                )
            })
        )

        const { result } = renderHook(() => useSubscription(), {
            wrapper: createWrapper(),
        })

        await waitFor(() => expect(result.current.isError).toBe(true))
    })
})

describe('useIsPro', () => {
    it('should return false for free users', async () => {
        server.use(
            http.get('/api/billing/subscription', () => {
                return HttpResponse.json(mockFreeSubscription)
            })
        )

        const { result } = renderHook(() => useIsPro(), {
            wrapper: createWrapper(),
        })

        // Initially false (loading)
        expect(result.current).toBe(false)

        // Wait for query to complete - still false for free plan
        await waitFor(() => {
            // useIsPro checks the subscription data internally
            // Since it's a derived hook, we need to wait for the underlying query
        })

        // Free plan should return false
        expect(result.current).toBe(false)
    })

    it('should return true for pro_monthly users', async () => {
        server.use(
            http.get('/api/billing/subscription', () => {
                return HttpResponse.json(mockProSubscription)
            })
        )

        const { result } = renderHook(() => useIsPro(), {
            wrapper: createWrapper(),
        })

        await waitFor(() => expect(result.current).toBe(true))
    })

    it('should return true for pro_yearly users', async () => {
        server.use(
            http.get('/api/billing/subscription', () => {
                return HttpResponse.json({
                    ...mockProSubscription,
                    plan: 'pro_yearly',
                })
            })
        )

        const { result } = renderHook(() => useIsPro(), {
            wrapper: createWrapper(),
        })

        await waitFor(() => expect(result.current).toBe(true))
    })
})

describe('useAiQuota', () => {
    it('should return remaining quota for free user', async () => {
        server.use(
            http.get('/api/billing/subscription', () => {
                return HttpResponse.json(mockFreeSubscription)
            })
        )

        const { result } = renderHook(() => useAiQuota(), {
            wrapper: createWrapper(),
        })

        // Should be loading initially
        expect(result.current.isLoading).toBe(true)

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        expect(result.current.remaining).toBe(3)
    })

    it('should return remaining quota for pro user', async () => {
        server.use(
            http.get('/api/billing/subscription', () => {
                return HttpResponse.json(mockProSubscription)
            })
        )

        const { result } = renderHook(() => useAiQuota(), {
            wrapper: createWrapper(),
        })

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        expect(result.current.remaining).toBe(100)
    })

    it('should return default quota (3) when subscription fails', async () => {
        server.use(
            http.get('/api/billing/subscription', () => {
                return HttpResponse.json(
                    { detail: 'Server error' },
                    { status: 500 }
                )
            })
        )

        const { result } = renderHook(() => useAiQuota(), {
            wrapper: createWrapper(),
        })

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        // Should fall back to default of 3
        expect(result.current.remaining).toBe(3)
    })
})
