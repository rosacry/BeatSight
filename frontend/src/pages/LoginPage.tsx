/**
 * Login page component.
 * Enhanced with modern glassmorphism design and improved UX.
 * Supports Two-Factor Authentication (2FA) flow.
 */

import { useState, useRef, useEffect } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuthStore, TwoFactorRequiredError } from '@/stores/authStore'
import { ParticleBackground, GradientOrbs } from '@/components/ui/ParticleBackground'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'

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
    const { login, isLoading, isAuthenticated } = useAuthStore()
    const authenticated = isAuthenticated()

    // Get redirect path from location state or default to home
    const from = (location.state as { from?: string })?.from || '/'

    // Redirect if already authenticated (e.g., after page refresh restored session)
    useEffect(() => {
        if (authenticated && !isLoading) {
            navigate(from, { replace: true })
        }
    }, [authenticated, isLoading, navigate, from])

    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [showPassword, setShowPassword] = useState(false)
    const [error, setError] = useState<string | null>(null)

    // 2FA state
    const [requires2FA, setRequires2FA] = useState(false)
    const [totpCode, setTotpCode] = useState(['', '', '', '', '', ''])
    const inputRefs = useRef<(HTMLInputElement | null)[]>([])



    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setError(null)

        try {
            await login({ email, password })
            navigate(from, { replace: true })
        } catch (err) {
            if (err instanceof TwoFactorRequiredError) {
                setRequires2FA(true)
                // Focus first TOTP input after a short delay
                setTimeout(() => inputRefs.current[0]?.focus(), 100)
            } else if (err instanceof Error) {
                setError(err.message)
            } else {
                setError('An unexpected error occurred')
            }
        }
    }

    const handle2FASubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setError(null)

        const code = totpCode.join('')
        if (code.length !== 6) {
            setError('Please enter a 6-digit code')
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
            // Clear the code on error
            setTotpCode(['', '', '', '', '', ''])
            inputRefs.current[0]?.focus()
        }
    }

    const handleTotpChange = (index: number, value: string) => {
        // Only allow digits
        if (value && !/^\d$/.test(value)) return

        const newCode = [...totpCode]
        newCode[index] = value
        setTotpCode(newCode)

        // Auto-focus next input
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
            // Focus the next empty input or the last one
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
        <div className="min-h-[80vh] flex items-center justify-center relative overflow-hidden">
            {/* Background effects */}
            <ParticleBackground particleCount={30} />
            <GradientOrbs />

            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
                className="w-full max-w-md relative z-10"
            >
                <div className="relative bg-slate-900/60 backdrop-blur-xl rounded-2xl p-8 
                              border border-white/10 shadow-2xl shadow-black/50">
                    {/* Subtle gradient border effect */}
                    <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-cyan-500/10 via-transparent to-fuchsia-500/10 pointer-events-none" />

                    <AnimatePresence mode="wait">
                        {!requires2FA ? (
                            <motion.div
                                key="login-form"
                                initial={{ opacity: 0, x: 0 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: -20 }}
                                transition={{ duration: 0.2 }}
                            >
                                <div className="relative text-center mb-8">
                                    {/* Logo with enhanced glow and blend effect */}
                                    <motion.div
                                        initial={{ scale: 0.8, opacity: 0 }}
                                        animate={{ scale: 1, opacity: 1 }}
                                        transition={{ delay: 0.1, type: 'spring', stiffness: 200 }}
                                        className="w-24 h-24 mx-auto mb-6 relative"
                                    >
                                        {/* Outer glow */}
                                        <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/40 to-fuchsia-500/40 rounded-3xl blur-2xl" />
                                        {/* Inner container with solid dark background for better blend */}
                                        <div className="relative w-full h-full rounded-2xl 
                                                      bg-slate-900
                                                      border border-white/10
                                                      flex items-center justify-center
                                                      shadow-2xl shadow-cyan-500/20
                                                      overflow-hidden">
                                            {/* Subtle inner gradient overlay for blend */}
                                            <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/10 via-transparent to-fuchsia-500/10" />
                                            <img
                                                src="/icons/logo-navbar.png"
                                                alt="BeatSight"
                                                className="w-14 h-14 relative z-10 
                                                         [mix-blend-mode:screen] brightness-[1.4] saturate-[1.2]
                                                         drop-shadow-[0_0_12px_rgba(0,212,255,0.4)]"
                                            />
                                        </div>
                                    </motion.div>

                                    <motion.h1
                                        initial={{ opacity: 0 }}
                                        animate={{ opacity: 1 }}
                                        transition={{ delay: 0.2 }}
                                        className="text-3xl font-bold text-white mb-2"
                                    >
                                        Welcome back
                                    </motion.h1>
                                    <motion.p
                                        initial={{ opacity: 0 }}
                                        animate={{ opacity: 1 }}
                                        transition={{ delay: 0.3 }}
                                        className="text-slate-400"
                                    >
                                        Sign in to your BeatSight account
                                    </motion.p>
                                </div>

                                {error && (
                                    <motion.div
                                        initial={{ opacity: 0, scale: 0.95 }}
                                        animate={{ opacity: 1, scale: 1 }}
                                        className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-xl backdrop-blur-sm"
                                    >
                                        <p className="text-red-400 text-sm flex items-center gap-2">
                                            <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                            </svg>
                                            {error}
                                        </p>
                                    </motion.div>
                                )}

                                <form onSubmit={handleSubmit} className="space-y-5 relative">
                                    <div>
                                        <label htmlFor="email" className="block text-sm font-medium text-slate-300 mb-2">
                                            Email address
                                        </label>
                                        <input
                                            id="email"
                                            type="email"
                                            value={email}
                                            onChange={(e) => setEmail(e.target.value)}
                                            required
                                            autoComplete="email"
                                            className="w-full px-4 py-3.5 bg-slate-800/50 border border-white/10 rounded-xl 
                                                     text-white placeholder-slate-500 
                                                     focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500/50
                                                     transition-all duration-200"
                                            placeholder="you@example.com"
                                        />
                                    </div>

                                    <div>
                                        <label htmlFor="password" className="block text-sm font-medium text-slate-300 mb-2">
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
                                                className="w-full px-4 py-3.5 pr-12 bg-slate-800/50 border border-white/10 rounded-xl 
                                                         text-white placeholder-slate-500 
                                                         focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500/50
                                                         transition-all duration-200"
                                                placeholder="••••••••"
                                            />
                                            <button
                                                type="button"
                                                onClick={() => setShowPassword(!showPassword)}
                                                className="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 
                                                         text-slate-400 hover:text-white transition-colors"
                                                aria-label={showPassword ? 'Hide password' : 'Show password'}
                                            >
                                                {showPassword ? <EyeOffIcon /> : <EyeIcon />}
                                            </button>
                                        </div>
                                        <div className="mt-2 text-right">
                                            <Link to="/forgot-password" className="text-sm text-cyan-400 hover:text-cyan-300 transition-colors">
                                                Forgot password?
                                            </Link>
                                        </div>
                                    </div>

                                    <motion.button
                                        type="submit"
                                        disabled={isLoading}
                                        whileHover={{ scale: 1.01 }}
                                        whileTap={{ scale: 0.99 }}
                                        className="w-full py-3.5 px-4 bg-gradient-to-r from-cyan-500 to-cyan-600 
                                                 hover:from-cyan-400 hover:to-cyan-500
                                                 disabled:from-slate-600 disabled:to-slate-700 disabled:cursor-not-allowed
                                                 text-white font-semibold rounded-xl 
                                                 shadow-lg shadow-cyan-500/25 hover:shadow-cyan-500/40
                                                 transition-all duration-300"
                                    >
                                        {isLoading ? (
                                            <span className="flex items-center justify-center gap-2">
                                                <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                                </svg>
                                                Signing in...
                                            </span>
                                        ) : (
                                            'Sign in'
                                        )}
                                    </motion.button>
                                </form>

                                <div className="mt-8 text-center">
                                    <p className="text-slate-400">
                                        Don't have an account?{' '}
                                        <Link to="/register" className="text-cyan-400 hover:text-cyan-300 font-medium transition-colors">
                                            Sign up
                                        </Link>
                                    </p>
                                </div>
                            </motion.div>
                        ) : (
                            <motion.div
                                key="2fa-form"
                                initial={{ opacity: 0, x: 20 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: 20 }}
                                transition={{ duration: 0.2 }}
                            >
                                <div className="relative text-center mb-8">
                                    {/* Shield icon for 2FA */}
                                    <motion.div
                                        initial={{ scale: 0.8, opacity: 0 }}
                                        animate={{ scale: 1, opacity: 1 }}
                                        transition={{ delay: 0.1, type: 'spring', stiffness: 200 }}
                                        className="w-20 h-20 mx-auto mb-6 relative"
                                    >
                                        <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/40 to-cyan-500/40 rounded-full blur-2xl" />
                                        <div className="relative w-full h-full rounded-full 
                                                      bg-slate-900
                                                      border border-white/10
                                                      flex items-center justify-center
                                                      shadow-2xl shadow-emerald-500/20">
                                            <div className="text-emerald-400">
                                                <ShieldIcon />
                                            </div>
                                        </div>
                                    </motion.div>

                                    <motion.h1
                                        initial={{ opacity: 0 }}
                                        animate={{ opacity: 1 }}
                                        transition={{ delay: 0.2 }}
                                        className="text-2xl font-bold text-white mb-2"
                                    >
                                        Two-Factor Authentication
                                    </motion.h1>
                                    <motion.p
                                        initial={{ opacity: 0 }}
                                        animate={{ opacity: 1 }}
                                        transition={{ delay: 0.3 }}
                                        className="text-slate-400 text-sm"
                                    >
                                        Enter the 6-digit code from your authenticator app
                                    </motion.p>
                                </div>

                                {error && (
                                    <motion.div
                                        initial={{ opacity: 0, scale: 0.95 }}
                                        animate={{ opacity: 1, scale: 1 }}
                                        className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-xl backdrop-blur-sm"
                                    >
                                        <p className="text-red-400 text-sm flex items-center gap-2">
                                            <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                            </svg>
                                            {error}
                                        </p>
                                    </motion.div>
                                )}

                                <form onSubmit={handle2FASubmit} className="space-y-6 relative">
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
                                                className="w-12 h-14 text-center text-xl font-mono font-bold
                                                         bg-slate-800/50 border border-white/10 rounded-xl 
                                                         text-white 
                                                         focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500/50
                                                         transition-all duration-200"
                                            />
                                        ))}
                                    </div>

                                    <p className="text-center text-sm text-slate-500">
                                        You can also use a backup code
                                    </p>

                                    <motion.button
                                        type="submit"
                                        disabled={isLoading || totpCode.join('').length !== 6}
                                        whileHover={{ scale: 1.01 }}
                                        whileTap={{ scale: 0.99 }}
                                        className="w-full py-3.5 px-4 bg-gradient-to-r from-cyan-500 to-cyan-600 
                                                 hover:from-cyan-400 hover:to-cyan-500
                                                 disabled:from-slate-600 disabled:to-slate-700 disabled:cursor-not-allowed
                                                 text-white font-semibold rounded-xl 
                                                 shadow-lg shadow-cyan-500/25 hover:shadow-cyan-500/40
                                                 transition-all duration-300"
                                    >
                                        {isLoading ? (
                                            <span className="flex items-center justify-center gap-2">
                                                <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                                </svg>
                                                Verifying...
                                            </span>
                                        ) : (
                                            'Verify'
                                        )}
                                    </motion.button>
                                </form>

                                <div className="mt-6 text-center">
                                    <button
                                        onClick={handleBack}
                                        className="text-slate-400 hover:text-white text-sm transition-colors"
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
