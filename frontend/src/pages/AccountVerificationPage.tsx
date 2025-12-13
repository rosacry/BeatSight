/**
 * Account Verification Page
 * 
 * osu!-style verification page that appears when users need to verify
 * their identity before accessing sensitive areas like settings.
 * 
 * Supports:
 * - 8-character code entry
 * - Request new code
 * - Shows obscured email
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate, useSearchParams, useLocation } from 'react-router-dom'
import { useVerificationStore } from '@/stores/verificationStore'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'

// Character count for verification code (8 hex chars)
const CODE_LENGTH = 8

export function AccountVerificationPage() {
    useDocumentTitle('Account Verification')
    const navigate = useNavigate()
    const location = useLocation()
    const [searchParams] = useSearchParams()

    // Where to redirect after verification
    const returnTo = searchParams.get('return') || location.state?.from || '/settings'

    // Store state
    const {
        isVerified,
        isLoading,
        error,
        isVerificationInProgress,
        obscuredEmail,
        verificationMessage,
        startVerification,
        submitCode,
        requestNewCode,
        clearError,
    } = useVerificationStore()

    // Local state for code input
    const [code, setCode] = useState('')
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [successMessage, setSuccessMessage] = useState<string | null>(null)
    const inputRef = useRef<HTMLInputElement>(null)

    // Initialize verification on mount
    useEffect(() => {
        if (!isVerificationInProgress && !isVerified) {
            startVerification()
        }
    }, [isVerificationInProgress, isVerified, startVerification])

    // Auto-focus input
    useEffect(() => {
        if (isVerificationInProgress && inputRef.current) {
            inputRef.current.focus()
        }
    }, [isVerificationInProgress])

    // Redirect if already verified
    useEffect(() => {
        if (isVerified) {
            navigate(returnTo, { replace: true })
        }
    }, [isVerified, navigate, returnTo])

    // Auto-submit when code is complete
    useEffect(() => {
        const normalized = code.replace(/\s/g, '')
        if (normalized.length === CODE_LENGTH && !isSubmitting) {
            handleSubmit()
        }
    }, [code])

    const handleCodeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        // Allow only hex characters and spaces
        const value = e.target.value.replace(/[^0-9a-fA-F\s]/g, '')
        setCode(value)
        clearError()
    }

    const handleSubmit = useCallback(async () => {
        const normalized = code.replace(/\s/g, '').toLowerCase()
        if (normalized.length !== CODE_LENGTH) {
            return
        }

        setIsSubmitting(true)
        clearError()

        const success = await submitCode(normalized)

        if (success) {
            setSuccessMessage('Verification successful!')
            // Will auto-redirect via useEffect
        }

        setIsSubmitting(false)
    }, [code, submitCode, clearError])

    const handleRequestNewCode = async () => {
        setCode('')
        clearError()
        await requestNewCode()
    }

    // Format code for display (add space in middle)
    const formatCode = (input: string): string => {
        const clean = input.replace(/\s/g, '')
        if (clean.length > 4) {
            return `${clean.slice(0, 4)} ${clean.slice(4)}`
        }
        return clean
    }

    return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-dark-500 via-dark-500 to-black px-4">
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.3 }}
                className="w-full max-w-md"
            >
                {/* Card */}
                <div className="bg-dark-400/80 backdrop-blur-sm rounded-2xl border border-dark-300 overflow-hidden shadow-2xl">
                    {/* Header */}
                    <div className="bg-gradient-to-r from-primary-600 to-pink-500 p-6 text-center">
                        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-white/20 flex items-center justify-center">
                            <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                            </svg>
                        </div>
                        <h1 className="text-2xl font-bold text-white">Account Verification</h1>
                    </div>

                    {/* Content */}
                    <div className="p-6">
                        {isLoading && !isVerificationInProgress ? (
                            // Loading state
                            <div className="text-center py-8">
                                <div className="animate-spin w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full mx-auto mb-4" />
                                <p className="text-gray-400">Sending verification email...</p>
                            </div>
                        ) : (
                            <>
                                {/* Info message */}
                                <p className="text-gray-300 text-center mb-6">
                                    {verificationMessage || (
                                        <>
                                            An email has been sent to{' '}
                                            <span className="font-semibold text-white">{obscuredEmail}</span>{' '}
                                            with a verification code. Enter the code.
                                        </>
                                    )}
                                </p>

                                {/* Code input */}
                                <div className="mb-6">
                                    <div className="relative">
                                        <input
                                            ref={inputRef}
                                            type="text"
                                            value={formatCode(code)}
                                            onChange={handleCodeChange}
                                            placeholder="Enter code"
                                            maxLength={9} // 8 chars + 1 space
                                            className={`
                                                w-full px-4 py-4 text-2xl text-center font-mono tracking-[0.3em]
                                                bg-dark-500 border-2 rounded-lg
                                                focus:outline-none transition-colors
                                                ${error
                                                    ? 'border-red-500 text-red-400'
                                                    : 'border-primary-500/50 focus:border-primary-500 text-white'
                                                }
                                            `}
                                            autoComplete="off"
                                            autoCorrect="off"
                                            autoCapitalize="off"
                                            spellCheck={false}
                                        />

                                        {/* Verifying indicator */}
                                        {isSubmitting && (
                                            <div className="absolute right-4 top-1/2 -translate-y-1/2">
                                                <div className="animate-spin w-5 h-5 border-2 border-primary-500 border-t-transparent rounded-full" />
                                            </div>
                                        )}
                                    </div>

                                    {/* Error message */}
                                    <AnimatePresence>
                                        {error && (
                                            <motion.p
                                                initial={{ opacity: 0, y: -10 }}
                                                animate={{ opacity: 1, y: 0 }}
                                                exit={{ opacity: 0, y: -10 }}
                                                className="mt-2 text-sm text-red-400 text-center"
                                            >
                                                {error}
                                            </motion.p>
                                        )}
                                    </AnimatePresence>

                                    {/* Success message */}
                                    <AnimatePresence>
                                        {successMessage && (
                                            <motion.p
                                                initial={{ opacity: 0, y: -10 }}
                                                animate={{ opacity: 1, y: 0 }}
                                                exit={{ opacity: 0, y: -10 }}
                                                className="mt-2 text-sm text-green-400 text-center"
                                            >
                                                {successMessage}
                                            </motion.p>
                                        )}
                                    </AnimatePresence>
                                </div>

                                {/* Help text */}
                                <div className="text-sm text-gray-400 space-y-3 mb-6">
                                    <p className="flex items-start gap-2">
                                        <svg className="w-4 h-4 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                        </svg>
                                        Make sure to check your spam folder if you can't find the email.
                                    </p>
                                </div>

                                {/* Actions */}
                                <div className="flex flex-col gap-3">
                                    <button
                                        onClick={handleRequestNewCode}
                                        disabled={isLoading}
                                        className="text-primary-400 hover:text-primary-300 text-sm transition-colors disabled:opacity-50"
                                    >
                                        Request another code
                                    </button>

                                    <button
                                        onClick={() => navigate(-1)}
                                        className="text-gray-500 hover:text-gray-400 text-sm transition-colors"
                                    >
                                        Sign out
                                    </button>
                                </div>
                            </>
                        )}
                    </div>
                </div>

                {/* Security notice */}
                <p className="mt-6 text-center text-xs text-gray-500">
                    If you can't access your email or have forgotten what you used,<br />
                    please contact{' '}
                    <a href="mailto:support@beatsight.io" className="text-primary-400 hover:underline">
                        support@beatsight.io
                    </a>
                </p>
            </motion.div>
        </div>
    )
}

