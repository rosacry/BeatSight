/**
 * Type-safe API client using openapi-fetch.
 * 
 * Types are generated from the backend OpenAPI spec.
 * Run `npm run api:generate` to update types from running backend.
 * Run `npm run api:generate:file` to update from exported openapi.json.
 * 
 * Usage:
 *   import { api } from '@/api/typedClient'
 *   const { data, error } = await api.GET('/api/songs/{song_id}', { params: { path: { song_id: '123' } } })
 */

import createClient from 'openapi-fetch'
import type { paths } from '@/types/api.generated'
import { getAccessToken, useAuthStore } from '@/stores/authStore'

// Create the typed client
const client = createClient<paths>({
    baseUrl: import.meta.env.VITE_API_BASE_URL || '/api',
})

// Add auth middleware
client.use({
    async onRequest({ request }) {
        const token = getAccessToken()
        if (token) {
            request.headers.set('Authorization', `Bearer ${token}`)
        }
        return request
    },
    async onResponse({ response }) {
        // Handle 401 - trigger token refresh or logout
        if (response.status === 401) {
            const authStore = useAuthStore.getState()
            // Try to refresh token
            try {
                await authStore.refreshTokens()
            } catch {
                // Refresh failed, logout
                authStore.logout()
            }
        }
        return response
    },
})

export { client as api }

// Re-export types for convenience
export type { paths, components } from '@/types/api.generated'
