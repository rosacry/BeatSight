/**
 * PWA install prompt component.
 * Shows a dismissible banner encouraging users to install the app.
 */

import { useState, useEffect } from 'react'
import { usePWAInstall } from '@/hooks/usePWA'

export function InstallPrompt() {
    const { isInstallable, install } = usePWAInstall()
    const [isDismissed, setIsDismissed] = useState(false)
    const [isInstalling, setIsInstalling] = useState(false)

    // Check if user has previously dismissed the prompt
    useEffect(() => {
        const dismissed = localStorage.getItem('pwa-install-dismissed')
        if (dismissed) {
            const dismissedAt = parseInt(dismissed, 10)
            // Show again after 7 days
            if (Date.now() - dismissedAt < 7 * 24 * 60 * 60 * 1000) {
                setIsDismissed(true)
            }
        }
    }, [])

    if (!isInstallable || isDismissed) {
        return null
    }

    const handleInstall = async () => {
        setIsInstalling(true)
        const success = await install()
        setIsInstalling(false)

        if (!success) {
            // User declined, don't show again for a while
            handleDismiss()
        }
    }

    const handleDismiss = () => {
        setIsDismissed(true)
        localStorage.setItem('pwa-install-dismissed', Date.now().toString())
    }

    return (
        <div className="fixed bottom-4 left-4 right-4 md:left-auto md:right-4 md:max-w-md z-50">
            <div className="bg-gray-800 rounded-xl shadow-xl border border-gray-700 p-4">
                <div className="flex items-start gap-4">
                    {/* App icon */}
                    <div className="flex-shrink-0 w-12 h-12 bg-primary-500 rounded-xl flex items-center justify-center">
                        <span className="text-white font-bold text-xl">B</span>
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                        <h3 className="text-white font-semibold">Install BeatSight</h3>
                        <p className="text-gray-400 text-sm mt-1">
                            Install our app for a better experience with offline support and quick access.
                        </p>

                        {/* Actions */}
                        <div className="flex items-center gap-3 mt-3">
                            <button
                                onClick={handleInstall}
                                disabled={isInstalling}
                                className="px-4 py-2 bg-primary-500 hover:bg-primary-600 disabled:bg-primary-500/50 text-white text-sm font-medium rounded-lg transition-colors"
                            >
                                {isInstalling ? 'Installing...' : 'Install'}
                            </button>
                            <button
                                onClick={handleDismiss}
                                className="px-4 py-2 text-gray-400 hover:text-white text-sm font-medium transition-colors"
                            >
                                Not now
                            </button>
                        </div>
                    </div>

                    {/* Close button */}
                    <button
                        onClick={handleDismiss}
                        className="flex-shrink-0 text-gray-500 hover:text-gray-300 transition-colors"
                    >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
            </div>
        </div>
    )
}

/**
 * Offline indicator component.
 * Shows when the user is offline.
 */
export function OfflineIndicator() {
    const [isOnline, setIsOnline] = useState(true)

    useEffect(() => {
        setIsOnline(navigator.onLine)

        const handleOnline = () => setIsOnline(true)
        const handleOffline = () => setIsOnline(false)

        window.addEventListener('online', handleOnline)
        window.addEventListener('offline', handleOffline)

        return () => {
            window.removeEventListener('online', handleOnline)
            window.removeEventListener('offline', handleOffline)
        }
    }, [])

    if (isOnline) {
        return null
    }

    return (
        <div className="fixed top-0 left-0 right-0 bg-yellow-500 text-yellow-900 text-center py-2 text-sm font-medium z-50">
            <span className="flex items-center justify-center gap-2">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 5.636a9 9 0 010 12.728m0 0l-2.829-2.829m2.829 2.829L21 21M15.536 8.464a5 5 0 010 7.072m0 0l-2.829-2.829m-4.243 2.829a4.978 4.978 0 01-1.414-2.83m-1.414 5.658a9 9 0 01-2.167-9.238m7.824 2.167a1 1 0 111.414 1.414m-1.414-1.414L3 3m8.293 8.293l1.414 1.414" />
                </svg>
                You're offline. Some features may be unavailable.
            </span>
        </div>
    )
}

/**
 * Update available notification.
 * Shows when a new version of the app is available.
 */
interface UpdateNotificationProps {
    onUpdate: () => void
}

export function UpdateNotification({ onUpdate }: UpdateNotificationProps) {
    return (
        <div className="fixed bottom-4 left-4 right-4 md:left-auto md:right-4 md:max-w-md z-50">
            <div className="bg-primary-600 rounded-xl shadow-xl p-4">
                <div className="flex items-center gap-4">
                    <svg className="w-6 h-6 text-white flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    <div className="flex-1">
                        <p className="text-white font-medium">Update available</p>
                        <p className="text-primary-200 text-sm">A new version is ready to install.</p>
                    </div>
                    <button
                        onClick={onUpdate}
                        className="px-4 py-2 bg-white text-primary-600 text-sm font-medium rounded-lg hover:bg-gray-100 transition-colors"
                    >
                        Update
                    </button>
                </div>
            </div>
        </div>
    )
}
