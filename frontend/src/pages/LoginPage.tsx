/**
 * Login page component.
 * Clean design with 2FA support.
 */

import { useState, useRef, useEffect } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuthStore, TwoFactorRequiredError } from '@/stores/authStore'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { forceUnlockBodyScroll, removeStaleOverlays } from '@/lib/bodyScrollLock'
import { TRANSITION_DURATION, EASE_CURVE } from '@/components/ui/UnifiedTransitions'

// Eye icons for password visibility toggle
function EyeIcon() {
    return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
        </svg>
    )
}

function EyeOffIcon() {
    return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
        </svg>
    )
}

function ShieldIcon() {
    return (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
        </svg>
    )
}

export function LoginPage() {
    useDocumentTitle('sign in')
    const navigate = useNavigate()
    const location = useLocation()
    const { login, isLoading, isAuthenticated, _hasHydrated: hasHydrated } = useAuthStore()
    const authenticated = isAuthenticated()

    const from = (location.state as { from?: string })?.from || '/'

    // Reset any stuck body styles on mount
    useEffect(() => {
        forceUnlockBodyScroll()
        removeStaleOverlays()
        const timeoutId = setTimeout(() => {
            forceUnlockBodyScroll()
            removeStaleOverlays()
        }, 100)
        return () => clearTimeout(timeoutId)
    }, [])

    // Redirect if already authenticated
    useEffect(() => {
        if (authenticated && !isLoading && hasHydrated) {
            navigate(from, { replace: true })
        }
    }, [authenticated, isLoading, hasHydrated, navigate, from])

    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [showPassword, setShowPassword] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [isSubmitting, setIsSubmitting] = useState(false)

    // 2FA state
    const [requires2FA, setRequires2FA] = useState(false)
    const [totpCode, setTotpCode] = useState(['', '', '', '', '', ''])
    const inputRefs = useRef<(HTMLInputElement | null)[]>([])

    // Show loading state while checking auth
    if (isLoading || !hasHydrated) {
        return (
            <div className="min-h-[80vh] flex items-center justify-center">
                <div className="flex flex-col items-center gap-3">
                    <svg className="animate-spin h-8 w-8 text-primary-400" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    <p className="text-gray-500 text-sm">Checking authentication...</p>
                </div>
            </div>
        )
    }

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setError(null)
        setIsSubmitting(true)

        try {
            await login({ email, password })
            navigate(from, { replace: true })
        } catch (err) {
            if (err instanceof TwoFactorRequiredError) {
                setRequires2FA(true)
                setTimeout(() => inputRefs.current[0]?.focus(), 100)
            } else if (err instanceof Error) {
                setError(err.message)
            } else {
                setError('An unexpected error occurred')
            }
        } finally {
            setIsSubmitting(false)
        }
    }

    const handle2FASubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setError(null)
        setIsSubmitting(true)

        const code = totpCode.join('')
        if (code.length !== 6) {
            setError('Please enter a 6-digit code')
            setIsSubmitting(false)
            return
        }

        try {
            await login({ email, password, totp_code: code })
            navigate(from, { replace: true })
        } catch (err) {
            if (err instanceof Error) {
                setError(err.message)
            } else {
                setError('An unexpected error occurred')
            }
            setTotpCode(['', '', '', '', '', ''])
            inputRefs.current[0]?.focus()
        } finally {
            setIsSubmitting(false)
        }
    }

    const handleTotpChange = (index: number, value: string) => {
        if (value && !/^\d$/.test(value)) return
        const newCode = [...totpCode]
        newCode[index] = value
        setTotpCode(newCode)
        if (value && index < 5) {
            inputRefs.current[index + 1]?.focus()
        }
    }

    const handleTotpKeyDown = (index: number, e: React.KeyboardEvent) => {
        if (e.key === 'Backspace' && !totpCode[index] && index > 0) {
            inputRefs.current[index - 1]?.focus()
        }
    }

    const handleTotpPaste = (e: React.ClipboardEvent) => {
        e.preventDefault()
        const pastedData = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6)
        if (pastedData) {
            const newCode = [...totpCode]
            for (let i = 0; i < 6; i++) {
                newCode[i] = pastedData[i] || ''
            }
            setTotpCode(newCode)
            const nextEmpty = newCode.findIndex(c => !c)
            inputRefs.current[nextEmpty === -1 ? 5 : nextEmpty]?.focus()
        }
    }

    const handleBack = () => {
        setRequires2FA(false)
        setTotpCode(['', '', '', '', '', ''])
        setError(null)
    }

    return (
        <div className="min-h-[80vh] flex items-center justify-center px-4">
            <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: TRANSITION_DURATION, ease: EASE_CURVE }}
                className="w-full max-w-sm"
            >
                <div className="bg-dark-400 rounded-xl p-6 border border-white/5">
                    <AnimatePresence mode="wait">
                        {!requires2FA ? (
                            <motion.div
                                key="login-form"
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                exit={{ opacity: 0 }}
                                transition={{ duration: TRANSITION_DURATION, ease: EASE_CURVE }}
                            >
                                {/* Header */}
                                <div className="text-center mb-6">
                                    <div className="w-16 h-16 mx-auto mb-4 rounded-xl bg-dark-300 
                                                  border border-white/10 flex items-center justify-center">
                                        <img
                                            src="/icons/logo-navbar.png"
                                            alt="BeatSight"
                                            className="w-10 h-10"
                                        />
                                    </div>
                                    <h1 className="text-xl font-bold text-white mb-1">
                                        Welcome back
                                    </h1>
                                    <p className="text-gray-500 text-sm">
                                        Sign in to continue
                                    </p>
                                </div>

                                {error && (
                                    <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                                        <p className="text-red-400 text-sm flex items-center gap-2">
                                            <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                            </svg>
                                            {error}
                                        </p>
                                    </div>
                                )}

                                <form onSubmit={handleSubmit} className="space-y-4">
                                    <div>
                                        <label htmlFor="email" className="block text-sm font-medium text-gray-300 mb-1.5">
                                            Email
                                        </label>
                                        <input
                                            id="email"
                                            type="email"
                                            value={email}
                                            onChange={(e) => setEmail(e.target.value)}
                                            required
                                            autoComplete="email"
                                            className="w-full px-3 py-2.5 bg-dark-300 border border-white/10 rounded-lg 
                                                     text-white placeholder-gray-500 text-sm
                                                     focus:outline-none focus:ring-2 focus:ring-primary-400/50 focus:border-primary-400/50
                                                     transition-colors"
                                            placeholder="you@example.com"
                                        />
                                    </div>

                                    <div>
                                        <label htmlFor="password" className="block text-sm font-medium text-gray-300 mb-1.5">
                                            Password
                                        </label>
                                        <div className="relative">
                                            <input
                                                id="password"
                                                type={showPassword ? 'text' : 'password'}
                                                value={password}
                                                onChange={(e) => setPassword(e.target.value)}
                                                required
                                                autoComplete="current-password"
                                                className="w-full px-3 py-2.5 pr-10 bg-dark-300 border border-white/10 rounded-lg 
                                                         text-white placeholder-gray-500 text-sm
                                                         focus:outline-none focus:ring-2 focus:ring-primary-400/50 focus:border-primary-400/50
                                                         transition-colors"
                                                placeholder="••••••••"
                                            />
                                            <button
                                                type="button"
                                                onClick={() => setShowPassword(!showPassword)}
                                                className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 
                                                         text-gray-500 hover:text-white transition-colors"
                                                aria-label={showPassword ? 'Hide password' : 'Show password'}
                                            >
                                                {showPassword ? <EyeOffIcon /> : <EyeIcon />}
                                            </button>
                                        </div>
                                        <div className="mt-1.5 text-right">
                                            <Link to="/forgot-password" className="text-xs text-primary-400 hover:text-primary-300 transition-colors">
                                                Forgot password?
                                            </Link>
                                        </div>
                                    </div>

                                    <button
                                        type="submit"
                                        disabled={isSubmitting}
                                        className="w-full py-2.5 px-4 bg-primary-400 hover:bg-primary-500
                                                 disabled:bg-gray-600 disabled:cursor-not-allowed
                                                 text-white font-semibold rounded-lg text-sm
                                                 transition-colors"
                                    >
                                        {isSubmitting ? (
                                            <span className="flex items-center justify-center gap-2">
                                                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                                </svg>
                                                Signing in...
                                            </span>
                                        ) : (
                                            'Sign in'
                                        )}
                                    </button>
                                </form>

                                <div className="mt-6 text-center">
                                    <p className="text-gray-500 text-sm">
                                        Don't have an account?{' '}
                                        <Link to="/register" className="text-primary-400 hover:text-primary-300 font-medium transition-colors">
                                            Sign up
                                        </Link>
                                    </p>
                                </div>
                            </motion.div>
                        ) : (
                            <motion.div
                                key="2fa-form"
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                exit={{ opacity: 0 }}
                                transition={{ duration: TRANSITION_DURATION, ease: EASE_CURVE }}
                            >
                                {/* 2FA Header */}
                                <div className="text-center mb-6">
                                    <div className="w-14 h-14 mx-auto mb-4 rounded-xl bg-green-500/10 
                                                  border border-green-500/30 flex items-center justify-center text-green-400">
                                        <ShieldIcon />
                                    </div>
                                    <h1 className="text-xl font-bold text-white mb-1">
                                        Two-Factor Authentication
                                    </h1>
                                    <p className="text-gray-500 text-sm">
                                        Enter the 6-digit code from your app
                                    </p>
                                </div>

                                {error && (
                                    <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                                        <p className="text-red-400 text-sm flex items-center gap-2">
                                            <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                            </svg>
                                            {error}
                                        </p>
                                    </div>
                                )}

                                <form onSubmit={handle2FASubmit} className="space-y-5">
                                    {/* 6-digit code input */}
                                    <div className="flex justify-center gap-2" onPaste={handleTotpPaste}>
                                        {totpCode.map((digit, index) => (
                                            <input
                                                key={index}
                                                ref={(el) => { inputRefs.current[index] = el }}
                                                type="text"
                                                inputMode="numeric"
                                                maxLength={1}
                                                value={digit}
                                                onChange={(e) => handleTotpChange(index, e.target.value)}
                                                onKeyDown={(e) => handleTotpKeyDown(index, e)}
                                                className="w-10 h-12 text-center text-lg font-mono font-bold
                                                         bg-dark-300 border border-white/10 rounded-lg 
                                                         text-white 
                                                         focus:outline-none focus:ring-2 focus:ring-primary-400/50 focus:border-primary-400/50
                                                         transition-colors"
                                            />
                                        ))}
                                    </div>

                                    <p className="text-center text-xs text-gray-500">
                                        You can also use a backup code
                                    </p>

                                    <button
                                        type="submit"
                                        disabled={isSubmitting || totpCode.join('').length !== 6}
                                        className="w-full py-2.5 px-4 bg-primary-400 hover:bg-primary-500
                                                 disabled:bg-gray-600 disabled:cursor-not-allowed
                                                 text-white font-semibold rounded-lg text-sm
                                                 transition-colors"
                                    >
                                        {isSubmitting ? (
                                            <span className="flex items-center justify-center gap-2">
                                                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                                </svg>
                                                Verifying...
                                            </span>
                                        ) : (
                                            'Verify'
                                        )}
                                    </button>
                                </form>

                                <div className="mt-5 text-center">
                                    <button
                                        onClick={handleBack}
                                        className="text-gray-500 hover:text-white text-sm transition-colors"
                                    >
                                        ← Back to login
                                    </button>
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            </motion.div>
        </div>
    )
}
