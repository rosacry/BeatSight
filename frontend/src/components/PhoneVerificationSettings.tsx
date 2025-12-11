/**
 * Phone verification settings component.
 * 
 * Allows users to add and verify their phone number via SMS code.
 * This is required for participating in beatmap accuracy voting.
 * Users with both email and phone verified receive a 200 karma bonus.
 */

import { useState, useEffect, useCallback } from 'react'
import { useAuthStore } from '@/stores/authStore'
import { API_CONFIG } from '@/lib/config'
import { createLogger } from '@/lib/logger'

const logger = createLogger('PhoneVerification')
const API_BASE = API_CONFIG.baseUrl

interface PhoneStatus {
    phone_number: string | null
    phone_verified: boolean
    can_send_code: boolean
    next_send_allowed_at: string | null
}

interface SendCodeResponse {
    success: boolean
    message: string
    expires_at: string | null
}

interface VerifyCodeResponse {
    success: boolean
    message: string
    phone_verified: boolean
    karma_bonus_awarded: boolean
    karma_bonus_amount: number
}

export function PhoneVerificationSettings() {
    const user = useAuthStore((state) => state.user)
    const accessToken = useAuthStore((state) => state.accessToken)
    const fetchCurrentUser = useAuthStore((state) => state.fetchCurrentUser)

    const [phoneNumber, setPhoneNumber] = useState('')
    const [verificationCode, setVerificationCode] = useState('')
    const [status, setStatus] = useState<PhoneStatus | null>(null)
    const [isLoading, setIsLoading] = useState(false)
    const [isSendingCode, setIsSendingCode] = useState(false)
    const [isVerifying, setIsVerifying] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [successMessage, setSuccessMessage] = useState<string | null>(null)
    const [codeSent, setCodeSent] = useState(false)
    const [codeExpiresAt, setCodeExpiresAt] = useState<Date | null>(null)

    // Load phone status on mount
    const loadPhoneStatus = useCallback(async () => {
        if (!accessToken) return
        try {
            setIsLoading(true)
            const response = await fetch(`${API_BASE}/api/phone/status`, {
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                },
            })
            if (response.ok) {
                const data = await response.json()
                setStatus(data)
            }
        } catch (err) {
            logger.error('Failed to load phone status:', err)
        } finally {
            setIsLoading(false)
        }
    }, [accessToken])

    useEffect(() => {
        loadPhoneStatus()
    }, [loadPhoneStatus])

    const handleSendCode = async () => {
        if (!accessToken || !phoneNumber.trim()) return

        setError(null)
        setSuccessMessage(null)
        setIsSendingCode(true)

        try {
            const response = await fetch(`${API_BASE}/api/phone/send-code`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${accessToken}`,
                },
                body: JSON.stringify({ phone_number: phoneNumber }),
            })

            const data: SendCodeResponse = await response.json()

            if (!response.ok) {
                throw new Error(data.message || 'Failed to send verification code')
            }

            setCodeSent(true)
            setSuccessMessage(data.message)
            if (data.expires_at) {
                setCodeExpiresAt(new Date(data.expires_at))
            }
            await loadPhoneStatus()
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to send code')
        } finally {
            setIsSendingCode(false)
        }
    }

    const handleVerifyCode = async () => {
        if (!accessToken || !verificationCode.trim()) return

        setError(null)
        setSuccessMessage(null)
        setIsVerifying(true)

        try {
            const response = await fetch(`${API_BASE}/api/phone/verify`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${accessToken}`,
                },
                body: JSON.stringify({ code: verificationCode }),
            })

            const data: VerifyCodeResponse = await response.json()

            if (!response.ok) {
                throw new Error(data.message || 'Failed to verify code')
            }

            setSuccessMessage(data.message)
            setCodeSent(false)
            setVerificationCode('')
            setPhoneNumber('')
            await loadPhoneStatus()
            // Refresh user data to update karma score if bonus was awarded
            if (data.karma_bonus_awarded) {
                await fetchCurrentUser()
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to verify code')
        } finally {
            setIsVerifying(false)
        }
    }

    const handleRemovePhone = async () => {
        if (!accessToken) return
        if (!confirm('Remove phone number? You\'ll lose accuracy voting access.')) {
            return
        }

        setError(null)
        setIsLoading(true)

        try {
            const response = await fetch(`${API_BASE}/api/phone/remove`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                },
            })

            if (!response.ok) {
                const data = await response.json()
                throw new Error(data.detail || 'Failed to remove phone number')
            }

            setSuccessMessage('Phone number removed successfully')
            setCodeSent(false)
            await loadPhoneStatus()
            await fetchCurrentUser()
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to remove phone')
        } finally {
            setIsLoading(false)
        }
    }

    // Format phone number as user types
    const formatPhoneInput = (value: string) => {
        // Keep only digits and + at the start
        const cleaned = value.replace(/[^\d+]/g, '')
        // Ensure + is only at the start
        if (cleaned.includes('+') && !cleaned.startsWith('+')) {
            return cleaned.replace(/\+/g, '')
        }
        return cleaned
    }

    if (isLoading && !status) {
        return (
            <div className="p-4 rounded-xl bg-dark-400/30 border border-white/10/50 animate-pulse">
                <div className="h-20 bg-dark-300/30 rounded"></div>
            </div>
        )
    }

    const isVerified = user?.phone_verified || status?.phone_verified

    return (
        <div className="p-4 rounded-xl bg-dark-400/30 border border-white/10/50">
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center ${isVerified
                        ? 'bg-green-500/20'
                        : 'bg-amber-500/20'
                        }`}>
                        {isVerified ? (
                            <svg className="w-5 h-5 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                        ) : (
                            <svg className="w-5 h-5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                            </svg>
                        )}
                    </div>
                    <div>
                        <p className="text-white font-medium">Phone Verification</p>
                        <p className={`text-sm ${isVerified ? 'text-green-400' : 'text-amber-400'}`}>
                            {isVerified
                                ? `Verified: ${status?.phone_number || user?.phone_number}`
                                : 'Phone not verified'}
                        </p>
                    </div>
                </div>
                {isVerified && (
                    <button
                        onClick={handleRemovePhone}
                        disabled={isLoading}
                        className="text-sm text-red-400 hover:text-red-300 transition-colors"
                    >
                        Remove
                    </button>
                )}
            </div>

            {/* Info banner about verification benefits */}
            {!isVerified && (
                <div className="mb-4 p-3 rounded-lg bg-primary-500/10 border border-primary-500/20">
                    <p className="text-sm text-primary-300">
                        <strong>Verify phone:</strong> +200 karma bonus + accuracy voting access
                    </p>
                </div>
            )}

            {/* Error message */}
            {error && (
                <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                    <p className="text-sm text-red-400">{error}</p>
                </div>
            )}

            {/* Success message */}
            {successMessage && (
                <div className="mb-4 p-3 rounded-lg bg-green-500/10 border border-green-500/20">
                    <p className="text-sm text-green-400">{successMessage}</p>
                </div>
            )}

            {/* Phone input form - only show if not verified */}
            {!isVerified && (
                <div className="space-y-4">
                    {!codeSent ? (
                        /* Step 1: Enter phone number */
                        <div>
                            <label className="block text-sm font-medium text-gray-300 mb-2">
                                Phone Number
                            </label>
                            <div className="flex gap-2">
                                <input
                                    type="tel"
                                    value={phoneNumber}
                                    onChange={(e) => setPhoneNumber(formatPhoneInput(e.target.value))}
                                    placeholder="+1 (555) 555-1234"
                                    className="input flex-1"
                                    disabled={isSendingCode}
                                />
                                <button
                                    onClick={handleSendCode}
                                    disabled={isSendingCode || !phoneNumber.trim() || !status?.can_send_code}
                                    className="btn bg-primary-500 hover:bg-primary-600 text-white px-4 disabled:opacity-50"
                                >
                                    {isSendingCode ? (
                                        <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                        </svg>
                                    ) : (
                                        'Send Code'
                                    )}
                                </button>
                            </div>
                            <p className="mt-2 text-xs text-gray-500">
                                Include country code (e.g., +1)
                            </p>
                            {status && !status.can_send_code && status.next_send_allowed_at && (
                                <p className="mt-2 text-xs text-amber-400">
                                    Rate limited. You can request a new code after{' '}
                                    {new Date(status.next_send_allowed_at).toLocaleTimeString()}
                                </p>
                            )}
                        </div>
                    ) : (
                        /* Step 2: Enter verification code */
                        <div>
                            <label className="block text-sm font-medium text-gray-300 mb-2">
                                Verification Code
                            </label>
                            <div className="flex gap-2">
                                <input
                                    type="text"
                                    value={verificationCode}
                                    onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                                    placeholder="123456"
                                    className="input flex-1 text-center tracking-widest text-lg font-mono"
                                    maxLength={6}
                                    disabled={isVerifying}
                                />
                                <button
                                    onClick={handleVerifyCode}
                                    disabled={isVerifying || verificationCode.length !== 6}
                                    className="btn bg-green-500 hover:bg-green-600 text-white px-4 disabled:opacity-50"
                                >
                                    {isVerifying ? (
                                        <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                        </svg>
                                    ) : (
                                        'Verify'
                                    )}
                                </button>
                            </div>
                            <div className="mt-2 flex items-center justify-between">
                                <p className="text-xs text-gray-500">
                                    Code sent to phone
                                </p>
                                <button
                                    onClick={() => {
                                        setCodeSent(false)
                                        setVerificationCode('')
                                        setError(null)
                                    }}
                                    className="text-xs text-primary-400 hover:text-primary-300"
                                >
                                    Use different number
                                </button>
                            </div>
                            {codeExpiresAt && (
                                <p className="mt-1 text-xs text-gray-500">
                                    Code expires at {codeExpiresAt.toLocaleTimeString()}
                                </p>
                            )}
                        </div>
                    )}
                </div>
            )}

            {/* Show verification benefits when verified */}
            {isVerified && user?.email_verified && (
                <div className="mt-4 p-3 rounded-lg bg-green-500/10 border border-green-500/20">
                    <p className="text-sm text-green-400">
                        ✓ Fully verified! Accuracy voting unlocked.
                    </p>
                </div>
            )}

            {/* Show reminder if email not verified */}
            {isVerified && !user?.email_verified && (
                <div className="mt-4 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
                    <p className="text-sm text-amber-400">
                        Verify email for karma bonus + voting access.
                    </p>
                </div>
            )}
        </div>
    )
}
