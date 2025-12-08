/**
 * User settings page.
 * Account settings, preferences, and notification configuration.
 * Persists to backend via /api/users/me and /api/sync/preferences
 */

import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuthStore } from '@/stores/authStore'
import { createLogger, getDeveloperModeEnabled, enableDeveloperMode, disableDeveloperMode } from '@/lib/logger'
import { AvatarUpload } from '@/components/AvatarUpload'
import { TwoFactorSettings } from '@/components/TwoFactorSettings'
import { PhoneVerificationSettings } from '@/components/PhoneVerificationSettings'
import { API_CONFIG } from '@/lib/config'
import type { UserPreferences } from '@/types/sync'
import { DEFAULT_CUSTOM_SETTINGS } from '@/types/sync'

const logger = createLogger('Settings')
const API_BASE = API_CONFIG.baseUrl

type SettingsTab = 'account' | 'preferences' | 'notifications' | 'privacy' | 'developer' | 'danger'

// Use the shared Preferences type but make it compatible with our local usage
type Preferences = Omit<UserPreferences, 'version' | 'checksum' | 'last_modified'>

// API helper with auth
async function apiRequest<T>(
    endpoint: string,
    options: RequestInit = {},
    token: string | null
): Promise<T> {
    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
    }
    if (token) {
        headers['Authorization'] = `Bearer ${token}`
    }

    const response = await fetch(`${API_BASE}/api${endpoint}`, {
        ...options,
        headers: { ...headers, ...options.headers },
    })

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Request failed' }))
        throw new Error(error.detail || 'Request failed')
    }

    return response.json()
}

