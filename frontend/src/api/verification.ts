/**
 * Session verification API client.
 * 
 * Implements osu!-style sensitive action verification where users must
 * verify their identity via email code or link before accessing settings,
 * credits, and other sensitive areas.
 */

import { getAccessToken } from '@/stores/authStore'
import { API_CONFIG } from '@/lib/config'

const API_BASE = API_CONFIG.baseUrl

// Types
export interface VerificationStatusResponse {
    is_verified: boolean
    requires_verification: boolean
    message: string | null
}

export interface VerificationInitiateResponse {
    success: boolean
    obscured_email: string
    message: string
}

export interface VerificationCodeResponse {
    success: boolean
    message: string | null
}

export interface ReissueCodeResponse {
    success: boolean
    message: string
}

class VerificationAPIError extends Error {
    constructor(public status: number, message: string) {
        super(message)
        this.name = 'VerificationAPIError'
    }
}

async function verifyRequest<T>(
    endpoint: string,
    options: RequestInit = {}
): Promise<T> {
    const url = `${API_BASE}/api/verify${endpoint}`

    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
    }

    const token = getAccessToken()
    if (token) {
        headers['Authorization'] = `Bearer ${token}`
    }

    const response = await fetch(url, {
        ...options,
        headers: {
            ...headers,
            ...options.headers,
        },
    })

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
        throw new VerificationAPIError(response.status, error.detail || 'Request failed')
    }

    return response.json()
}

/**
 * Check if the current session is verified for sensitive actions.
 */
export async function getVerificationStatus(): Promise<VerificationStatusResponse> {
    return verifyRequest<VerificationStatusResponse>('/status')
}

/**
 * Initiate verification by sending a code to the user's email.
 */
export async function initiateVerification(): Promise<VerificationInitiateResponse> {
    return verifyRequest<VerificationInitiateResponse>('/initiate', {
        method: 'POST',
    })
}

/**
 * Verify using the code from the email.
 */
export async function verifyWithCode(verificationCode: string): Promise<VerificationCodeResponse> {
    return verifyRequest<VerificationCodeResponse>('/code', {
        method: 'POST',
        body: JSON.stringify({ verification_code: verificationCode }),
    })
}

/**
 * Request a new verification code.
 */
export async function reissueVerificationCode(): Promise<ReissueCodeResponse> {
    return verifyRequest<ReissueCodeResponse>('/reissue', {
        method: 'POST',
    })
}

export { VerificationAPIError }
