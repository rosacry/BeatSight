/**
 * Session verification state management using Zustand.
 * 
 * Manages the osu!-style sensitive action verification state.
 * When users access sensitive areas (settings, credits, etc.) after
 * a period of inactivity, they must verify their identity.
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import {
    getVerificationStatus,
    initiateVerification,
    verifyWithCode,
    reissueVerificationCode,
    type VerificationInitiateResponse,
} from '@/api/verification'

/** Timeout in milliseconds before verification expires (30 minutes) */
const VERIFICATION_TIMEOUT_MS = 30 * 60 * 1000

interface VerificationStore {
    // State
    isVerified: boolean
    lastVerifiedAt: number | null // Timestamp
    isLoading: boolean
    error: string | null

    // Verification flow state
    isVerificationInProgress: boolean
    obscuredEmail: string | null
    verificationMessage: string | null

    // Computed
    needsVerification: () => boolean

    // Actions
    checkVerificationStatus: () => Promise<boolean>
    startVerification: () => Promise<VerificationInitiateResponse | null>
    submitCode: (code: string) => Promise<boolean>
    requestNewCode: () => Promise<boolean>
    clearError: () => void
    resetVerification: () => void
    markVerified: () => void
}

export const useVerificationStore = create<VerificationStore>()(
    persist(
        (set, get) => ({
            // Initial state
            isVerified: false,
            lastVerifiedAt: null,
            isLoading: false,
            error: null,
            isVerificationInProgress: false,
            obscuredEmail: null,
            verificationMessage: null,

            // Check if verification is needed
            needsVerification: () => {
                const state = get()

                // Not verified at all
                if (!state.isVerified || !state.lastVerifiedAt) {
                    return true
                }

                // Check if verification has expired
                const now = Date.now()
                const elapsed = now - state.lastVerifiedAt
                return elapsed > VERIFICATION_TIMEOUT_MS
            },

            // Check verification status with backend
            checkVerificationStatus: async () => {
                set({ isLoading: true, error: null })

                try {
                    const status = await getVerificationStatus()

                    if (status.is_verified) {
                        set({
                            isVerified: true,
                            lastVerifiedAt: Date.now(),
                            isLoading: false,
                        })
                        return true
                    } else {
                        set({
                            isVerified: false,
                            isLoading: false,
                        })
                        return false
                    }
                } catch (error) {
                    set({
                        isLoading: false,
                        error: error instanceof Error ? error.message : 'Failed to check status',
                    })
                    return false
                }
            },

            // Start verification flow (sends email)
            startVerification: async () => {
                set({ isLoading: true, error: null })

                try {
                    const response = await initiateVerification()

                    set({
                        isLoading: false,
                        isVerificationInProgress: true,
                        obscuredEmail: response.obscured_email,
                        verificationMessage: response.message,
                    })

                    return response
                } catch (error) {
                    set({
                        isLoading: false,
                        error: error instanceof Error ? error.message : 'Failed to initiate verification',
                    })
                    return null
                }
            },

            // Submit verification code
            submitCode: async (code: string) => {
                set({ isLoading: true, error: null })

                try {
                    const response = await verifyWithCode(code)

                    if (response.success) {
                        set({
                            isVerified: true,
                            lastVerifiedAt: Date.now(),
                            isLoading: false,
                            isVerificationInProgress: false,
                            obscuredEmail: null,
                            verificationMessage: null,
                        })
                        return true
                    } else {
                        set({
                            isLoading: false,
                            error: response.message || 'Verification failed',
                            verificationMessage: response.message,
                        })
                        return false
                    }
                } catch (error) {
                    set({
                        isLoading: false,
                        error: error instanceof Error ? error.message : 'Verification failed',
                    })
                    return false
                }
            },

            // Request a new verification code
            requestNewCode: async () => {
                set({ isLoading: true, error: null })

                try {
                    const response = await reissueVerificationCode()

                    set({
                        isLoading: false,
                        verificationMessage: response.message,
                    })

                    return response.success
                } catch (error) {
                    set({
                        isLoading: false,
                        error: error instanceof Error ? error.message : 'Failed to reissue code',
                    })
                    return false
                }
            },

            // Clear error
            clearError: () => {
                set({ error: null })
            },

            // Reset verification state (e.g., on logout)
            resetVerification: () => {
                set({
                    isVerified: false,
                    lastVerifiedAt: null,
                    isVerificationInProgress: false,
                    obscuredEmail: null,
                    verificationMessage: null,
                    error: null,
                })
            },

            // Mark as verified (called from link verification success page)
            markVerified: () => {
                set({
                    isVerified: true,
                    lastVerifiedAt: Date.now(),
                    isVerificationInProgress: false,
                    obscuredEmail: null,
                    verificationMessage: null,
                })
            },
        }),
        {
            name: 'beatsight-verification',
            // Only persist verification state, not loading/error
            partialize: (state) => ({
                isVerified: state.isVerified,
                lastVerifiedAt: state.lastVerifiedAt,
            }),
        }
    )
)

// Helper to check if verification is needed (for use in components)
export function needsSessionVerification(): boolean {
    return useVerificationStore.getState().needsVerification()
}

// Helper to reset verification on logout
export function resetSessionVerification(): void {
    useVerificationStore.getState().resetVerification()
}
