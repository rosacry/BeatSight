/**
 * Two-Factor Authentication hooks.
 * Provides hooks for managing 2FA setup and verification.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { API_CONFIG } from '@/lib/config'
import { getAccessToken } from '@/stores/authStore'

const API_BASE = API_CONFIG.baseUrl

interface TwoFactorStatus {
    enabled: boolean
    backup_codes_remaining: number
    enabled_at: string | null
}

interface TwoFactorSetupResponse {
    provisioning_uri: string
    qr_code_base64: string
    backup_codes: string[]
    message: string
}

interface BackupCodesResponse {
    backup_codes: string[]
    message: string
}

interface MessageResponse {
    success: boolean
    message: string
}

async function twoFactorRequest<T>(
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

    const response = await fetch(`${API_BASE}/auth/2fa${endpoint}`, {
        ...options,
        headers: { ...headers, ...options.headers as Record<string, string> },
    })

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Request failed' }))
        throw new Error(error.detail || `HTTP ${response.status}`)
    }

    return response.json()
}

/**
 * Hook to get 2FA status for the current user.
 */
export function useTwoFactorStatus() {
    return useQuery<TwoFactorStatus>({
        queryKey: ['twoFactorStatus'],
        queryFn: async () => {
            return twoFactorRequest<TwoFactorStatus>('/status')
        },
        // Cache the status to avoid repeated fetches
        staleTime: 1000 * 60 * 5, // 5 minutes
        gcTime: 1000 * 60 * 10, // 10 minutes (formerly cacheTime)
    })
}

/**
 * Hook to initiate 2FA setup.
 */
export function useTwoFactorSetup() {
    const queryClient = useQueryClient()

    return useMutation<TwoFactorSetupResponse, Error>({
        mutationFn: async () => {
            return twoFactorRequest<TwoFactorSetupResponse>('/setup', {
                method: 'POST',
            })
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['twoFactorStatus'] })
        },
    })
}

/**
 * Hook to enable 2FA with verification code.
 */
export function useTwoFactorEnable() {
    const queryClient = useQueryClient()

    return useMutation<MessageResponse, Error, { verificationCode: string }>({
        mutationFn: async ({ verificationCode }) => {
            return twoFactorRequest<MessageResponse>('/enable', {
                method: 'POST',
                body: JSON.stringify({ verification_code: verificationCode }),
            })
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['twoFactorStatus'] })
        },
    })
}

/**
 * Hook to disable 2FA.
 */
export function useTwoFactorDisable() {
    const queryClient = useQueryClient()

    return useMutation<MessageResponse, Error, { password: string }>({
        mutationFn: async ({ password }) => {
            return twoFactorRequest<MessageResponse>('/disable', {
                method: 'POST',
                body: JSON.stringify({ password }),
            })
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['twoFactorStatus'] })
        },
    })
}

/**
 * Hook to verify a 2FA code.
 */
export function useTwoFactorVerify() {
    return useMutation<MessageResponse, Error, { code: string }>({
        mutationFn: async ({ code }) => {
            return twoFactorRequest<MessageResponse>('/verify', {
                method: 'POST',
                body: JSON.stringify({ code }),
            })
        },
    })
}

/**
 * Hook to regenerate backup codes.
 */
export function useTwoFactorRegenerateBackupCodes() {
    const queryClient = useQueryClient()

    return useMutation<BackupCodesResponse, Error>({
        mutationFn: async () => {
            return twoFactorRequest<BackupCodesResponse>('/backup-codes/regenerate', {
                method: 'POST',
            })
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['twoFactorStatus'] })
        },
    })
}
