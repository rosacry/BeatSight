/**
 * Type-safe localStorage wrapper with JSON serialization and SSR safety.
 * 
 * Usage:
 *   // Define a storage key with its type
 *   const authStorage = createStorage<AuthState>('beatsight-auth')
 *   
 *   // Get/set values
 *   const auth = authStorage.get() // AuthState | null
 *   authStorage.set({ user: {...}, accessToken: '...' })
 *   authStorage.remove()
 *   
 *   // Use the hook for reactive values
 *   const [auth, setAuth] = useLocalStorage('beatsight-auth', defaultAuth)
 * 
 * @module lib/storage
 */

import { useCallback, useEffect, useState } from 'react'

/** Check if we're in a browser environment */
const isBrowser = typeof window !== 'undefined'

/**
 * Storage options for customization.
 */
interface StorageOptions {
    /** Use sessionStorage instead of localStorage */
    session?: boolean
    /** Custom serializer (default: JSON.stringify) */
    serialize?: (value: unknown) => string
    /** Custom deserializer (default: JSON.parse) */
    deserialize?: (value: string) => unknown
}

/**
 * Create a type-safe storage accessor for a specific key.
 * 
 * @param key - The localStorage key
 * @param options - Optional configuration
 * @returns Object with get, set, remove methods
 * 
 * @example
 * interface UserPrefs {
 *   theme: 'light' | 'dark'
 *   volume: number
 * }
 * 
 * const prefsStorage = createStorage<UserPrefs>('user-prefs')
 * prefsStorage.set({ theme: 'dark', volume: 0.8 })
 * const prefs = prefsStorage.get() // UserPrefs | null
 */
export function createStorage<T>(key: string, options?: StorageOptions) {
    const storage = options?.session
        ? (isBrowser ? sessionStorage : null)
        : (isBrowser ? localStorage : null)

    const serialize = options?.serialize ?? JSON.stringify
    const deserialize = options?.deserialize ?? JSON.parse

    return {
        /**
         * Get the stored value.
         * @returns The stored value or null if not found/invalid
         */
        get(): T | null {
            if (!storage) return null

            try {
                const item = storage.getItem(key)
                return item ? (deserialize(item) as T) : null
            } catch {
                // Invalid JSON or other error
                return null
            }
        },

        /**
         * Set a value in storage.
         * @param value - The value to store
         */
        set(value: T): void {
            if (!storage) return

            try {
                storage.setItem(key, serialize(value))

                // Dispatch custom event for cross-tab sync
                window.dispatchEvent(new StorageEvent('storage', {
                    key,
                    newValue: serialize(value),
                    storageArea: storage,
                }))
            } catch (error) {
                // Storage full or other error
                console.error(`Failed to save to storage: ${key}`, error)
            }
        },

        /**
         * Remove the value from storage.
         */
        remove(): void {
            if (!storage) return

            storage.removeItem(key)

            // Dispatch custom event for cross-tab sync
            window.dispatchEvent(new StorageEvent('storage', {
                key,
                newValue: null,
                storageArea: storage,
            }))
        },

        /**
         * Check if the key exists in storage.
         */
        exists(): boolean {
            if (!storage) return false
            return storage.getItem(key) !== null
        },
    }
}

/**
 * React hook for localStorage with automatic sync across tabs.
 * 
 * @param key - The localStorage key
 * @param defaultValue - Default value if key doesn't exist
 * @param options - Optional configuration
 * @returns [value, setValue, removeValue] tuple
 * 
 * @example
 * function ThemeToggle() {
 *   const [theme, setTheme] = useLocalStorage('theme', 'light')
 *   
 *   return (
 *     <button onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}>
 *       Current: {theme}
 *     </button>
 *   )
 * }
 */
export function useLocalStorage<T>(
    key: string,
    defaultValue: T,
    options?: StorageOptions
): [T, (value: T | ((prev: T) => T)) => void, () => void] {
    const storage = createStorage<T>(key, options)

    // Initialize state with stored value or default
    const [storedValue, setStoredValue] = useState<T>(() => {
        return storage.get() ?? defaultValue
    })

    // Update localStorage when state changes
    const setValue = useCallback((value: T | ((prev: T) => T)) => {
        setStoredValue(prev => {
            const newValue = value instanceof Function ? value(prev) : value
            storage.set(newValue)
            return newValue
        })
    }, [storage])

    // Remove from localStorage
    const removeValue = useCallback(() => {
        storage.remove()
        setStoredValue(defaultValue)
    }, [storage, defaultValue])

    // Listen for changes from other tabs
    useEffect(() => {
        const handleStorage = (event: StorageEvent) => {
            if (event.key === key && event.storageArea === localStorage) {
                const newValue = event.newValue
                    ? (JSON.parse(event.newValue) as T)
                    : defaultValue
                setStoredValue(newValue)
            }
        }

        window.addEventListener('storage', handleStorage)
        return () => window.removeEventListener('storage', handleStorage)
    }, [key, defaultValue])

    return [storedValue, setValue, removeValue]
}

/**
 * React hook for sessionStorage.
 * Values are cleared when the tab is closed.
 */
export function useSessionStorage<T>(
    key: string,
    defaultValue: T
): [T, (value: T | ((prev: T) => T)) => void, () => void] {
    return useLocalStorage(key, defaultValue, { session: true })
}

// Pre-configured storage keys for BeatSight
export const storageKeys = {
    // Auth
    auth: 'beatsight-auth',
    accessToken: 'access_token',
    refreshToken: 'refresh_token',

    // User preferences
    theme: 'beatsight:theme',
    volume: 'beatsight:volume',
    developerMode: 'beatsight:developerMode',

    // Feature flags
    featureFlags: 'beatsight_feature_flags',

    // PWA
    pwaInstallDismissed: 'pwa-install-dismissed',

    // Recently viewed
    recentSongs: 'beatsight:recent-songs',
} as const

/**
 * Clear all BeatSight-related storage.
 * Useful for logout or data reset.
 */
export function clearAllStorage(): void {
    if (!isBrowser) return

    Object.values(storageKeys).forEach(key => {
        localStorage.removeItem(key)
    })
}
