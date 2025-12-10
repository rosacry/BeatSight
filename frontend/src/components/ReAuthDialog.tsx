/**
 * ReAuthDialog - Re-authentication dialog for sensitive actions
 * 
 * Similar to osu!'s account verification popup that appears when
 * accessing sensitive profile settings or performing important actions.
 * 
 * This provides an extra layer of security by requiring users to
 * re-verify their identity before proceeding with sensitive operations.
 */

import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuthStore } from '@/stores/authStore'
import { API_CONFIG } from '@/lib/config'
import { lockBodyScroll, unlockBodyScroll } from '@/lib/bodyScrollLock'

interface ReAuthDialogProps {
    isOpen: boolean
    onClose: () => void
    onSuccess: () => void
    title?: string
    description?: string
    /** Type of verification required */
    verificationType?: 'password' | 'email' | '2fa'
}

const overlayVariants = {
    hidden: { opacity: 0 },
    visible: { opacity: 1 },
}

const dialogVariants = {
    hidden: { opacity: 0, scale: 0.95, y: 10 },
    visible: {
        opacity: 1,
        scale: 1,
        y: 0,
        transition: { type: 'spring', duration: 0.3, bounce: 0.2 }
    },
    exit: {
        opacity: 0,
        scale: 0.95,
        y: 10,
        transition: { duration: 0.15 }
    },
}

