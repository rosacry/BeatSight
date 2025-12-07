/**
 * Application Configuration
 * 
 * Centralized configuration pulled from environment variables.
 * All Vite env vars must be prefixed with VITE_ to be exposed to the client.
 */

/**
 * API Configuration
 */

// Detect production environment and use appropriate API URL
const getApiBaseUrl = () => {
    // Explicit env var takes priority
    if (import.meta.env.VITE_API_BASE_URL) {
        return import.meta.env.VITE_API_BASE_URL
    }
    // Production domains use the production API
    if (typeof window !== 'undefined' &&
        (window.location.hostname === 'beatsight.io' ||
            window.location.hostname === 'www.beatsight.io' ||
            window.location.hostname.endsWith('.pages.dev'))) {
        return 'https://api.beatsight.io'
    }
    // Development fallback
    return '/api'
}

export const API_CONFIG = {
    /**
     * Base URL for API requests.
     * - In development: '/api' (proxied by Vite to localhost:8000)
     * - In production: Full URL like 'https://api.beatsight.io'
     */
    baseUrl: getApiBaseUrl(),

    /**
     * WebSocket URL for real-time updates.
     * - In development: 'ws://localhost:8000/ws'
     * - In production: 'wss://api.beatsight.io/ws'
     */
    wsUrl: import.meta.env.VITE_WS_URL ||
        (import.meta.env.VITE_API_BASE_URL
            ? import.meta.env.VITE_API_BASE_URL.replace(/^http/, 'ws') + '/ws'
            : 'ws://localhost:8000/ws'),
} as const

/**
 * Application Settings
 */
export const APP_CONFIG = {
    name: import.meta.env.VITE_APP_NAME || 'BeatSight',

    /** Maximum file upload size in bytes (default: 100MB) */
    maxUploadSize: Number(import.meta.env.VITE_MAX_UPLOAD_SIZE) || 104857600,

    /** Supported audio file formats */
    supportedFormats: (import.meta.env.VITE_SUPPORTED_FORMATS || '.mp3,.wav,.flac,.ogg,.m4a').split(','),

    /** PWA features enabled */
    pwaEnabled: import.meta.env.VITE_ENABLE_PWA === 'true',

    /** Debug mode enabled */
    debug: import.meta.env.VITE_DEBUG === 'true',

    /** Use mock API responses */
    useMocks: import.meta.env.VITE_USE_MOCKS === 'true',
} as const

/**
 * Third-party Service Configuration
 */
export const SERVICES_CONFIG = {
    sentryDsn: import.meta.env.VITE_SENTRY_DSN || '',
    analyticsId: import.meta.env.VITE_ANALYTICS_ID || '',
} as const

/**
 * Environment helpers
 */
export const ENV = {
    isDevelopment: import.meta.env.DEV,
    isProduction: import.meta.env.PROD,
    mode: import.meta.env.MODE,
} as const

// Log configuration in development
if (ENV.isDevelopment && APP_CONFIG.debug) {
    console.log('[Config]', {
        apiBaseUrl: API_CONFIG.baseUrl,
        wsUrl: API_CONFIG.wsUrl,
        environment: ENV.mode,
    })
}
