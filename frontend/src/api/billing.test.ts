/**
 * Tests for Billing API
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { billingApi } from './billing'

// Mock the config module
vi.mock('@/lib/config', () => ({
    API_CONFIG: {
        baseUrl: 'https://api.test.com'
    }
}))

// Mock the auth store
vi.mock('@/stores/authStore', () => ({
    getAccessToken: vi.fn(() => 'test-token')
}))

describe('billingApi', () => {
    const mockFetch = vi.fn()

    beforeEach(() => {
        global.fetch = mockFetch
        mockFetch.mockClear()
    })

    afterEach(() => {
        vi.restoreAllMocks()
    })

    describe('getConfig', () => {
        it('fetches stripe config from correct endpoint', async () => {
            const mockConfig = { publishableKey: 'pk_test_123' }
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(mockConfig)
            })

            const result = await billingApi.getConfig()

            expect(mockFetch).toHaveBeenCalledWith(
                'https://api.test.com/api/billing/config',
                expect.objectContaining({
                    headers: expect.objectContaining({
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer test-token'
                    })
                })
            )
            expect(result).toEqual(mockConfig)
        })
    })

    describe('getSubscription', () => {
        it('fetches subscription from correct endpoint', async () => {
            const mockSubscription = { id: 'sub_123', status: 'active' }
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(mockSubscription)
            })

            const result = await billingApi.getSubscription()

            expect(mockFetch).toHaveBeenCalledWith(
                'https://api.test.com/api/billing/subscription',
                expect.objectContaining({
                    headers: expect.objectContaining({
                        'Authorization': 'Bearer test-token'
                    })
                })
            )
            expect(result).toEqual(mockSubscription)
        })
    })

    describe('createCheckout', () => {
        it('posts to checkout endpoint with plan', async () => {
            const mockResponse = { checkout_url: 'https://checkout.stripe.com/123' }
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(mockResponse)
            })

            const result = await billingApi.createCheckout('pro')

            expect(mockFetch).toHaveBeenCalledWith(
                'https://api.test.com/api/billing/checkout',
                expect.objectContaining({
                    method: 'POST',
                    body: JSON.stringify({ plan: 'pro' })
                })
            )
            expect(result).toEqual(mockResponse)
        })
    })

    describe('createPortalSession', () => {
        it('posts to portal endpoint', async () => {
            const mockResponse = { portal_url: 'https://billing.stripe.com/portal/123' }
            mockFetch.mockResolvedValueOnce({
                ok: true,
                json: () => Promise.resolve(mockResponse)
            })

            const result = await billingApi.createPortalSession()

            expect(mockFetch).toHaveBeenCalledWith(
                'https://api.test.com/api/billing/portal',
                expect.objectContaining({
                    method: 'POST'
                })
            )
            expect(result).toEqual(mockResponse)
        })
    })

    describe('error handling', () => {
        it('throws error on non-ok response', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 401,
                json: () => Promise.resolve({ detail: 'Unauthorized' })
            })

            await expect(billingApi.getConfig()).rejects.toThrow('Unauthorized')
        })

        it('throws generic error when response body cannot be parsed', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 500,
                json: () => Promise.reject(new Error('Parse error'))
            })

            await expect(billingApi.getConfig()).rejects.toThrow('Request failed')
        })

        it('handles HTTP status in error message', async () => {
            mockFetch.mockResolvedValueOnce({
                ok: false,
                status: 404,
                json: () => Promise.resolve({})
            })

            await expect(billingApi.getConfig()).rejects.toThrow('HTTP 404')
        })
    })
})
