/**
 * Simple API client utility for unauthenticated endpoints.
 * 
 * Re-exports APIError from the main client for consistency.
 * Use this module for simple unauthenticated requests like password reset.
 * For authenticated API calls, use '@/api/client' directly.
 */

// Re-export shared types from main client
export { APIError } from '@/api/client'

const API_BASE = '/api'

/**
 * Simple API client for unauthenticated endpoints.
 * Does not require or send authentication tokens.
 */
export const api = {
    /**
     * Make an unauthenticated POST request.
     */
    async post<T = unknown>(endpoint: string, data: Record<string, unknown>): Promise<T> {
        const { APIError } = await import('@/api/client')

        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        })

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
            throw new APIError(response.status, error.detail || 'Request failed')
        }

        return response.json()
    },

    /**
     * Make an unauthenticated GET request.
     */
    async get<T = unknown>(endpoint: string): Promise<T> {
        const { APIError } = await import('@/api/client')

        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
        })

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
            throw new APIError(response.status, error.detail || 'Request failed')
        }

        return response.json()
    },
}
