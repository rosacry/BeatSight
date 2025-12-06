/**
 * Feature flags and A/B testing utilities.
 * 
 * Usage:
 *   if (isFeatureEnabled('new-dashboard')) {
 *     // Show new dashboard
 *   }
 * 
 * Flags can be set via:
 * 1. Environment variables (VITE_FF_xxx)
 * 2. URL parameters (?ff_xxx=true)
 * 3. LocalStorage (for persistence)
 * 4. API response (for server-controlled flags)
 * 
 * @module lib/featureFlags
 */

import { createLogger } from './logger'

const logger = createLogger('FeatureFlags')

/** Feature flag configuration */
interface FeatureFlagConfig {
    /** Flag is enabled */
    enabled: boolean
    /** Percentage of users to enable (0-100) */
    rolloutPercent?: number
    /** User segments to enable */
    segments?: string[]
    /** Expiration date for the flag */
    expiresAt?: Date
}

/** All feature flags */
type FeatureFlags = Record<string, FeatureFlagConfig | boolean>

/** Default feature flags (can be overridden) */
const DEFAULT_FLAGS: FeatureFlags = {
    // UI Features
    'new-dashboard': false,
    'dark-mode-v2': false,
    'compact-mode': false,

    // Beta Features
    'beta-timeline-editor': false,
    'beta-ai-suggestions': false,

    // Experiments
    'experiment-onboarding-flow': false,
    'experiment-pricing-page': false,
}

/** Storage key for persisted flags */
const STORAGE_KEY = 'beatsight_feature_flags'

/** Singleton instance */
let flags: FeatureFlags = { ...DEFAULT_FLAGS }
let userId: string | null = null

/**
 * Initialize feature flags.
 * Call this early in app startup.
 */
export function initFeatureFlags(options?: {
    userId?: string
    serverFlags?: FeatureFlags
}): void {
    userId = options?.userId ?? null

    // 1. Start with defaults
    flags = { ...DEFAULT_FLAGS }

    // 2. Load persisted flags from localStorage
    try {
        const stored = localStorage.getItem(STORAGE_KEY)
        if (stored) {
            const parsed = JSON.parse(stored) as FeatureFlags
            flags = { ...flags, ...parsed }
        }
    } catch {
        // Ignore parse errors
    }

    // 3. Override with environment variables
    Object.keys(flags).forEach(flag => {
        const envKey = `VITE_FF_${flag.toUpperCase().replace(/-/g, '_')}`
        const envValue = import.meta.env[envKey]
        if (envValue !== undefined) {
            flags[flag] = envValue === 'true'
        }
    })

    // 4. Override with URL parameters (for testing)
    if (typeof window !== 'undefined') {
        const params = new URLSearchParams(window.location.search)
        params.forEach((value, key) => {
            if (key.startsWith('ff_')) {
                const flagName = key.slice(3).replace(/_/g, '-')
                flags[flagName] = value === 'true' || value === '1'
            }
        })
    }

    // 5. Override with server-provided flags
    if (options?.serverFlags) {
        flags = { ...flags, ...options.serverFlags }
    }

    logger.debug('Feature flags initialized', { flags, userId })
}

/**
 * Check if a feature is enabled.
 */
export function isFeatureEnabled(flagName: string): boolean {
    const flag = flags[flagName]

    if (flag === undefined) {
        logger.warn(`Unknown feature flag: ${flagName}`)
        return false
    }

    if (typeof flag === 'boolean') {
        return flag
    }

    // Complex flag config
    const config = flag as FeatureFlagConfig

    // Check expiration
    if (config.expiresAt && new Date() > config.expiresAt) {
        return false
    }

    // Check rollout percentage
    if (config.rolloutPercent !== undefined && userId) {
        const hash = simpleHash(userId + flagName)
        const bucket = hash % 100
        if (bucket >= config.rolloutPercent) {
            return false
        }
    }

    return config.enabled
}

/**
 * Get all enabled flags.
 */
export function getEnabledFlags(): string[] {
    return Object.keys(flags).filter(isFeatureEnabled)
}

/**
 * Override a flag locally (persists to localStorage).
 */
export function setFlagOverride(flagName: string, enabled: boolean): void {
    flags[flagName] = enabled

    // Persist to localStorage
    try {
        const stored = localStorage.getItem(STORAGE_KEY)
        const persisted = stored ? JSON.parse(stored) : {}
        persisted[flagName] = enabled
        localStorage.setItem(STORAGE_KEY, JSON.stringify(persisted))
    } catch {
        // Ignore storage errors
    }

    logger.info(`Flag override set: ${flagName} = ${enabled}`)
}

/**
 * Clear all flag overrides.
 */
export function clearFlagOverrides(): void {
    localStorage.removeItem(STORAGE_KEY)
    flags = { ...DEFAULT_FLAGS }
    logger.info('Flag overrides cleared')
}

/**
 * Simple string hash for consistent bucketing.
 */
function simpleHash(str: string): number {
    let hash = 0
    for (let i = 0; i < str.length; i++) {
        const char = str.charCodeAt(i)
        hash = ((hash << 5) - hash) + char
        hash = hash & hash // Convert to 32-bit integer
    }
    return Math.abs(hash)
}

/**
 * React hook for feature flags.
 */
export function useFeatureFlag(flagName: string): boolean {
    // This could be made reactive with state + event listeners
    // For now, just return the current value
    return isFeatureEnabled(flagName)
}

/**
 * Development helper: Log all flags to console.
 */
export function debugFlags(): void {
    console.table(
        Object.entries(flags).map(([name, value]) => ({
            name,
            value: typeof value === 'boolean' ? value : (value as FeatureFlagConfig).enabled,
            enabled: isFeatureEnabled(name),
        }))
    )
}

// Export for testing
export const _internal = {
    flags,
    simpleHash,
}