/**
 * Verification Success Page
 * Shown after clicking the verification link from email.
 */
export function VerificationSuccessPage() {
    useDocumentTitle('Verification Complete')
    const markVerified = useVerificationStore((state) => state.markVerified)

    // Mark as verified on mount
    useEffect(() => {
        markVerified()
    }, [markVerified])

    return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-dark-500 via-dark-500 to-black px-4">
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.3 }}
                className="w-full max-w-md"
            >
                <div className="bg-dark-400/80 backdrop-blur-sm rounded-2xl border border-dark-300 overflow-hidden shadow-2xl">
                    {/* Header */}
                    <div className="bg-gradient-to-r from-primary-600 to-pink-500 p-6 text-center">
                        <div className="flex items-center justify-center gap-2 mb-2">
                            <span className="text-white/80 font-medium">BeatSight</span>
                        </div>
                        <h2 className="text-lg font-semibold text-white">ACCOUNT VERIFICATION</h2>
                    </div>

                    {/* Content */}
                    <div className="p-8 text-center">
                        <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-green-500/20 flex items-center justify-center">
                            <svg className="w-10 h-10 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                            </svg>
                        </div>

                        <h1 className="text-2xl font-bold text-white mb-3">
                            Verification has been completed
                        </h1>

                        <p className="text-gray-400">
                            You can close this tab/window now
                        </p>
                    </div>
                </div>
            </motion.div>
        </div>
    )
}

/**
 * Verification Invalid Page
 * Shown when a verification link is invalid or expired.
 */
export function VerificationInvalidPage() {
    useDocumentTitle('Verification Invalid')
    const navigate = useNavigate()

    return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-dark-500 via-dark-500 to-black px-4">
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.3 }}
                className="w-full max-w-md"
            >
                <div className="bg-dark-400/80 backdrop-blur-sm rounded-2xl border border-dark-300 overflow-hidden shadow-2xl">
                    {/* Header */}
                    <div className="bg-gradient-to-r from-red-600 to-orange-500 p-6 text-center">
                        <div className="flex items-center justify-center gap-2 mb-2">
                            <span className="text-white/80 font-medium">BeatSight</span>
                        </div>
                        <h2 className="text-lg font-semibold text-white">ACCOUNT VERIFICATION</h2>
                    </div>

                    {/* Content */}
                    <div className="p-8 text-center">
                        <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-red-500/20 flex items-center justify-center">
                            <svg className="w-10 h-10 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </div>

                        <h1 className="text-2xl font-bold text-white mb-3">
                            Invalid or expired verification link
                        </h1>

                        <p className="text-gray-400 mb-6">
                            The verification link you clicked is no longer valid.
                            Please request a new verification code.
                        </p>

                        <button
                            onClick={() => navigate('/settings')}
                            className="px-6 py-3 bg-primary-600 hover:bg-primary-500 text-white rounded-lg font-medium transition-colors"
                        >
                            Go to Settings
                        </button>
                    </div>
                </div>
            </motion.div>
        </div>
    )
}

export default AccountVerificationPage
