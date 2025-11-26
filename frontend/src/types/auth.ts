/**
 * Authentication-related types.
 */

export interface User {
    id: string
    email: string
    display_name: string
    email_verified: boolean
    karma_score: number
    created_at: string
}

export interface TokenResponse {
    access_token: string
    refresh_token: string
    token_type: string
}

export interface LoginCredentials {
    email: string
    password: string
}

export interface RegisterCredentials {
    email: string
    password: string
    display_name: string
}

export interface AuthState {
    user: User | null
    accessToken: string | null
    refreshToken: string | null
    isLoading: boolean
    isAuthenticated: boolean
}
