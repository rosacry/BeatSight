/**
 * Analytics tracking utilities.
 * 
 * A provider-agnostic analytics layer that can be configured to use:
 * - Google Analytics (gtag)
 * - Mixpanel
 * - Amplitude
 * - PostHog
 * - Custom backend
 * 
 * Usage:
 *   import { analytics, trackEvent, trackPageView } from '@/lib/analytics'
 *   
 *   // Track a custom event
 *   trackEvent('button_click', { button_name: 'sign_up' })
 *   
 *   // Track page views (usually called by router)
 *   trackPageView('/dashboard')
 *   
 *   // Identify a user after login
 *   analytics.identify(userId, { email, plan })
 * 
 * @module lib/analytics
 */

import { createLogger } from './logger'

const logger = createLogger('Analytics')

/** Event properties type */
type EventProperties = Record<string, string | number | boolean | null | undefined>

/** User traits for identification */
interface UserTraits {
    email?: string
    name?: string
    plan?: string
    created_at?: string
    [key: string]: string | number | boolean | undefined
}

/** Analytics provider interface */
interface AnalyticsProvider {
    name: string
    trackEvent(eventName: string, properties?: EventProperties): void
    trackPageView(path: string, properties?: EventProperties): void
    identify(userId: string, traits?: UserTraits): void
    reset(): void
}

/** Console provider for development */
const consoleProvider: AnalyticsProvider = {
    name: 'console',
    trackEvent(eventName, properties) {
        logger.debug(`Event: ${eventName}`, properties)
    },
    trackPageView(path, properties) {
        logger.debug(`Page View: ${path}`, properties)
    },
    identify(userId, traits) {
        logger.debug(`Identify: ${userId}`, traits)
    },
    reset() {
        logger.debug('Analytics reset')
    },
}

/** Google Analytics provider */
function createGtagProvider(): AnalyticsProvider | null {
    const gtag = (window as unknown as { gtag?: (...args: unknown[]) => void }).gtag
    if (!gtag) return null

    return {
        name: 'gtag',
        trackEvent(eventName, properties) {
            gtag('event', eventName, properties)
        },
        trackPageView(path, properties) {
            gtag('event', 'page_view', { page_path: path, ...properties })
        },
        identify(userId, traits) {
            gtag('set', { user_id: userId, ...traits })
        },
        reset() {
            gtag('set', { user_id: null })
        },
    }
}

/** PostHog provider */
function createPostHogProvider(): AnalyticsProvider | null {
    const posthog = (window as unknown as {
        posthog?: {
            capture: (event: string, props?: EventProperties) => void
            identify: (userId: string, traits?: UserTraits) => void
            reset: () => void
        }
    }).posthog
    if (!posthog) return null

    return {
        name: 'posthog',
        trackEvent(eventName, properties) {
            posthog.capture(eventName, properties)
        },
        trackPageView(path, properties) {
            posthog.capture('$pageview', { $current_url: path, ...properties })
        },
        identify(userId, traits) {
            posthog.identify(userId, traits)
        },
        reset() {
            posthog.reset()
        },
    }
}

/** Mixpanel provider */
function createMixpanelProvider(): AnalyticsProvider | null {
    const mixpanel = (window as unknown as {
        mixpanel?: {
            track: (event: string, props?: EventProperties) => void
            identify: (userId: string) => void
            people: { set: (traits: UserTraits) => void }
            reset: () => void
        }
    }).mixpanel
    if (!mixpanel) return null

    return {
        name: 'mixpanel',
        trackEvent(eventName, properties) {
            mixpanel.track(eventName, properties)
        },
        trackPageView(path, properties) {
            mixpanel.track('Page View', { path, ...properties })
        },
        identify(userId, traits) {
            mixpanel.identify(userId)
            if (traits) mixpanel.people.set(traits)
        },
        reset() {
            mixpanel.reset()
        },
    }
}

/** Active providers */
let providers: AnalyticsProvider[] = []
let initialized = false
let currentUserId: string | null = null

/**
 * Initialize analytics with automatic provider detection.
 */
