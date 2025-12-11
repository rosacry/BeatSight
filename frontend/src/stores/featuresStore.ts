/**
 * Features store for caching backend feature flags.
 * 
 * Fetches feature flags once on app load and caches them to avoid
 * repeated requests to disabled endpoints (which show console errors).
 */

import { create } from 'zustand'
import { API_CONFIG } from '@/lib/config'

interface Features {
    cloud_sync: boolean
    phone_verification: boolean
    two_factor_auth: boolean
    stripe_payments: boolean
}

interface FeaturesState {
    features: Features | null
    isLoading: boolean
    error: string | null
    fetchFeatures: () => Promise<void>
}

const defaultFeatures: Features = {
    cloud_sync: false,
    phone_verification: false,
    two_factor_auth: true,
    stripe_payments: false,
}

export const useFeaturesStore = create<FeaturesState>((set, get) => ({
    features: null,
    isLoading: false,
    error: null,

    fetchFeatures: async () => {
        // Don't refetch if already loaded or loading
        if (get().features || get().isLoading) return

        set({ isLoading: true, error: null })

        try {
            const response = await fetch(`${API_CONFIG.baseUrl}/health/features`)

            if (!response.ok) {
                // Fall back to defaults if endpoint doesn't exist
                set({ features: defaultFeatures, isLoading: false })
                return
            }

            const features = await response.json()
            set({ features, isLoading: false })
        } catch (err) {
            // Fall back to defaults on network error
            console.debug('Could not fetch features, using defaults')
            set({
                features: defaultFeatures,
                isLoading: false,
                error: err instanceof Error ? err.message : 'Failed to fetch features'
            })
        }
    },
}))

/**
 * Hook to check if a specific feature is enabled.
 * Returns false if features haven't loaded yet.
 */
export function useFeature(feature: keyof Features): boolean {
    const features = useFeaturesStore((state) => state.features)
    return features?.[feature] ?? false
}

/**
 * Hook to check if cloud sync is enabled.
 */
export function useCloudSync(): boolean {
    return useFeature('cloud_sync')
}
