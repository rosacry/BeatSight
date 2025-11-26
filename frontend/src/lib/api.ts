/**
 * Simple API client utility.
 * Used for unauthenticated endpoints like password reset.
 */

const API_BASE = '/api'

class APIError extends Error {
    constructor(public status: number, message: string) {
        super(message)
        this.name = 'APIError'
    }
}

export const api = {
    async post<T = unknown>(endpoint: string, data: Record<string, unknown>): Promise<T> {
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

    async get<T = unknown>(endpoint: string): Promise<T> {
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