export function initAnalytics(options?: {
    /** Force console logging even in production */
    debug?: boolean
    /** Disable all tracking (for GDPR compliance) */
    disabled?: boolean
}): void {
    if (initialized) return

    if (options?.disabled) {
        logger.info('Analytics disabled')
        initialized = true
        return
    }

    providers = []

    // Always use console in development
    if (import.meta.env.DEV || options?.debug) {
        providers.push(consoleProvider)
    }

    // Auto-detect available providers
    if (typeof window !== 'undefined') {
        const gtag = createGtagProvider()
        if (gtag) providers.push(gtag)

        const posthog = createPostHogProvider()
        if (posthog) providers.push(posthog)

        const mixpanel = createMixpanelProvider()
        if (mixpanel) providers.push(mixpanel)
    }

    logger.info('Analytics initialized', {
        providers: providers.map(p => p.name)
    })
    initialized = true
}

/**
 * Track a custom event.
 */
export function trackEvent(
    eventName: string,
    properties?: EventProperties
): void {
    if (!initialized) initAnalytics()

    const enrichedProps = {
        ...properties,
        timestamp: new Date().toISOString(),
        url: typeof window !== 'undefined' ? window.location.href : undefined,
    }

    providers.forEach(provider => {
        try {
            provider.trackEvent(eventName, enrichedProps)
        } catch (error) {
            logger.error(`Failed to track event with ${provider.name}`, error)
        }
    })
}

/**
 * Track a page view.
 */
export function trackPageView(
    path: string,
    properties?: EventProperties
): void {
    if (!initialized) initAnalytics()

    const enrichedProps = {
        ...properties,
        referrer: typeof document !== 'undefined' ? document.referrer : undefined,
    }

    providers.forEach(provider => {
        try {
            provider.trackPageView(path, enrichedProps)
        } catch (error) {
            logger.error(`Failed to track page view with ${provider.name}`, error)
        }
    })
}

/**
 * Analytics singleton with advanced methods.
 */
export const analytics = {
    /**
     * Identify a user (call after login).
     */
    identify(userId: string, traits?: UserTraits): void {
        if (!initialized) initAnalytics()

        currentUserId = userId

        providers.forEach(provider => {
            try {
                provider.identify(userId, traits)
            } catch (error) {
                logger.error(`Failed to identify with ${provider.name}`, error)
            }
        })
    },

    /**
     * Reset analytics (call after logout).
     */
    reset(): void {
        if (!initialized) return

        currentUserId = null

        providers.forEach(provider => {
            try {
                provider.reset()
            } catch (error) {
                logger.error(`Failed to reset ${provider.name}`, error)
            }
        })
    },

    /**
     * Get current identified user ID.
     */
    getUserId(): string | null {
        return currentUserId
    },

    /**
     * Track timed event (returns a function to call when done).
     */
    startTimer(eventName: string, properties?: EventProperties): () => void {
        const startTime = performance.now()

        return () => {
            const duration = Math.round(performance.now() - startTime)
            trackEvent(eventName, {
                ...properties,
                duration_ms: duration,
            })
        }
    },
}

// Common event names for consistency
export const AnalyticsEvents = {
    // Auth
    SIGN_UP_STARTED: 'sign_up_started',
    SIGN_UP_COMPLETED: 'sign_up_completed',
    LOGIN: 'login',
    LOGOUT: 'logout',

    // Songs
    SONG_UPLOADED: 'song_uploaded',
    SONG_DELETED: 'song_deleted',
    SONG_PLAYED: 'song_played',

    // AI Jobs
    JOB_STARTED: 'ai_job_started',
    JOB_COMPLETED: 'ai_job_completed',
    JOB_FAILED: 'ai_job_failed',

    // Beatmaps
    BEATMAP_CREATED: 'beatmap_created',
    BEATMAP_DOWNLOADED: 'beatmap_downloaded',
    BEATMAP_EDITED: 'beatmap_edited',

    // Subscription
    SUBSCRIPTION_STARTED: 'subscription_started',
    SUBSCRIPTION_CANCELLED: 'subscription_cancelled',
    CREDITS_PURCHASED: 'credits_purchased',

    // Errors
    ERROR_OCCURRED: 'error_occurred',

    // Engagement
    FEATURE_USED: 'feature_used',
    BUTTON_CLICKED: 'button_clicked',
    FORM_SUBMITTED: 'form_submitted',
} as const