export function SettingsPage() {
    const user = useAuthStore((state) => state.user)
    const accessToken = useAuthStore((state) => state.accessToken)
    const logout = useAuthStore((state) => state.logout)
    const fetchCurrentUser = useAuthStore((state) => state.fetchCurrentUser)

    const [activeTab, setActiveTab] = useState<SettingsTab>('account')
    const [isSaving, setIsSaving] = useState(false)
    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [successMessage, setSuccessMessage] = useState<string | null>(null)
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
    const [deleteConfirmText, setDeleteConfirmText] = useState('')
    const [deletePassword, setDeletePassword] = useState('')

    // Form state
    const [displayName, setDisplayName] = useState(user?.display_name || '')

    // Developer mode state (synced with server via custom_settings)
    const [developerMode, setDeveloperMode] = useState(getDeveloperModeEnabled())

    // Contribution consent state
    const [contributionConsent, setContributionConsent] = useState({
        consent_given: false,
        allow_anonymous_export: true,
        allow_public_credit: false,
    })
    const [isLoadingConsent, setIsLoadingConsent] = useState(false)

    // Preferences from server
    const [preferences, setPreferences] = useState<Preferences | null>(null)

    // Load contribution consent
    const loadContributionConsent = useCallback(async () => {
        if (!accessToken) return
        try {
            setIsLoadingConsent(true)
            const consent = await apiRequest<typeof contributionConsent>(
                '/contributions/consent',
                {},
                accessToken
            )
            setContributionConsent(consent)
        } catch (err) {
            logger.error('Failed to load contribution consent:', err)
            // Use defaults on error
        } finally {
            setIsLoadingConsent(false)
        }
    }, [accessToken])

    // Save contribution consent
    const handleSaveContributionConsent = async () => {
        if (!accessToken) return
        setIsSaving(true)
        setError(null)
        try {
            await apiRequest('/contributions/consent', {
                method: 'POST',
                body: JSON.stringify(contributionConsent),
            }, accessToken)
            setSuccessMessage('Privacy settings saved successfully!')
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to save privacy settings')
        } finally {
            setIsSaving(false)
        }
    }

    // Load preferences on mount
    const loadPreferences = useCallback(async () => {
        if (!accessToken) return
        try {
            setIsLoading(true)
            const prefs = await apiRequest<Preferences>('/sync/preferences', {}, accessToken)
            setPreferences(prefs)
            setError(null)
        } catch (err) {
            logger.error('Failed to load preferences:', err)
            // Initialize with defaults if not found
            setPreferences({
                scroll_speed: 1.0,
                note_skin: 'default',
                audio_offset_ms: 0,
                visual_offset_ms: 0,
                background_dim: 0.5,  // Match backend default
                master_volume: 1.0,
                music_volume: 0.8,
                effects_volume: 0.8,
                hitsound_volume: 1.0,
                theme: 'dark',
                language: 'en',
                custom_settings: DEFAULT_CUSTOM_SETTINGS,
            })
        } finally {
            setIsLoading(false)
        }
    }, [accessToken])

    useEffect(() => {
        loadPreferences()
        loadContributionConsent()
    }, [loadPreferences, loadContributionConsent])

    // Sync developer mode with server preferences when they load
    useEffect(() => {
        if (preferences?.custom_settings?.developerModeEnabled !== undefined) {
            const serverValue = preferences.custom_settings.developerModeEnabled
            const localValue = getDeveloperModeEnabled()

            // If server has developer mode enabled but local doesn't, enable locally
            if (serverValue && !localValue) {
                enableDeveloperMode()
                setDeveloperMode(true)
            }
            // If server has developer mode disabled but local has it, sync to server state
            else if (!serverValue && localValue) {
                disableDeveloperMode()
                setDeveloperMode(false)
            }
            // Otherwise just sync the state
            else {
                setDeveloperMode(serverValue)
            }
        }
    }, [preferences?.custom_settings?.developerModeEnabled])

    useEffect(() => {
        if (user) {
            setDisplayName(user.display_name || '')
        }
    }, [user])

    // Clear messages after 3 seconds
    useEffect(() => {
        if (successMessage) {
            const timer = setTimeout(() => setSuccessMessage(null), 3000)
            return () => clearTimeout(timer)
        }
    }, [successMessage])

    const handleSaveProfile = async () => {
        if (!accessToken) return
        setIsSaving(true)
        setError(null)
        try {
            await apiRequest('/users/me', {
                method: 'PATCH',
                body: JSON.stringify({ display_name: displayName }),
            }, accessToken)
            await fetchCurrentUser()
            setSuccessMessage('Profile saved successfully!')
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to save profile')
        } finally {
            setIsSaving(false)
        }
    }

    const handleSavePreferences = async () => {
        if (!accessToken || !preferences) return
        setIsSaving(true)
        setError(null)
        try {
            await apiRequest('/sync/preferences', {
                method: 'PATCH',
                body: JSON.stringify({
                    scroll_speed: preferences.scroll_speed,
                    note_skin: preferences.note_skin,
                    audio_offset_ms: preferences.audio_offset_ms,
                    visual_offset_ms: preferences.visual_offset_ms,
                    background_dim: preferences.background_dim,
                    master_volume: preferences.master_volume,
                    music_volume: preferences.music_volume,
                    effects_volume: preferences.effects_volume,
                    hitsound_volume: preferences.hitsound_volume,
                    theme: preferences.theme,
                    language: preferences.language,
                    custom_settings: preferences.custom_settings,
                }),
            }, accessToken)
            setSuccessMessage('Preferences saved successfully!')
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to save preferences')
        } finally {
            setIsSaving(false)
        }
    }

    const handleDeleteAccount = async () => {
        if (deleteConfirmText !== 'DELETE') {
            setError('Please type DELETE to confirm')
            return
        }
        if (!accessToken) return

        setIsSaving(true)
        setError(null)
        try {
            await apiRequest('/users/me', {
                method: 'DELETE',
                body: JSON.stringify({
                    confirmation: 'DELETE',
                    password: deletePassword,
                }),
            }, accessToken)
            logout()
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to delete account')
            setIsSaving(false)
        }
    }

    // Send verification email
    const handleSendVerificationEmail = async () => {
        if (!accessToken || !user?.email) return
        setIsSaving(true)
        setError(null)
        try {
            await apiRequest('/auth/send-verification-email', {
                method: 'POST',
            }, accessToken)
            setSuccessMessage('Verification email sent! Please check your inbox.')
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to send verification email')
        } finally {
            setIsSaving(false)
        }
    }

    // Send password reset email
    const handleSendPasswordResetEmail = async () => {
        if (!user?.email) return
        setIsSaving(true)
        setError(null)
        try {
            await fetch(`${API_BASE}/auth/forgot-password`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: user.email }),
            })
            setSuccessMessage('Password reset link sent! Please check your inbox.')
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to send password reset email')
        } finally {
            setIsSaving(false)
        }
    }

    // Update custom settings helper
    const updateCustomSetting = <K extends keyof Preferences['custom_settings']>(
        key: K,
        value: Preferences['custom_settings'][K]
    ) => {
        if (!preferences) return
        setPreferences({
            ...preferences,
            custom_settings: { ...preferences.custom_settings, [key]: value },
        })
    }

    // Toggle developer mode - updates both local storage and server preferences
    const handleDeveloperModeToggle = (enabled: boolean) => {
        // Update local storage for immediate effect
        if (enabled) {
            enableDeveloperMode()
        } else {
            disableDeveloperMode()
        }
        setDeveloperMode(enabled)

        // Also update server preferences for cross-device sync
        if (preferences) {
            updateCustomSetting('developerModeEnabled', enabled)
        }
    }

    const tabs: { id: SettingsTab; label: string; icon: React.ReactNode }[] = [
        {
            id: 'account',
            label: 'Account',
            icon: (
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
            ),
        },
        {
            id: 'preferences',
            label: 'Preferences',
            icon: (
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
                </svg>
            ),
        },
        {
            id: 'notifications',
            label: 'Notifications',
            icon: (
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                </svg>
            ),
        },
        {
            id: 'privacy',
            label: 'Privacy & Data',
            icon: (
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
            ),
        },
        {
            id: 'developer',
            label: 'Developer',
            icon: (
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                </svg>
            ),
        },
        {
            id: 'danger',
            label: 'Danger Zone',
            icon: (
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
            ),
        },
    ]

    return (
        <div className="max-w-4xl mx-auto">
            <h1 className="text-2xl font-bold text-white mb-8">Settings</h1>

            {/* Feedback Messages */}
            {error && (
                <div className="mb-4 p-3 bg-red-500/20 border border-red-500/50 rounded-lg text-red-400">
                    {error}
                </div>
            )}
            {successMessage && (
                <div className="mb-4 p-3 bg-green-500/20 border border-green-500/50 rounded-lg text-green-400">
                    {successMessage}
                </div>
            )}

            <div className="flex flex-col md:flex-row gap-8">
                {/* Sidebar */}
                <nav className="md:w-48 space-y-1">
                    {tabs.map((tab) => (
                        <motion.button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id)}
                            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors relative ${activeTab === tab.id
                                ? 'text-white'
                                : 'text-gray-400 hover:text-white hover:bg-gray-800'
                                }`}
                            whileHover={{ x: 4 }}
                            whileTap={{ scale: 0.98 }}
                            transition={{ duration: 0.15 }}
                        >
                            {activeTab === tab.id && (
                                <motion.div
                                    layoutId="activeTab"
                                    className="absolute inset-0 bg-gray-700 rounded-lg"
                                    initial={false}
                                    transition={{ type: "spring", bounce: 0.2, duration: 0.4 }}
                                />
                            )}
                            <span className="relative z-10 flex items-center gap-3">
                                {tab.icon}
                                {tab.label}
                            </span>
                        </motion.button>
                    ))}
                </nav>

                {/* Content */}
                <div className="flex-1">
                    <AnimatePresence mode="wait">
                        {isLoading ? (
                            <motion.div
                                key="loading"
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                exit={{ opacity: 0 }}
                                className="card flex items-center justify-center py-12"
                            >
                                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
                            </motion.div>
                        ) : (
                            <motion.div
                                key={activeTab}
                                initial={{ opacity: 0, x: 20 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: -20 }}
                                transition={{ duration: 0.2 }}
                            >
                                {activeTab === 'account' && (
                                    <div className="space-y-6">
                                        {/* Profile Section - Modern Card */}
                                        <div className="card bg-gradient-to-br from-slate-800/50 to-slate-900/50 backdrop-blur-sm border border-white/5">
                                            <div className="flex items-center gap-3 mb-6">
                                                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500/20 to-cyan-600/20 flex items-center justify-center">
                                                    <svg className="w-5 h-5 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                                                    </svg>
                                                </div>
                                                <div>
                                                    <h2 className="text-lg font-semibold text-white">Profile</h2>
                                                    <p className="text-sm text-gray-400">Manage your public profile information</p>
                                                </div>
                                            </div>

                                            <div className="grid md:grid-cols-[auto,1fr] gap-8 items-start">
                                                {/* Avatar Upload - Improved Design */}
                                                <div className="flex flex-col items-center gap-4">
                                                    <AvatarUpload
                                                        currentAvatarUrl={user?.avatar_url}
                                                        size="lg"
                                                        onUploadSuccess={() => {
                                                            setSuccessMessage('Avatar updated successfully!')
                                                        }}
                                                        onUploadError={(err) => {
                                                            setError(err)
                                                        }}
                                                    />
                                                    <div className="text-center">
                                                        <p className="text-xs text-gray-500">Supported: JPG, PNG, GIF</p>
                                                        <p className="text-xs text-gray-500">Max size: 5MB</p>
                                                    </div>
                                                </div>

                                                {/* Profile Form */}
                                                <div className="space-y-5 flex-1">
                                                    <div>
                                                        <label className="block text-sm font-medium text-gray-300 mb-2">
                                                            Display Name
                                                        </label>
                                                        <div className="relative">
                                                            <input
                                                                type="text"
                                                                value={displayName}
                                                                onChange={(e) => setDisplayName(e.target.value)}
                                                                className="input pl-10 bg-slate-800/50 border-slate-700/50 focus:border-cyan-500/50 focus:ring-cyan-500/20"
                                                                placeholder="Your display name"
                                                            />
                                                            <svg className="w-5 h-5 text-gray-500 absolute left-3 top-1/2 -translate-y-1/2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                                                            </svg>
                                                        </div>
                                                    </div>

                                                    <div>
                                                        <label className="block text-sm font-medium text-gray-300 mb-2">
                                                            Email Address
                                                        </label>
                                                        <div className="relative">
                                                            <input
                                                                type="email"
                                                                value={user?.email || ''}
                                                                disabled
                                                                className="input pl-10 bg-slate-900/50 border-slate-700/30 text-gray-500 cursor-not-allowed"
                                                            />
                                                            <svg className="w-5 h-5 text-gray-600 absolute left-3 top-1/2 -translate-y-1/2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                                                            </svg>
                                                            <div className="absolute right-3 top-1/2 -translate-y-1/2">
                                                                {user?.email_verified ? (
                                                                    <span className="flex items-center gap-1 text-xs text-green-400">
                                                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                                                        </svg>
                                                                        Verified
                                                                    </span>
                                                                ) : (
                                                                    <span className="flex items-center gap-1 text-xs text-amber-400">
                                                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                                                        </svg>
                                                                        Not verified
                                                                    </span>
                                                                )}
                                                            </div>
                                                        </div>
                                                        <p className="text-xs text-gray-500 mt-2 flex items-center gap-1">
                                                            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                                            </svg>
                                                            Contact support to change your email address
                                                        </p>
                                                    </div>

                                                    <button
                                                        onClick={handleSaveProfile}
                                                        disabled={isSaving || displayName === user?.display_name}
                                                        className="btn btn-primary w-full sm:w-auto group relative overflow-hidden"
                                                    >
                                                        <span className="relative z-10 flex items-center justify-center gap-2">
                                                            {isSaving ? (
                                                                <>
                                                                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                                                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                                                    </svg>
                                                                    Saving...
                                                                </>
                                                            ) : (
                                                                <>
                                                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                                                    </svg>
                                                                    Save Changes
                                                                </>
                                                            )}
                                                        </span>
                                                    </button>
                                                </div>
                                            </div>
                                        </div>

                                        {/* Security Section */}
                                        <div className="card bg-gradient-to-br from-slate-800/50 to-slate-900/50 backdrop-blur-sm border border-white/5">
                                            <div className="flex items-center gap-3 mb-6">
                                                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500/20 to-orange-600/20 flex items-center justify-center">
                                                    <svg className="w-5 h-5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                                                    </svg>
                                                </div>
                                                <div>
                                                    <h2 className="text-lg font-semibold text-white">Security</h2>
                                                    <p className="text-sm text-gray-400">Manage your account security</p>
                                                </div>
                                            </div>

                                            <div className="space-y-6">
                                                {/* Email Verification Status */}
                                                <div className="p-4 rounded-xl bg-slate-800/30 border border-slate-700/50">
                                                    <div className="flex items-center justify-between">
                                                        <div className="flex items-center gap-3">
                                                            <div className={`w-10 h-10 rounded-full flex items-center justify-center ${user?.email_verified
                                                                ? 'bg-green-500/20'
                                                                : 'bg-amber-500/20'
                                                                }`}>
                                                                {user?.email_verified ? (
                                                                    <svg className="w-5 h-5 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                                                    </svg>
                                                                ) : (
                                                                    <svg className="w-5 h-5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                                                    </svg>
                                                                )}
                                                            </div>
                                                            <div>
                                                                <p className="text-white font-medium">Email Verification</p>
                                                                <p className={`text-sm ${user?.email_verified ? 'text-green-400' : 'text-amber-400'}`}>
                                                                    {user?.email_verified ? 'Your email is verified' : 'Email not verified'}
                                                                </p>
                                                            </div>
                                                        </div>
                                                        {!user?.email_verified && (
                                                            <button
                                                                onClick={handleSendVerificationEmail}
                                                                disabled={isSaving}
                                                                className="btn btn-sm bg-amber-500/20 hover:bg-amber-500/30 text-amber-400 border border-amber-500/30"
                                                            >
                                                                Send Verification Email
                                                            </button>
                                                        )}
                                                    </div>
                                                </div>

                                                {/* Phone Verification */}
                                                <PhoneVerificationSettings />

                                                {/* Password Reset */}
                                                <div className="p-4 rounded-xl bg-slate-800/30 border border-slate-700/50">
                                                    <div className="flex items-center justify-between">
                                                        <div className="flex items-center gap-3">
                                                            <div className="w-10 h-10 rounded-full bg-slate-700/50 flex items-center justify-center">
                                                                <svg className="w-5 h-5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                                                                </svg>
                                                            </div>
                                                            <div>
                                                                <p className="text-white font-medium">Password</p>
                                                                <p className="text-sm text-gray-400">Reset your password via email</p>
                                                            </div>
                                                        </div>
                                                        <button
                                                            onClick={handleSendPasswordResetEmail}
                                                            disabled={isSaving}
                                                            className="btn btn-sm bg-slate-700/50 hover:bg-slate-700 text-white border border-slate-600/50"
                                                        >
                                                            <svg className="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                                                            </svg>
                                                            Send Reset Link
                                                        </button>
                                                    </div>
                                                </div>

                                                {/* Two-Factor Authentication */}
                                                <TwoFactorSettings />
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {activeTab === 'preferences' && preferences && (
                                    <div className="card space-y-6">
                                        <h2 className="text-lg font-semibold text-white">Generation Preferences</h2>

                                        <div className="space-y-4">
                                            <label className="flex items-center justify-between">
                                                <div>
                                                    <span className="text-white">Auto-generate beatmap</span>
                                                    <p className="text-sm text-gray-500">
                                                        Automatically start generation after upload
                                                    </p>
                                                </div>
                                                <input
                                                    type="checkbox"
                                                    checked={preferences.custom_settings.autoGenerateBeatmap}
                                                    onChange={(e) => updateCustomSetting('autoGenerateBeatmap', e.target.checked)}
                                                    className="w-5 h-5 rounded bg-gray-700 border-gray-600 text-primary-500 focus:ring-primary-500"
                                                />
                                            </label>

                                            <div>
                                                <label className="block text-sm font-medium text-gray-300 mb-2">
                                                    Default Quantization
                                                </label>
                                                <select
                                                    value={preferences.custom_settings.defaultQuantization}
                                                    onChange={(e) => updateCustomSetting('defaultQuantization', e.target.value)}
                                                    className="input"
                                                >
                                                    <option value="8th">8th Notes</option>
                                                    <option value="16th">16th Notes</option>
                                                    <option value="32nd">32nd Notes</option>
                                                    <option value="none">No Quantization</option>
                                                </select>
                                            </div>

                                            <div>
                                                <label className="block text-sm font-medium text-gray-300 mb-2">
                                                    Detection Sensitivity ({Math.round(preferences.custom_settings.defaultSensitivity * 100)}%)
                                                </label>
                                                <input
                                                    type="range"
                                                    min="0"
                                                    max="1"
                                                    step="0.05"
                                                    value={preferences.custom_settings.defaultSensitivity}
                                                    onChange={(e) => updateCustomSetting('defaultSensitivity', parseFloat(e.target.value))}
                                                    className="w-full"
                                                />
                                            </div>

                                            <label className="flex items-center justify-between">
                                                <div>
                                                    <span className="text-white">Show confidence overlay</span>
                                                    <p className="text-sm text-gray-500">
                                                        Display detection confidence heatmap
                                                    </p>
                                                </div>
                                                <input
                                                    type="checkbox"
                                                    checked={preferences.custom_settings.showConfidenceOverlay}
                                                    onChange={(e) => updateCustomSetting('showConfidenceOverlay', e.target.checked)}
                                                    className="w-5 h-5 rounded bg-gray-700 border-gray-600 text-primary-500 focus:ring-primary-500"
                                                />
                                            </label>

                                            <label className="flex items-center justify-between">
                                                <div>
                                                    <span className="text-white">Enable offline mode</span>
                                                    <p className="text-sm text-gray-500">
                                                        Cache beatmaps for offline access
                                                    </p>
                                                </div>
                                                <input
                                                    type="checkbox"
                                                    checked={preferences.custom_settings.enableOfflineMode}
                                                    onChange={(e) => updateCustomSetting('enableOfflineMode', e.target.checked)}
                                                    className="w-5 h-5 rounded bg-gray-700 border-gray-600 text-primary-500 focus:ring-primary-500"
                                                />
                                            </label>
                                        </div>

                                        <button onClick={handleSavePreferences} disabled={isSaving} className="btn btn-primary">
                                            {isSaving ? 'Saving...' : 'Save Preferences'}
                                        </button>
                                    </div>
                                )}

                                {activeTab === 'notifications' && preferences && (
                                    <div className="card space-y-6">
                                        <h2 className="text-lg font-semibold text-white">Notification Settings</h2>

                                        <div className="space-y-4">
                                            <label className="flex items-center justify-between">
                                                <div>
                                                    <span className="text-white">Job complete emails</span>
                                                    <p className="text-sm text-gray-500">
                                                        Get notified when beatmap generation completes
                                                    </p>
                                                </div>
                                                <input
                                                    type="checkbox"
                                                    checked={preferences.custom_settings.emailJobComplete}
                                                    onChange={(e) => updateCustomSetting('emailJobComplete', e.target.checked)}
                                                    className="w-5 h-5 rounded bg-gray-700 border-gray-600 text-primary-500 focus:ring-primary-500"
                                                />
                                            </label>

                                            <label className="flex items-center justify-between">
                                                <div>
                                                    <span className="text-white">Job failed emails</span>
                                                    <p className="text-sm text-gray-500">
                                                        Get notified when a job fails
                                                    </p>
                                                </div>
                                                <input
                                                    type="checkbox"
                                                    checked={preferences.custom_settings.emailJobFailed}
                                                    onChange={(e) => updateCustomSetting('emailJobFailed', e.target.checked)}
                                                    className="w-5 h-5 rounded bg-gray-700 border-gray-600 text-primary-500 focus:ring-primary-500"
                                                />
                                            </label>

                                            <label className="flex items-center justify-between">
                                                <div>
                                                    <span className="text-white">Push notifications</span>
                                                    <p className="text-sm text-gray-500">
                                                        Receive browser push notifications
                                                    </p>
                                                </div>
                                                <input
                                                    type="checkbox"
                                                    checked={preferences.custom_settings.pushNotifications}
                                                    onChange={(e) => updateCustomSetting('pushNotifications', e.target.checked)}
                                                    className="w-5 h-5 rounded bg-gray-700 border-gray-600 text-primary-500 focus:ring-primary-500"
                                                />
                                            </label>

                                            <label className="flex items-center justify-between">
                                                <div>
                                                    <span className="text-white">Marketing emails</span>
                                                    <p className="text-sm text-gray-500">
                                                        Receive updates about new features
                                                    </p>
                                                </div>
                                                <input
                                                    type="checkbox"
                                                    checked={preferences.custom_settings.marketingEmails}
                                                    onChange={(e) => updateCustomSetting('marketingEmails', e.target.checked)}
                                                    className="w-5 h-5 rounded bg-gray-700 border-gray-600 text-primary-500 focus:ring-primary-500"
                                                />
                                            </label>
                                        </div>

                                        <button onClick={handleSavePreferences} disabled={isSaving} className="btn btn-primary">
                                            {isSaving ? 'Saving...' : 'Save Notifications'}
                                        </button>
                                    </div>
                                )}

                                {activeTab === 'privacy' && (
                                    <div className="card space-y-6">
                                        <h2 className="text-lg font-semibold text-white">Privacy & Training Data</h2>
                                        <p className="text-gray-400 text-sm">
                                            Control how your beatmap corrections contribute to improving our AI model.
                                            Your corrections help make BeatSight better for everyone.
                                        </p>

                                        {isLoadingConsent ? (
                                            <div className="text-gray-400">Loading...</div>
                                        ) : (
                                            <div className="space-y-4">
                                                <label className="flex items-center justify-between">
                                                    <div>
                                                        <span className="text-white">Contribute to model training</span>
                                                        <p className="text-sm text-gray-500">
                                                            Allow your beatmap corrections to be used for improving the AI.
                                                            Earn karma when your contributions are approved.
                                                        </p>
                                                    </div>
                                                    <input
                                                        type="checkbox"
                                                        checked={contributionConsent.consent_given}
                                                        onChange={(e) => setContributionConsent(prev => ({
                                                            ...prev,
                                                            consent_given: e.target.checked
                                                        }))}
                                                        className="w-5 h-5 rounded bg-gray-700 border-gray-600 text-primary-500 focus:ring-primary-500"
                                                    />
                                                </label>

                                                {contributionConsent.consent_given && (
                                                    <>
                                                        <label className="flex items-center justify-between">
                                                            <div>
                                                                <span className="text-white">Anonymous export</span>
                                                                <p className="text-sm text-gray-500">
                                                                    Export corrections without your username attached
                                                                </p>
                                                            </div>
                                                            <input
                                                                type="checkbox"
                                                                checked={contributionConsent.allow_anonymous_export}
                                                                onChange={(e) => setContributionConsent(prev => ({
                                                                    ...prev,
                                                                    allow_anonymous_export: e.target.checked
                                                                }))}
                                                                className="w-5 h-5 rounded bg-gray-700 border-gray-600 text-primary-500 focus:ring-primary-500"
                                                            />
                                                        </label>

                                                        <label className="flex items-center justify-between">
                                                            <div>
                                                                <span className="text-white">Public credit</span>
                                                                <p className="text-sm text-gray-500">
                                                                    Show your name in public contributor lists
                                                                </p>
                                                            </div>
                                                            <input
                                                                type="checkbox"
                                                                checked={contributionConsent.allow_public_credit}
                                                                onChange={(e) => setContributionConsent(prev => ({
                                                                    ...prev,
                                                                    allow_public_credit: e.target.checked
                                                                }))}
                                                                className="w-5 h-5 rounded bg-gray-700 border-gray-600 text-primary-500 focus:ring-primary-500"
                                                            />
                                                        </label>
                                                    </>
                                                )}

                                                <div className="pt-4 border-t border-gray-700">
                                                    <h3 className="text-white font-medium mb-2">Why contribute?</h3>
                                                    <ul className="text-sm text-gray-400 space-y-1 list-disc list-inside">
                                                        <li>Earn +15 karma for each approved correction</li>
                                                        <li>Help improve accuracy for everyone</li>
                                                        <li>Build reputation as a trusted contributor</li>
                                                    </ul>
                                                </div>
                                            </div>
                                        )}

                                        <button onClick={handleSaveContributionConsent} disabled={isSaving || isLoadingConsent} className="btn btn-primary">
                                            {isSaving ? 'Saving...' : 'Save Privacy Settings'}
                                        </button>
                                    </div>
                                )}

                                {activeTab === 'developer' && (
                                    <div className="card space-y-6">
                                        <h2 className="text-lg font-semibold text-white">Developer Settings</h2>
                                        <p className="text-gray-400 text-sm">
                                            Advanced settings for developers and power users. These settings sync across all your devices.
                                        </p>

                                        <div className="space-y-4">
                                            <label className="flex items-center justify-between">
                                                <div>
                                                    <span className="text-white">Developer Mode</span>
                                                    <p className="text-sm text-gray-500">
                                                        Enable console logging and debug information in production
                                                    </p>
                                                </div>
                                                <input
                                                    type="checkbox"
                                                    checked={developerMode}
                                                    onChange={(e) => handleDeveloperModeToggle(e.target.checked)}
                                                    className="w-5 h-5 rounded bg-gray-700 border-gray-600 text-primary-500 focus:ring-primary-500"
                                                />
                                            </label>

                                            {developerMode && (
                                                <div className="p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                                                    <p className="text-yellow-400 text-sm">
                                                        <strong>Developer Mode Active:</strong> Console logging is enabled.
                                                        Open your browser's developer tools (F12) to view logs.
                                                    </p>
                                                </div>
                                            )}
                                        </div>

                                        <button onClick={handleSavePreferences} disabled={isSaving} className="btn btn-primary">
                                            {isSaving ? 'Saving...' : 'Save Developer Settings'}
                                        </button>
                                    </div>
                                )}

                                {activeTab === 'danger' && (
                                    <div className="card border border-red-500/30 space-y-6">
                                        <h2 className="text-lg font-semibold text-red-400">Danger Zone</h2>

                                        <div className="space-y-4">
                                            <div className="p-4 bg-red-500/10 rounded-lg">
                                                <h3 className="text-white font-medium mb-2">Delete Account</h3>
                                                <p className="text-gray-400 text-sm mb-4">
                                                    Permanently delete your account and all associated data. This action cannot be
                                                    undone.
                                                </p>
                                                {showDeleteConfirm ? (
                                                    <div className="space-y-3">
                                                        <p className="text-red-400 text-sm">
                                                            Are you sure? Type "DELETE" to confirm.
                                                        </p>
                                                        <input
                                                            type="text"
                                                            placeholder="Type DELETE to confirm"
                                                            value={deleteConfirmText}
                                                            onChange={(e) => setDeleteConfirmText(e.target.value)}
                                                            className="input"
                                                        />
                                                        <input
                                                            type="password"
                                                            placeholder="Enter your password"
                                                            value={deletePassword}
                                                            onChange={(e) => setDeletePassword(e.target.value)}
                                                            className="input"
                                                        />
                                                        <div className="flex gap-3">
                                                            <button
                                                                onClick={handleDeleteAccount}
                                                                disabled={isSaving || deleteConfirmText !== 'DELETE'}
                                                                className="btn bg-red-600 hover:bg-red-700 text-white disabled:opacity-50"
                                                            >
                                                                {isSaving ? 'Deleting...' : 'Delete My Account'}
                                                            </button>
                                                            <button
                                                                onClick={() => {
                                                                    setShowDeleteConfirm(false)
                                                                    setDeleteConfirmText('')
                                                                    setDeletePassword('')
                                                                }}
                                                                className="btn btn-secondary"
                                                            >
                                                                Cancel
                                                            </button>
                                                        </div>
                                                    </div>
                                                ) : (
                                                    <button
                                                        onClick={() => setShowDeleteConfirm(true)}
                                                        className="btn bg-red-600 hover:bg-red-700 text-white"
                                                    >
                                                        Delete Account
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            </div>
        </div>
    )
}
