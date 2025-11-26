/**
 * Auth state management using Zustand.
 * Handles authentication state, token storage, and user session.
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User, TokenResponse, LoginCredentials, RegisterCredentials } from '@/types/auth'

const API_BASE = '/api'

interface AuthStore {
    // State
    user: User | null
    accessToken: string | null
    refreshToken: string | null
    isLoading: boolean

    // Computed
    isAuthenticated: () => boolean

    // Actions
    login: (credentials: LoginCredentials) => Promise<void>
    register: (credentials: RegisterCredentials) => Promise<void>
    logout: () => void
    refreshTokens: () => Promise<boolean>
    fetchCurrentUser: () => Promise<void>
    setLoading: (loading: boolean) => void
    initialize: () => Promise<void>
}

class AuthError extends Error {
    constructor(public status: number, message: string) {
        super(message)
        this.name = 'AuthError'
    }
}

async function authRequest<T>(
    endpoint: string,
    options: RequestInit = {},
    token?: string | null
): Promise<T> {
    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
    }

    if (token) {
        headers['Authorization'] = `Bearer ${token}`
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers: {
            ...headers,
            ...options.headers,
        },
    })

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
        throw new AuthError(response.status, error.detail || 'Request failed')
    }

    return response.json()
}

export const useAuthStore = create<AuthStore>()(
    persist(
        (set, get) => ({
            // Initial state
            user: null,
            accessToken: null,
            refreshToken: null,
            isLoading: false,

            // Computed property
            isAuthenticated: () => {
                const state = get()
                return state.accessToken !== null && state.user !== null
            },

            // Initialize auth state on app load
            initialize: async () => {
                const state = get()
                if (state.accessToken && !state.user) {
                    try {
                        await get().fetchCurrentUser()
                    } catch {
                        // Token invalid, clear state
                        get().logout()
                    }
                }
            },

            // Login action
            login: async (credentials: LoginCredentials) => {
                set({ isLoading: true })
                try {
                    const tokens = await authRequest<TokenResponse>('/auth/login', {
                        method: 'POST',
                        body: JSON.stringify(credentials),
                    })

                    set({
                        accessToken: tokens.access_token,
                        refreshToken: tokens.refresh_token,
                    })

                    // Fetch user profile
                    await get().fetchCurrentUser()
                } finally {
                    set({ isLoading: false })
                }
            },

            // Register action
            register: async (credentials: RegisterCredentials) => {
                set({ isLoading: true })
                try {
                    const tokens = await authRequest<TokenResponse>('/auth/register', {
                        method: 'POST',
                        body: JSON.stringify(credentials),
                    })

                    set({
                        accessToken: tokens.access_token,
                        refreshToken: tokens.refresh_token,
                    })

                    // Fetch user profile
                    await get().fetchCurrentUser()
                } finally {
                    set({ isLoading: false })
                }
            },

            // Logout action
            logout: () => {
                set({
                    user: null,
                    accessToken: null,
                    refreshToken: null,
                })
            },

            // Refresh tokens
            refreshTokens: async (): Promise<boolean> => {
                const state = get()
                if (!state.refreshToken) {
                    return false
                }

                try {
                    const tokens = await authRequest<TokenResponse>('/auth/refresh', {
                        method: 'POST',
                        body: JSON.stringify({ refresh_token: state.refreshToken }),
                    })

                    set({
                        accessToken: tokens.access_token,
                        refreshToken: tokens.refresh_token,
                    })

                    return true
                } catch {
                    get().logout()
                    return false
                }
            },

            // Fetch current user
            fetchCurrentUser: async () => {
                const state = get()
                if (!state.accessToken) {
                    throw new AuthError(401, 'No access token')
                }

                const user = await authRequest<User>(
                    '/auth/me',
                    { method: 'GET' },
                    state.accessToken
                )

                set({ user })
            },

            // Set loading state
            setLoading: (loading: boolean) => {
                set({ isLoading: loading })
            },
        }),
        {
            name: 'beatsight-auth',
            // Only persist tokens, not loading state
            partialize: (state) => ({
                accessToken: state.accessToken,
                refreshToken: state.refreshToken,
            }),
        }
    )
)

// Hook to get access token for API requests
export function getAccessToken(): string | null {
    return useAuthStore.getState().accessToken
}

// Helper to check if authenticated
export function isAuthenticated(): boolean {
    return useAuthStore.getState().isAuthenticated()
}