export function ReAuthDialog({
    isOpen,
    onClose,
    onSuccess,
    title = 'Account Verification',
    description,
    verificationType = 'password',
}: ReAuthDialogProps) {
    const { user, accessToken } = useAuthStore()
    const dialogRef = useRef<HTMLDivElement>(null)

    // State for different verification types
    const [password, setPassword] = useState('')
    const [verificationCode, setVerificationCode] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [codeSent, setCodeSent] = useState(false)
    const [cooldown, setCooldown] = useState(0)

    // Mask email for display
    const maskedEmail = user?.email
        ? user.email.replace(/(.{2})(.*)(@.*)/, '$1***$3')
        : ''

    // Handle escape key
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape' && isOpen) {
                onClose()
            }
        }

        if (isOpen) {
            document.addEventListener('keydown', handleKeyDown)
            dialogRef.current?.focus()
        }

        return () => {
            document.removeEventListener('keydown', handleKeyDown)
        }
    }, [isOpen, onClose])

    // Prevent body scroll when dialog is open
    useEffect(() => {
        if (isOpen) {
            lockBodyScroll()
            return () => {
                unlockBodyScroll()
            }
        }
    }, [isOpen])

    // Cooldown timer for resending code
    useEffect(() => {
        if (cooldown > 0) {
            const timer = setTimeout(() => setCooldown(cooldown - 1), 1000)
            return () => clearTimeout(timer)
        }
    }, [cooldown])

    // Reset state when dialog opens/closes
    useEffect(() => {
        if (!isOpen) {
            setPassword('')
            setVerificationCode('')
            setError(null)
            setCodeSent(false)
        }
    }, [isOpen])

    const handleSendCode = async () => {
        if (!accessToken) return

        setIsLoading(true)
        setError(null)

        try {
            const response = await fetch(`${API_CONFIG.baseUrl}/api/auth/send-verification-code`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ type: 'reauth' }),
            })

            if (!response.ok) {
                const data = await response.json().catch(() => ({ detail: 'Failed to send code' }))
                throw new Error(data.detail || 'Failed to send verification code')
            }

            setCodeSent(true)
            setCooldown(60) // 60 second cooldown
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to send code')
        } finally {
            setIsLoading(false)
        }
    }

    const handleVerifyPassword = async () => {
        if (!password.trim()) {
            setError('Please enter your password')
            return
        }
        if (!accessToken) return

        setIsLoading(true)
        setError(null)

        try {
            const response = await fetch(`${API_CONFIG.baseUrl}/api/auth/verify-password`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ password }),
            })

            if (!response.ok) {
                const data = await response.json().catch(() => ({ detail: 'Verification failed' }))
                throw new Error(data.detail || 'Invalid password')
            }

            onSuccess()
            onClose()
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Verification failed')
        } finally {
            setIsLoading(false)
        }
    }

    const handleVerifyCode = async () => {
        if (verificationCode.length !== 6) {
            setError('Please enter a 6-digit code')
            return
        }
        if (!accessToken) return

        setIsLoading(true)
        setError(null)

        try {
            const response = await fetch(`${API_CONFIG.baseUrl}/api/auth/verify-code`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ code: verificationCode, type: 'reauth' }),
            })

            if (!response.ok) {
                const data = await response.json().catch(() => ({ detail: 'Verification failed' }))
                throw new Error(data.detail || 'Invalid code')
            }

            onSuccess()
            onClose()
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Verification failed')
        } finally {
            setIsLoading(false)
        }
    }

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        if (verificationType === 'password') {
            handleVerifyPassword()
        } else if (verificationType === 'email' || verificationType === '2fa') {
            handleVerifyCode()
        }
    }

    // Default description based on verification type
    const defaultDescription = verificationType === 'password'
        ? 'Please enter your password to continue.'
        : `An email has been sent to ${maskedEmail} with a verification code. Enter the code.`

    return (
        <AnimatePresence>
            {isOpen && (
                <motion.div
                    initial="hidden"
                    animate="visible"
                    exit="hidden"
                    variants={overlayVariants}
                    className="fixed inset-0 z-50 flex items-center justify-center p-4"
                    onClick={onClose}
                >
                    {/* Backdrop with blur */}
                    <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

                    {/* Dialog - osu-style with decorative image */}
                    <motion.div
                        ref={dialogRef}
                        variants={dialogVariants}
                        initial="hidden"
                        animate="visible"
                        exit="exit"
                        onClick={(e) => e.stopPropagation()}
                        tabIndex={-1}
                        className="relative bg-slate-900 rounded-2xl border border-slate-700/50 shadow-2xl shadow-black/50 max-w-lg w-full overflow-hidden focus:outline-none"
                        role="dialog"
                        aria-modal="true"
                        aria-labelledby="reauth-title"
                    >
                        {/* Close button */}
                        <button
                            onClick={onClose}
                            className="absolute top-4 right-4 z-10 p-1 text-slate-400 hover:text-white transition-colors"
                            aria-label="Close"
                        >
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>

                        {/* Content */}
                        <div className="p-8">
                            {/* Title */}
                            <h2 id="reauth-title" className="text-2xl font-bold text-amber-400 mb-3 text-center">
                                {title}
                            </h2>

                            {/* Description */}
                            <p className="text-slate-300 text-center mb-6 text-sm">
                                {description || defaultDescription}
                            </p>

                            {/* Verification Form */}
                            <form onSubmit={handleSubmit} className="space-y-4">
                                {verificationType === 'password' ? (
                                    <div>
                                        <input
                                            type="password"
                                            value={password}
                                            onChange={(e) => setPassword(e.target.value)}
                                            placeholder="Enter your password"
                                            className="w-full px-4 py-3 bg-slate-800 border border-slate-600 rounded-xl
                                                     text-white placeholder-slate-400 text-center
                                                     focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500
                                                     transition-colors"
                                            autoFocus
                                            autoComplete="current-password"
                                        />
                                    </div>
                                ) : (
                                    <>
                                        {!codeSent ? (
                                            <div className="text-center">
                                                <button
                                                    type="button"
                                                    onClick={handleSendCode}
                                                    disabled={isLoading}
                                                    className="px-6 py-3 bg-amber-500 hover:bg-amber-600 text-black font-medium
                                                             rounded-xl transition-colors disabled:opacity-50"
                                                >
                                                    {isLoading ? 'Sending...' : 'Send Verification Code'}
                                                </button>
                                            </div>
                                        ) : (
                                            <div>
                                                <input
                                                    type="text"
                                                    value={verificationCode}
                                                    onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                                                    placeholder="Enter 6-digit code"
                                                    className="w-full px-4 py-3 bg-slate-800 border border-slate-600 rounded-xl
                                                             text-white placeholder-slate-400 text-center text-2xl tracking-widest
                                                             focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500
                                                             transition-colors font-mono"
                                                    maxLength={6}
                                                    autoFocus
                                                />
                                                <p className="text-xs text-slate-500 text-center mt-2">
                                                    Make sure to check your spam folder if you can't find the email.
                                                </p>
                                            </div>
                                        )}
                                    </>
                                )}

                                {/* Error message */}
                                {error && (
                                    <div className="p-3 bg-red-500/20 border border-red-500/30 rounded-lg text-red-400 text-sm text-center">
                                        {error}
                                    </div>
                                )}

                                {/* Submit button */}
                                {(verificationType === 'password' || codeSent) && (
                                    <button
                                        type="submit"
                                        disabled={isLoading}
                                        className="w-full py-3 bg-slate-700 hover:bg-slate-600 text-white font-medium
                                                 rounded-xl transition-colors disabled:opacity-50"
                                    >
                                        {isLoading ? 'Verifying...' : 'Verify'}
                                    </button>
                                )}
                            </form>

                            {/* Helper links for email verification */}
                            {verificationType === 'email' && codeSent && (
                                <div className="mt-6 text-center text-sm text-slate-400">
                                    <p>
                                        If you can't access your email or have forgotten what you used, please follow the{' '}
                                        <a href="/forgot-password" className="text-cyan-400 hover:text-cyan-300 transition-colors">
                                            email recovery process here
                                        </a>
                                        .
                                    </p>
                                    <p className="mt-2">
                                        You can also{' '}
                                        <button
                                            onClick={handleSendCode}
                                            disabled={cooldown > 0}
                                            className="text-cyan-400 hover:text-cyan-300 transition-colors disabled:text-slate-500"
                                        >
                                            request another code{cooldown > 0 ? ` (${cooldown}s)` : ''}
                                        </button>
                                        {' '}or{' '}
                                        <button
                                            onClick={onClose}
                                            className="text-cyan-400 hover:text-cyan-300 transition-colors"
                                        >
                                            sign out
                                        </button>
                                        .
                                    </p>
                                </div>
                            )}
                        </div>
                    </motion.div>
                </motion.div>
            )}
        </AnimatePresence>
    )
}

/**
 * Hook for easily using re-authentication
 */
export function useReAuth() {
    const [isOpen, setIsOpen] = useState(false)
    const [config, setConfig] = useState<Omit<ReAuthDialogProps, 'isOpen' | 'onClose' | 'onSuccess'>>({})
    const resolveRef = useRef<((value: boolean) => void) | null>(null)

    const requireReAuth = (
        options?: Omit<ReAuthDialogProps, 'isOpen' | 'onClose' | 'onSuccess'>
    ): Promise<boolean> => {
        setConfig(options || {})
        setIsOpen(true)

        return new Promise((resolve) => {
            resolveRef.current = resolve
        })
    }

    const handleClose = () => {
        setIsOpen(false)
        resolveRef.current?.(false)
    }

    const handleSuccess = () => {
        setIsOpen(false)
        resolveRef.current?.(true)
    }

    const ReAuthDialogComponent = () => (
        <ReAuthDialog
            isOpen={isOpen}
            onClose={handleClose}
            onSuccess={handleSuccess}
            {...config}
        />
    )

    return { requireReAuth, ReAuthDialog: ReAuthDialogComponent }
}

export default ReAuthDialog
