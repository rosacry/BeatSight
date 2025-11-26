/**
 * User settings page.
 * Account settings, preferences, and notification configuration.
 */

import { useState } from 'react'
import { useAuthStore } from '@/stores/authStore'

type SettingsTab = 'account' | 'preferences' | 'notifications' | 'danger'

interface Preferences {
    autoGenerateBeatmap: boolean
    defaultQuantization: string
    defaultSensitivity: number
    showConfidenceOverlay: boolean
    enableOfflineMode: boolean
    theme: 'dark' | 'light' | 'system'
}

interface NotificationSettings {
    emailJobComplete: boolean
    emailJobFailed: boolean
    pushNotifications: boolean
    marketingEmails: boolean
}

export function SettingsPage() {
    const user = useAuthStore((state) => state.user)
    const logout = useAuthStore((state) => state.logout)
    const [activeTab, setActiveTab] = useState<SettingsTab>('account')
    const [isSaving, setIsSaving] = useState(false)
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

    // Form state
    const [displayName, setDisplayName] = useState(user?.display_name || '')
    const [currentPassword, setCurrentPassword] = useState('')
    const [newPassword, setNewPassword] = useState('')
    const [confirmPassword, setConfirmPassword] = useState('')

    const [preferences, setPreferences] = useState<Preferences>({
        autoGenerateBeatmap: true,
        defaultQuantization: '16th',
        defaultSensitivity: 0.5,
        showConfidenceOverlay: true,
        enableOfflineMode: false,
        theme: 'dark',
    })

    const [notifications, setNotifications] = useState<NotificationSettings>({
        emailJobComplete: true,
        emailJobFailed: true,
        pushNotifications: true,
        marketingEmails: false,
    })

    const handleSave = async () => {
        setIsSaving(true)
        // TODO: Implement actual save to backend
        await new Promise((resolve) => setTimeout(resolve, 1000))
        setIsSaving(false)
    }

    const handlePasswordChange = async (e: React.FormEvent) => {
        e.preventDefault()
        if (newPassword !== confirmPassword) {
            alert('Passwords do not match')
            return
        }
        // TODO: Implement password change
        setCurrentPassword('')
        setNewPassword('')
        setConfirmPassword('')
    }

    const handleDeleteAccount = async () => {
        // TODO: Implement account deletion
        logout()
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
                                        onClick={handleSave}
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

                    {activeTab === 'preferences' && (
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
                                        checked={preferences.autoGenerateBeatmap}
                                        onChange={(e) =>
                                            setPreferences((p) => ({ ...p, autoGenerateBeatmap: e.target.checked }))
                                        }
                                        className="w-5 h-5 rounded bg-gray-700 border-gray-600 text-primary-500 focus:ring-primary-500"
                                    />
                                </label>

                                <div>
                                    <label className="block text-sm font-medium text-gray-300 mb-2">
                                        Default Quantization
                                    </label>
                                    <select
                                        value={preferences.defaultQuantization}
                                        onChange={(e) =>
                                            setPreferences((p) => ({ ...p, defaultQuantization: e.target.value }))
                                        }
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
                                        Detection Sensitivity ({Math.round(preferences.defaultSensitivity * 100)}%)
                                    </label>
                                    <input
                                        type="range"
                                        min="0"
                                        max="1"
                                        step="0.05"
                                        value={preferences.defaultSensitivity}
                                        onChange={(e) =>
                                            setPreferences((p) => ({
                                                ...p,
                                                defaultSensitivity: parseFloat(e.target.value),
                                            }))
                                        }
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
                                        checked={preferences.showConfidenceOverlay}
                                        onChange={(e) =>
                                            setPreferences((p) => ({ ...p, showConfidenceOverlay: e.target.checked }))
                                        }
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
                                        checked={preferences.enableOfflineMode}
                                        onChange={(e) =>
                                            setPreferences((p) => ({ ...p, enableOfflineMode: e.target.checked }))
                                        }
                                        className="w-5 h-5 rounded bg-gray-700 border-gray-600 text-primary-500 focus:ring-primary-500"
                                    />
                                </label>
                            </div>

                            <button onClick={handleSave} disabled={isSaving} className="btn btn-primary">
                                {isSaving ? 'Saving...' : 'Save Preferences'}
                            </button>
                        </div>
                    )}

                    {activeTab === 'notifications' && (
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
                                        checked={notifications.emailJobComplete}
                                        onChange={(e) =>
                                            setNotifications((n) => ({ ...n, emailJobComplete: e.target.checked }))
                                        }
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
                                        checked={notifications.emailJobFailed}
                                        onChange={(e) =>
                                            setNotifications((n) => ({ ...n, emailJobFailed: e.target.checked }))
                                        }
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
                                        checked={notifications.pushNotifications}
                                        onChange={(e) =>
                                            setNotifications((n) => ({ ...n, pushNotifications: e.target.checked }))
                                        }
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
                                        checked={notifications.marketingEmails}
                                        onChange={(e) =>
                                            setNotifications((n) => ({ ...n, marketingEmails: e.target.checked }))
                                        }
                                        className="w-5 h-5 rounded bg-gray-700 border-gray-600 text-primary-500 focus:ring-primary-500"
                                    />
                                </label>
                            </div>

                            <button onClick={handleSave} disabled={isSaving} className="btn btn-primary">
                                {isSaving ? 'Saving...' : 'Save Notifications'}
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
                                                className="input"
                                            />
                                            <div className="flex gap-3">
                                                <button
                                                    onClick={handleDeleteAccount}
                                                    className="btn bg-red-600 hover:bg-red-700 text-white"
                                                >
                                                    Delete My Account
                                                </button>
                                                <button
                                                    onClick={() => setShowDeleteConfirm(false)}
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
                </div>
            </div>
        </div>
    )
}
