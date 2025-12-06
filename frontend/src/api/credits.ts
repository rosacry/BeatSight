/**
 * Credits API service for pay-per-use credit system.
 */

import type {
    CreditBalance,
    CreditPack,
    CreditCheckoutResponse,
    CreditTransaction,
    CreditPackType,
    AutoTopupConfig,
} from '@/types/credits'
import { getAccessToken } from '@/stores/authStore'
import { API_CONFIG } from '@/lib/config'

const API_BASE = API_CONFIG.baseUrl

async function creditsRequest<T>(
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

    const response = await fetch(`${API_BASE}/credits${endpoint}`, {
        ...options,
        headers: { ...headers, ...(options.headers as Record<string, string>) },
    })

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Request failed' }))
        throw new Error(error.detail || `HTTP ${response.status}`)
    }

    return response.json()
}

export const creditsApi = {
    /**
     * Get current user's credit balance.
     */
    async getBalance(): Promise<CreditBalance> {
        return creditsRequest<CreditBalance>('/balance')
    },

    /**
     * Get available credit packs for purchase.
     */
    async getPacks(): Promise<CreditPack[]> {
        return creditsRequest<CreditPack[]>('/packs')
    },

    /**
     * Create a checkout session to purchase a credit pack.
     */
    async purchasePack(
        packType: CreditPackType,
        options?: { successUrl?: string; cancelUrl?: string }
    ): Promise<CreditCheckoutResponse> {
        return creditsRequest<CreditCheckoutResponse>('/purchase', {
            method: 'POST',
            body: JSON.stringify({
                pack_type: packType,
                success_url: options?.successUrl,
                cancel_url: options?.cancelUrl,
            }),
        })
    },

    /**
     * Get credit transaction history.
     */
    async getHistory(params?: {
        limit?: number
        offset?: number
    }): Promise<{ transactions: CreditTransaction[]; total: number }> {
        const searchParams = new URLSearchParams()
        if (params?.limit) searchParams.set('limit', params.limit.toString())
        if (params?.offset) searchParams.set('offset', params.offset.toString())

        const query = searchParams.toString()
        return creditsRequest<{ transactions: CreditTransaction[]; total: number }>(
            `/history${query ? `?${query}` : ''}`
        )
    },

    /**
     * Configure auto-topup settings.
     */
    async configureAutoTopup(config: AutoTopupConfig): Promise<CreditBalance> {
        return creditsRequest<CreditBalance>('/auto-topup', {
            method: 'PUT',
            body: JSON.stringify({
                enabled: config.enabled,
                threshold: config.threshold,
                pack_type: config.pack_type,
            }),
        })
    },

    /**
     * Disable auto-topup.
     */
    async disableAutoTopup(): Promise<CreditBalance> {
        return creditsRequest<CreditBalance>('/auto-topup', {
            method: 'PUT',
            body: JSON.stringify({
                enabled: false,
            }),
        })
    },
}
