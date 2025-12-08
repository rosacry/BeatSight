/**
 * Authentication-related types.
 */

export interface User {
    id: string
    email: string
    display_name: string
    email_verified: boolean
    phone_number: string | null
    phone_verified: boolean
    avatar_url: string | null
    karma_score: number
    created_at: string
    roles: string[]
}

export type UserRole = 'user' | 'verifier' | 'staff' | 'admin'

export interface TokenResponse {
    access_token: string
    refresh_token: string
    token_type: string
}

export interface TwoFactorRequiredResponse {
    requires_2fa: boolean
    message: string
}

export interface LoginCredentials {
    email: string
    password: string
    totp_code?: string
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
