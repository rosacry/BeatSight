/**
 * Auth state management using Zustand.
 * Handles authentication state, token storage, and user session.
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User, TokenResponse, LoginCredentials, RegisterCredentials } from '@/types/auth'
import { API_CONFIG } from '@/lib/config'

const API_BASE = API_CONFIG.baseUrl

/** Margin in seconds before token expiration to trigger refresh */
const TOKEN_REFRESH_MARGIN = 60

interface AuthStore {
    // State
    user: User | null
    accessToken: string | null
    refreshToken: string | null
    isLoading: boolean

    // Computed
    isAuthenticated: () => boolean
    isTokenExpired: () => boolean
    getTokenExpirationTime: () => number | null
    hasRole: (role: string) => boolean
    isAdmin: () => boolean
    isStaff: () => boolean
    isVerifier: () => boolean

    // Actions
    login: (credentials: LoginCredentials) => Promise<void>
    register: (credentials: RegisterCredentials) => Promise<void>
    logout: () => void
    refreshTokens: () => Promise<boolean>
    fetchCurrentUser: () => Promise<void>
    setLoading: (loading: boolean) => void
    initialize: () => Promise<void>
}

export class AuthError extends Error {
    constructor(public status: number, message: string) {
        super(message)
        this.name = 'AuthError'
    }
}

export class TwoFactorRequiredError extends Error {
    constructor() {
        super('Two-factor authentication required')
        this.name = 'TwoFactorRequiredError'
    }
}

/**
 * Parse JWT token and extract payload without verification.
 * Note: This is for client-side expiry checking only, not security.
 */
function parseJwt(token: string): { exp?: number; iat?: number; sub?: string } | null {
    try {
        const parts = token.split('.')
        if (parts.length !== 3) return null
        const payload = parts[1]
        // Handle URL-safe base64
        const base64 = payload.replace(/-/g, '+').replace(/_/g, '/')
        const jsonPayload = decodeURIComponent(
            atob(base64)
                .split('')
                .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
                .join('')
        )
        return JSON.parse(jsonPayload)
    } catch {
        return null
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

    let response: Response
    try {
        response = await fetch(`${API_BASE}${endpoint}`, {
            ...options,
            headers: {
                ...headers,
                ...options.headers,
            },
        })
    } catch (networkError) {
        // Network error - CORS, offline, etc.
        console.error('Network error during auth request:', networkError)
        throw new AuthError(0, 'Unable to connect to server. Please check your internet connection.')
    }

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: `Server error (${response.status})` }))
        throw new AuthError(response.status, error.detail || `Request failed (${response.status})`)
    }

    return response.json()
}

async function loginRequest(credentials: LoginCredentials): Promise<TokenResponse> {
    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
    }

    let response: Response
    try {
        response = await fetch(`${API_BASE}/api/auth/login`, {
            method: 'POST',
            headers,
            body: JSON.stringify(credentials),
        })
    } catch (networkError) {
        console.error('Network error during login request:', networkError)
        throw new AuthError(0, 'Unable to connect to server. Please check your internet connection.')
    }

    // Handle 202 - 2FA required
    if (response.status === 202) {
        throw new TwoFactorRequiredError()
    }

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: `Server error (${response.status})` }))
        throw new AuthError(response.status, error.detail || `Request failed (${response.status})`)
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
                return state.accessToken !== null && state.user !== null && !state.isTokenExpired()
            },

            // Check if the access token is expired or about to expire
            isTokenExpired: () => {
                const state = get()
                if (!state.accessToken) return true

                const payload = parseJwt(state.accessToken)
                if (!payload?.exp) return true

                const now = Math.floor(Date.now() / 1000)
                return payload.exp - TOKEN_REFRESH_MARGIN <= now
            },

            // Get token expiration time in milliseconds
            getTokenExpirationTime: () => {
                const state = get()
                if (!state.accessToken) return null

                const payload = parseJwt(state.accessToken)
                if (!payload?.exp) return null

                return payload.exp * 1000
            },

            // Check if user has a specific role
            hasRole: (role: string) => {
                const state = get()
                if (!state.user?.roles) return false
                return state.user.roles.includes(role)
            },

            // Check if user is admin
            isAdmin: () => {
                return get().hasRole('admin')
            },

            // Check if user is staff (or admin, since admin inherits staff)
            isStaff: () => {
                const state = get()
                return state.hasRole('staff') || state.hasRole('admin')
            },

            // Check if user is verifier (or staff/admin, since they inherit verifier)
            isVerifier: () => {
                const state = get()
                return state.hasRole('verifier') || state.hasRole('staff') || state.hasRole('admin')
            },

            // Initialize auth state on app load
            initialize: async () => {
                const state = get()
                if (!state.accessToken) return

                // Check if token is expired
                if (state.isTokenExpired()) {
                    // Try to refresh
                    const refreshed = await get().refreshTokens()
                    if (!refreshed) {
                        get().logout()
                        return
                    }
                }

                // Fetch user if we have a valid token but no user
                if (!state.user) {
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
                    const tokens = await loginRequest(credentials)

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
                    const tokens = await authRequest<TokenResponse>('/api/auth/register', {
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
                    const tokens = await authRequest<TokenResponse>('/api/auth/refresh', {
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
                    '/api/auth/me',
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

// Helper to check if user is admin
export function isAdmin(): boolean {
    return useAuthStore.getState().isAdmin()
}

// Helper to check if user is staff
export function isStaff(): boolean {
    return useAuthStore.getState().isStaff()
}

// Helper to check if user is verifier
export function isVerifier(): boolean {
    return useAuthStore.getState().isVerifier()
}
