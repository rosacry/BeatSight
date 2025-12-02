/**
 * User settings page.
 * Account settings, preferences, and notification configuration.
 * Persists to backend via /api/users/me and /api/sync/preferences
 */

import { useState, useEffect, useCallback } from 'react'
import { useAuthStore } from '@/stores/authStore'
import { createLogger, getDeveloperModeEnabled, enableDeveloperMode, disableDeveloperMode } from '@/lib/logger'
import type { UserPreferences } from '@/types/sync'
import { DEFAULT_CUSTOM_SETTINGS } from '@/types/sync'

const logger = createLogger('Settings')
const API_BASE = '/api'

type SettingsTab = 'account' | 'preferences' | 'notifications' | 'developer' | 'danger'

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

    const response = await fetch(`${API_BASE}${endpoint}`, {
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
    const [currentPassword, setCurrentPassword] = useState('')
    const [newPassword, setNewPassword] = useState('')
    const [confirmPassword, setConfirmPassword] = useState('')

    // Developer mode state (synced with server via custom_settings)
    const [developerMode, setDeveloperMode] = useState(getDeveloperModeEnabled())

    // Preferences from server
    const [preferences, setPreferences] = useState<Preferences | null>(null)

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
    }, [loadPreferences])

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

    const handlePasswordChange = async (e: React.FormEvent) => {
        e.preventDefault()
        if (newPassword !== confirmPassword) {
            setError('Passwords do not match')
            return
        }
        if (newPassword.length < 8) {
            setError('Password must be at least 8 characters')
            return
        }
        if (!accessToken) return

        setIsSaving(true)
        setError(null)
        try {
            await apiRequest('/users/me/password', {
                method: 'POST',
                body: JSON.stringify({
                    current_password: currentPassword,
                    new_password: newPassword,
                }),
            }, accessToken)
            setCurrentPassword('')
            setNewPassword('')
            setConfirmPassword('')
            setSuccessMessage('Password changed successfully!')
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to change password')
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
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id)}
                            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${activeTab === tab.id
                                ? 'bg-gray-700 text-white'
                                : 'text-gray-400 hover:text-white hover:bg-gray-800'
                                }`}
                        >
                            {tab.icon}
                            {tab.label}
                        </button>
                    ))}
                </nav>

                {/* Content */}
                <div className="flex-1">
                    {isLoading ? (
                        <div className="card flex items-center justify-center py-12">
                            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
                        </div>
                    ) : (
                        <>
                            {activeTab === 'account' && (
                                <div className="space-y-6">
                                    {/* Profile Section */}
                                    <div className="card">
                                        <h2 className="text-lg font-semibold text-white mb-4">Profile</h2>
                                        <div className="space-y-4">
                                            <div>
                                                <label className="block text-sm font-medium text-gray-300 mb-2">
                                                    Display Name
                                                </label>
                                                <input
                                                    type="text"
                                                    value={displayName}
                                                    onChange={(e) => setDisplayName(e.target.value)}
                                                    className="input"
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-sm font-medium text-gray-300 mb-2">
                                                    Email
                                                </label>
                                                <input
                                                    type="email"
                                                    value={user?.email || ''}
                                                    disabled
                                                    className="input opacity-50 cursor-not-allowed"
                                                />
                                                <p className="text-xs text-gray-500 mt-1">
                                                    Contact support to change your email
                                                </p>
                                            </div>
                                            <button
                                                onClick={handleSaveProfile}
                                                disabled={isSaving}
                                                className="btn btn-primary"
                                            >
                                                {isSaving ? 'Saving...' : 'Save Changes'}
                                            </button>
                                        </div>
                                    </div>

                                    {/* Password Section */}
                                    <div className="card">
                                        <h2 className="text-lg font-semibold text-white mb-4">Change Password</h2>
                                        <form onSubmit={handlePasswordChange} className="space-y-4">
                                            <div>
                                                <label className="block text-sm font-medium text-gray-300 mb-2">
                                                    Current Password
                                                </label>
                                                <input
                                                    type="password"
                                                    value={currentPassword}
                                                    onChange={(e) => setCurrentPassword(e.target.value)}
                                                    className="input"
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-sm font-medium text-gray-300 mb-2">
                                                    New Password
                                                </label>
                                                <input
                                                    type="password"
                                                    value={newPassword}
                                                    onChange={(e) => setNewPassword(e.target.value)}
                                                    className="input"
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-sm font-medium text-gray-300 mb-2">
                                                    Confirm New Password
                                                </label>
                                                <input
                                                    type="password"
                                                    value={confirmPassword}
                                                    onChange={(e) => setConfirmPassword(e.target.value)}
                                                    className="input"
                                                />
                                            </div>
                                            <button type="submit" className="btn btn-secondary">
                                                Update Password
                                            </button>
                                        </form>
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
                        </>
                    )}
                </div>
            </div>
        </div>
    )
}
