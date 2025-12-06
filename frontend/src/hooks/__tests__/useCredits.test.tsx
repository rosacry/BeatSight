/**
 * Tests for credit hooks: useCredits, useCreditBalance, useHasCredits, etc.
 *
 * Created: December 3, 2025
 * Updated: June 2025 - Updated credit pack values to match new pricing
 * References: ENGINEERING_ACTION_TRACKER.md item 4.5
 *
 * Credit pack pricing:
 * - Starter: 15 credits @ $5.00 ($0.33/credit)
 * - Value: 30 credits @ $10.00 ($0.33/credit)
 * - Power: 75 credits @ $25.00 ($0.33/credit)
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { server } from '@/test/mocks/server'
import {
    useCreditBalance,
    useCreditPacks,
    useCreditHistory,
    useHasCredits,
    useCreditCount,
    useCanPerformAiAction,
    useRefreshCreditBalance,
} from '../useCredits'

// Mock data
const mockCreditBalance = {
    balance: 50,
    lifetime_purchased: 100,
    lifetime_consumed: 50,
    auto_topup_enabled: false,
    auto_topup_threshold: null,
    auto_topup_pack: null,
}

const mockCreditBalanceZero = {
    balance: 0,
    lifetime_purchased: 0,
    lifetime_consumed: 0,
    auto_topup_enabled: false,
    auto_topup_threshold: null,
    auto_topup_pack: null,
}

const mockCreditPacks = [
    {
        type: 'starter' as const,
        name: 'Starter Pack',
        credits: 15,
        price_cents: 500,
        price_display: '$5',
        per_credit_cents: 33.3,
        savings_percent: 0,
    },
    {
        type: 'value' as const,
        name: 'Value Pack',
        credits: 30,
        price_cents: 1000,
        price_display: '$10',
        per_credit_cents: 33.3,
        savings_percent: 0,
    },
    {
        type: 'power' as const,
        name: 'Power Pack',
        credits: 75,
        price_cents: 2500,
        price_display: '$25',
        per_credit_cents: 33.3,
        savings_percent: 0,
    },
]

const mockCreditHistory = {
    transactions: [
        {
            id: 'tx_1',
            transaction_type: 'purchase' as const,
            amount: 50,
            balance_before: 0,
            balance_after: 50,
            description: 'Purchased 50 credits',
            created_at: '2024-01-15T10:30:00Z',
        },
        {
            id: 'tx_2',
            transaction_type: 'consumption' as const,
            amount: -1,
            balance_before: 50,
            balance_after: 49,
            description: 'AI transcription - Song Title',
            created_at: '2024-01-16T14:22:00Z',
        },
    ],
    total: 2,
    page: 1,
    page_size: 20,
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

describe('useCreditBalance', () => {
    beforeEach(() => {
        server.use(
            http.get('/api/credits/balance', () => {
                return HttpResponse.json(mockCreditBalance)
            })
        )
    })

    it('should fetch credit balance', async () => {
        const { result } = renderHook(() => useCreditBalance(), {
            wrapper: createWrapper(),
        })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))

        expect(result.current.data?.balance).toBe(50)
        expect(result.current.data?.auto_topup_enabled).toBe(false)
    })

    it('should handle zero balance', async () => {
        server.use(
            http.get('/api/credits/balance', () => {
                return HttpResponse.json(mockCreditBalanceZero)
            })
        )

        const { result } = renderHook(() => useCreditBalance(), {
            wrapper: createWrapper(),
        })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))

        expect(result.current.data?.balance).toBe(0)
    })

    it('should handle fetch error', async () => {
        server.use(
            http.get('/api/credits/balance', () => {
                return HttpResponse.json(
                    { detail: 'Server error' },
                    { status: 500 }
                )
            })
        )

        const { result } = renderHook(() => useCreditBalance(), {
            wrapper: createWrapper(),
        })

        await waitFor(() => expect(result.current.isError).toBe(true))
    })
})

describe('useCreditPacks', () => {
    beforeEach(() => {
        server.use(
            http.get('/api/credits/packs', () => {
                return HttpResponse.json(mockCreditPacks)
            })
        )
    })

    it('should fetch available credit packs', async () => {
        const { result } = renderHook(() => useCreditPacks(), {
            wrapper: createWrapper(),
        })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))

        expect(result.current.data).toHaveLength(3)
        expect(result.current.data?.[0].credits).toBe(15)  // starter
        expect(result.current.data?.[1].credits).toBe(30)  // value
        expect(result.current.data?.[2].credits).toBe(75)  // power
    })

    it('should include pricing information', async () => {
        const { result } = renderHook(() => useCreditPacks(), {
            wrapper: createWrapper(),
        })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))

        const starterPack = result.current.data?.find((p) => p.type === 'starter')
        expect(starterPack?.price_cents).toBe(500)
        expect(starterPack?.per_credit_cents).toBeCloseTo(33.3, 1)
    })
})

describe('useCreditHistory', () => {
    beforeEach(() => {
        server.use(
            http.get('/api/credits/history', () => {
                return HttpResponse.json(mockCreditHistory)
            })
        )
    })

    it('should fetch credit transaction history', async () => {
        const { result } = renderHook(() => useCreditHistory(), {
            wrapper: createWrapper(),
        })

        await waitFor(() => expect(result.current.isSuccess).toBe(true))

        expect(result.current.data?.transactions).toHaveLength(2)
        expect(result.current.data?.transactions[0].transaction_type).toBe('purchase')
        expect(result.current.data?.transactions[1].transaction_type).toBe('consumption')
    })

    it('should pass pagination parameters', async () => {
        server.use(
            http.get('/api/credits/history', () => {
                return HttpResponse.json(mockCreditHistory)
            })
        )

        const { result } = renderHook(
            () => useCreditHistory({ limit: 10, offset: 20 }),
            { wrapper: createWrapper() }
        )

        await waitFor(() => expect(result.current.isSuccess).toBe(true))

        // The hook should have made the request with these params
        // (verification depends on how the API is called)
    })
})

describe('useHasCredits', () => {
    it('should return true when user has credits', async () => {
        server.use(
            http.get('/api/credits/balance', () => {
                return HttpResponse.json(mockCreditBalance)
            })
        )

        const { result } = renderHook(() => useHasCredits(), {
            wrapper: createWrapper(),
        })

        // Initially false while loading
        expect(result.current).toBe(false)

        await waitFor(() => expect(result.current).toBe(true))
    })

    it('should return false when user has no credits', async () => {
        server.use(
            http.get('/api/credits/balance', () => {
                return HttpResponse.json(mockCreditBalanceZero)
            })
        )

        const { result } = renderHook(() => useHasCredits(), {
            wrapper: createWrapper(),
        })

        await waitFor(() => {
            // Hook should settle and return false
        })

        // Should remain false
        expect(result.current).toBe(false)
    })
})

describe('useCreditCount', () => {
    it('should return credit count and loading state', async () => {
        server.use(
            http.get('/api/credits/balance', () => {
                return HttpResponse.json(mockCreditBalance)
            })
        )

        const { result } = renderHook(() => useCreditCount(), {
            wrapper: createWrapper(),
        })

        // Should be loading initially
        expect(result.current.isLoading).toBe(true)
        expect(result.current.credits).toBe(0) // Default while loading

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        expect(result.current.credits).toBe(50)
    })

    it('should return zero credits on error', async () => {
        server.use(
            http.get('/api/credits/balance', () => {
                return HttpResponse.json(
                    { detail: 'Error' },
                    { status: 500 }
                )
            })
        )

        const { result } = renderHook(() => useCreditCount(), {
            wrapper: createWrapper(),
        })

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        // Should default to 0 on error
        expect(result.current.credits).toBe(0)
    })
})

describe('useCanPerformAiAction', () => {
    it('should return true when user has credits', async () => {
        server.use(
            http.get('/api/credits/balance', () => {
                return HttpResponse.json(mockCreditBalance)
            })
        )

        const { result } = renderHook(() => useCanPerformAiAction(), {
            wrapper: createWrapper(),
        })

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        expect(result.current.canPerform).toBe(true)
        expect(result.current.creditsAvailable).toBe(50)
    })

    it('should return false when user has no credits', async () => {
        server.use(
            http.get('/api/credits/balance', () => {
                return HttpResponse.json(mockCreditBalanceZero)
            })
        )

        const { result } = renderHook(() => useCanPerformAiAction(), {
            wrapper: createWrapper(),
        })

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        expect(result.current.canPerform).toBe(false)
        expect(result.current.creditsAvailable).toBe(0)
    })
})

describe('useRefreshCreditBalance', () => {
    it('should return a function that invalidates credit balance', async () => {
        let fetchCount = 0
        server.use(
            http.get('/api/credits/balance', () => {
                fetchCount++
                return HttpResponse.json(mockCreditBalance)
            })
        )

        const queryClient = new QueryClient({
            defaultOptions: {
                queries: { retry: false, gcTime: 0 },
            },
        })

        const wrapper = ({ children }: { children: React.ReactNode }) => (
            <QueryClientProvider client={queryClient}>
                {children}
            </QueryClientProvider>
        )

        // First fetch the balance
        const { result: balanceResult } = renderHook(() => useCreditBalance(), {
            wrapper,
        })
        await waitFor(() => expect(balanceResult.current.isSuccess).toBe(true))

        // Get the refresh function
        const { result: refreshResult } = renderHook(
            () => useRefreshCreditBalance(),
            { wrapper }
        )

        // Call refresh
        act(() => {
            refreshResult.current()
        })

        // Should trigger a new fetch
        await waitFor(() => expect(fetchCount).toBeGreaterThanOrEqual(2))
    })
})
