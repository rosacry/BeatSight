/**
 * Registration page component.
 * Enhanced with modern glassmorphism design and improved UX.
 */

import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useAuthStore } from '@/stores/authStore'
import { ParticleBackground, GradientOrbs } from '@/components/ui/ParticleBackground'

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

// Check icon for password requirements
function CheckIcon({ filled }: { filled: boolean }) {
    return (
        <svg className={`w-4 h-4 ${filled ? 'text-green-400' : 'text-slate-600'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
    )
}

export function RegisterPage() {
    const navigate = useNavigate()
    const { register, isLoading } = useAuthStore()

    const [displayName, setDisplayName] = useState('')
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [confirmPassword, setConfirmPassword] = useState('')
    const [showPassword, setShowPassword] = useState(false)
    const [showConfirmPassword, setShowConfirmPassword] = useState(false)
    const [error, setError] = useState<string | null>(null)

    // Password requirements
    const passwordRequirements = {
        length: password.length >= 8,
        match: password === confirmPassword && confirmPassword.length > 0,
    }

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setError(null)

        // Validate password match
        if (password !== confirmPassword) {
            setError('Passwords do not match')
            return
        }

        // Validate password length
        if (password.length < 8) {
            setError('Password must be at least 8 characters')
            return
        }

        // Validate display name
        if (displayName.length < 2) {
            setError('Display name must be at least 2 characters')
            return
        }

        try {
            await register({ email, password, display_name: displayName })
            navigate('/', { replace: true })
        } catch (err) {
            if (err instanceof Error) {
                setError(err.message)
            } else {
                setError('An unexpected error occurred')
            }
        }
    }

    return (
        <div className="min-h-[80vh] flex items-center justify-center py-8 relative overflow-hidden">
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

                    <div className="relative text-center mb-6">
                        {/* Logo with glow effect */}
                        <motion.div
                            initial={{ scale: 0.8, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            transition={{ delay: 0.1, type: 'spring', stiffness: 200 }}
                            className="w-20 h-20 mx-auto mb-6 relative"
                        >
                            <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/30 to-fuchsia-500/30 rounded-2xl blur-xl" />
                            <div className="relative w-full h-full rounded-2xl bg-gradient-to-br from-slate-800 to-slate-900 
                                          border border-white/20 flex items-center justify-center
                                          shadow-lg shadow-fuchsia-500/20">
                                <img src="/icons/logo-navbar.png" alt="BeatSight" className="w-12 h-12" />
                            </div>
                        </motion.div>

                        <motion.h1
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ delay: 0.2 }}
                            className="text-3xl font-bold text-white mb-2"
                        >
                            Create account
                        </motion.h1>
                        <motion.p
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ delay: 0.3 }}
                            className="text-slate-400"
                        >
                            Join BeatSight and start creating beatmaps
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

                    <form onSubmit={handleSubmit} className="space-y-4 relative">
                        <div>
                            <label htmlFor="displayName" className="block text-sm font-medium text-slate-300 mb-2">
                                Display name
                            </label>
                            <input
                                id="displayName"
                                type="text"
                                value={displayName}
                                onChange={(e) => setDisplayName(e.target.value)}
                                required
                                autoComplete="name"
                                className="w-full px-4 py-3.5 bg-slate-800/50 border border-white/10 rounded-xl 
                                         text-white placeholder-slate-500 
                                         focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500/50
                                         transition-all duration-200"
                                placeholder="DrumMaster2000"
                            />
                        </div>

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
                                    autoComplete="new-password"
                                    minLength={8}
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
                        </div>

                        <div>
                            <label htmlFor="confirmPassword" className="block text-sm font-medium text-slate-300 mb-2">
                                Confirm password
                            </label>
                            <div className="relative">
                                <input
                                    id="confirmPassword"
                                    type={showConfirmPassword ? 'text' : 'password'}
                                    value={confirmPassword}
                                    onChange={(e) => setConfirmPassword(e.target.value)}
                                    required
                                    autoComplete="new-password"
                                    className="w-full px-4 py-3.5 pr-12 bg-slate-800/50 border border-white/10 rounded-xl 
                                             text-white placeholder-slate-500 
                                             focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500/50
                                             transition-all duration-200"
                                    placeholder="••••••••"
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                                    className="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 
                                             text-slate-400 hover:text-white transition-colors"
                                    aria-label={showConfirmPassword ? 'Hide password' : 'Show password'}
                                >
                                    {showConfirmPassword ? <EyeOffIcon /> : <EyeIcon />}
                                </button>
                            </div>
                        </div>

                        {/* Password requirements indicator */}
                        {password.length > 0 && (
                            <motion.div
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: 'auto' }}
                                className="flex flex-col gap-1 text-sm"
                            >
                                <div className="flex items-center gap-2">
                                    <CheckIcon filled={passwordRequirements.length} />
                                    <span className={passwordRequirements.length ? 'text-green-400' : 'text-slate-500'}>
                                        At least 8 characters
                                    </span>
                                </div>
                                {confirmPassword.length > 0 && (
                                    <div className="flex items-center gap-2">
                                        <CheckIcon filled={passwordRequirements.match} />
                                        <span className={passwordRequirements.match ? 'text-green-400' : 'text-slate-500'}>
                                            Passwords match
                                        </span>
                                    </div>
                                )}
                            </motion.div>
                        )}

                        <motion.button
                            type="submit"
                            disabled={isLoading}
                            whileHover={{ scale: 1.01 }}
                            whileTap={{ scale: 0.99 }}
                            className="w-full py-3.5 px-4 mt-2 bg-gradient-to-r from-cyan-500 to-fuchsia-500 
                                     hover:from-cyan-400 hover:to-fuchsia-400
                                     disabled:from-slate-600 disabled:to-slate-700 disabled:cursor-not-allowed
                                     text-white font-semibold rounded-xl 
                                     shadow-lg shadow-fuchsia-500/25 hover:shadow-fuchsia-500/40
                                     transition-all duration-300"
                        >
                            {isLoading ? (
                                <span className="flex items-center justify-center gap-2">
                                    <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                    </svg>
                                    Creating account...
                                </span>
                            ) : (
                                'Create account'
                            )}
                        </motion.button>
                    </form>

                    <div className="mt-6 text-center">
                        <p className="text-slate-400">
                            Already have an account?{' '}
                            <Link to="/login" className="text-cyan-400 hover:text-cyan-300 font-medium transition-colors">
                                Sign in
                            </Link>
                        </p>
                    </div>

                    <div className="mt-6 pt-6 border-t border-white/10">
                        <p className="text-xs text-slate-500 text-center">
                            By creating an account, you agree to our{' '}
                            <Link to="/terms" className="text-slate-400 hover:text-white underline">Terms of Service</Link>
                            {' '}and{' '}
                            <Link to="/privacy" className="text-slate-400 hover:text-white underline">Privacy Policy</Link>.
                        </p>
                    </div>
                </div>
            </motion.div>
        </div>
    )
}
