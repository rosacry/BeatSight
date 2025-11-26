/**
 * PWA utilities and hooks.
 * Handles service worker registration and install prompt.
 */

import { useState, useEffect, useCallback } from 'react'

interface BeforeInstallPromptEvent extends Event {
    prompt: () => Promise<void>
    userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

interface PWAStatus {
    isInstallable: boolean
    isInstalled: boolean
    isOnline: boolean
    isUpdateAvailable: boolean
}

/**
 * Register service worker.
 */
export async function registerServiceWorker(): Promise<ServiceWorkerRegistration | null> {
    if (!('serviceWorker' in navigator)) {
        console.log('[PWA] Service workers not supported')
        return null
    }

    try {
        const registration = await navigator.serviceWorker.register('/sw.js', {
            scope: '/',
        })

        console.log('[PWA] Service worker registered:', registration.scope)

        // Check for updates periodically
        setInterval(() => {
            registration.update()
        }, 60 * 60 * 1000) // Check every hour

        return registration
    } catch (error) {
        console.error('[PWA] Service worker registration failed:', error)
        return null
    }
}

/**
 * Hook for PWA install functionality.
 */
export function usePWAInstall() {
    const [installPrompt, setInstallPrompt] = useState<BeforeInstallPromptEvent | null>(null)
    const [isInstalled, setIsInstalled] = useState(false)

    useEffect(() => {
        // Check if already installed
        const checkInstalled = () => {
            const isStandalone = window.matchMedia('(display-mode: standalone)').matches
            const isIOSStandalone = (navigator as unknown as { standalone?: boolean }).standalone === true
            setIsInstalled(isStandalone || isIOSStandalone)
        }

        checkInstalled()

        // Listen for install prompt
        const handleBeforeInstallPrompt = (e: Event) => {
            e.preventDefault()
            setInstallPrompt(e as BeforeInstallPromptEvent)
        }

        // Listen for successful install
        const handleAppInstalled = () => {
            setIsInstalled(true)
            setInstallPrompt(null)
        }

        window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
        window.addEventListener('appinstalled', handleAppInstalled)

        return () => {
            window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
            window.removeEventListener('appinstalled', handleAppInstalled)
        }
    }, [])

    const install = useCallback(async (): Promise<boolean> => {
        if (!installPrompt) {
            return false
        }

        try {
            await installPrompt.prompt()
            const { outcome } = await installPrompt.userChoice

            if (outcome === 'accepted') {
                setInstallPrompt(null)
                return true
            }

            return false
        } catch {
            return false
        }
    }, [installPrompt])

    return {
        isInstallable: installPrompt !== null && !isInstalled,
        isInstalled,
        install,
    }
}

/**
 * Hook for online/offline status.
 */
export function useOnlineStatus() {
    const [isOnline, setIsOnline] = useState(navigator.onLine)

    useEffect(() => {
        const handleOnline = () => setIsOnline(true)
        const handleOffline = () => setIsOnline(false)

        window.addEventListener('online', handleOnline)
        window.addEventListener('offline', handleOffline)

        return () => {
            window.removeEventListener('online', handleOnline)
            window.removeEventListener('offline', handleOffline)
        }
    }, [])

    return isOnline
}

/**
 * Hook for service worker updates.
 */
export function useServiceWorkerUpdate() {
    const [updateAvailable, setUpdateAvailable] = useState(false)
    const [registration, setRegistration] = useState<ServiceWorkerRegistration | null>(null)

    useEffect(() => {
        if (!('serviceWorker' in navigator)) {
            return
        }

        const handleControllerChange = () => {
            // New service worker has taken control
            window.location.reload()
        }

        navigator.serviceWorker.addEventListener('controllerchange', handleControllerChange)

        // Check for existing registration
        navigator.serviceWorker.getRegistration().then((reg) => {
            if (reg) {
                setRegistration(reg)

                reg.addEventListener('updatefound', () => {
                    const newWorker = reg.installing
                    if (newWorker) {
                        newWorker.addEventListener('statechange', () => {
                            if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                                setUpdateAvailable(true)
                            }
                        })
                    }
                })
            }
        })

        return () => {
            navigator.serviceWorker.removeEventListener('controllerchange', handleControllerChange)
        }
    }, [])

    const applyUpdate = useCallback(() => {
        if (registration?.waiting) {
            registration.waiting.postMessage({ type: 'SKIP_WAITING' })
        }
    }, [registration])

    return {
        updateAvailable,
        applyUpdate,
    }
}

/**
 * Combined PWA status hook.
 */
export function usePWAStatus(): PWAStatus {
    const { isInstallable, isInstalled } = usePWAInstall()
    const isOnline = useOnlineStatus()
    const { updateAvailable } = useServiceWorkerUpdate()

    return {
        isInstallable,
        isInstalled,
        isOnline,
        isUpdateAvailable: updateAvailable,
    }
}
