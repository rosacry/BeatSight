/**
 * Tests for Application Configuration
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

describe('Config', () => {
    const originalWindow = global.window

    beforeEach(() => {
        vi.resetModules()
    })

    afterEach(() => {
        global.window = originalWindow
    })

    describe('getApiBaseUrl', () => {
        it('uses VITE_API_BASE_URL when set', async () => {
            vi.stubEnv('VITE_API_BASE_URL', 'https://custom-api.example.com')
            const { API_CONFIG } = await import('./config')
            expect(API_CONFIG.baseUrl).toBe('https://custom-api.example.com')
            vi.unstubAllEnvs()
        })

        it('returns empty string for development environment (API files add /api prefix)', async () => {
            vi.stubEnv('VITE_API_BASE_URL', '')
            // Mock window for non-production hostname
            Object.defineProperty(global, 'window', {
                value: { location: { hostname: 'localhost' } },
                writable: true,
            })

            const { API_CONFIG } = await import('./config')
            expect(API_CONFIG.baseUrl).toBe('')
            vi.unstubAllEnvs()
        })

        it('returns production API base for beatsight.io (API files add /api prefix)', async () => {
            vi.stubEnv('VITE_API_BASE_URL', '')
            Object.defineProperty(global, 'window', {
                value: { location: { hostname: 'beatsight.io' } },
                writable: true,
            })

            const { API_CONFIG } = await import('./config')
            expect(API_CONFIG.baseUrl).toBe('https://api.beatsight.io')
            vi.unstubAllEnvs()
        })

        it('returns production API base for www.beatsight.io (API files add /api prefix)', async () => {
            vi.stubEnv('VITE_API_BASE_URL', '')
            Object.defineProperty(global, 'window', {
                value: { location: { hostname: 'www.beatsight.io' } },
                writable: true,
            })

            const { API_CONFIG } = await import('./config')
            expect(API_CONFIG.baseUrl).toBe('https://api.beatsight.io')
            vi.unstubAllEnvs()
        })

        it('returns production API base for pages.dev domains (API files add /api prefix)', async () => {
            vi.stubEnv('VITE_API_BASE_URL', '')
            Object.defineProperty(global, 'window', {
                value: { location: { hostname: 'beatsight.pages.dev' } },
                writable: true,
            })

            const { API_CONFIG } = await import('./config')
            expect(API_CONFIG.baseUrl).toBe('https://api.beatsight.io')
            vi.unstubAllEnvs()
        })
    })

    describe('API_CONFIG', () => {
        it('has required configuration properties', async () => {
            const { API_CONFIG } = await import('./config')
            expect(API_CONFIG).toHaveProperty('baseUrl')
            expect(API_CONFIG).toHaveProperty('wsUrl')
        })

        it('has string baseUrl and wsUrl', async () => {
            const { API_CONFIG } = await import('./config')
            expect(typeof API_CONFIG.baseUrl).toBe('string')
            expect(typeof API_CONFIG.wsUrl).toBe('string')
        })
    })

    describe('APP_CONFIG', () => {
        it('has required configuration properties', async () => {
            const { APP_CONFIG } = await import('./config')
            expect(APP_CONFIG).toHaveProperty('name')
            expect(APP_CONFIG).toHaveProperty('maxUploadSize')
            expect(APP_CONFIG).toHaveProperty('supportedFormats')
        })

        it('has valid app name', async () => {
            const { APP_CONFIG } = await import('./config')
            expect(typeof APP_CONFIG.name).toBe('string')
            expect(APP_CONFIG.name.length).toBeGreaterThan(0)
        })

        it('has boolean debug and pwa flags', async () => {
            const { APP_CONFIG } = await import('./config')
            expect(typeof APP_CONFIG.debug).toBe('boolean')
            expect(typeof APP_CONFIG.pwaEnabled).toBe('boolean')
        })
    })

    describe('SERVICES_CONFIG', () => {
        it('has service configuration properties', async () => {
            const { SERVICES_CONFIG } = await import('./config')
            expect(SERVICES_CONFIG).toHaveProperty('sentryDsn')
            expect(SERVICES_CONFIG).toHaveProperty('analyticsId')
        })
    })

    describe('ENV', () => {
        it('has environment helper properties', async () => {
            const { ENV } = await import('./config')
            expect(ENV).toHaveProperty('isDevelopment')
            expect(ENV).toHaveProperty('isProduction')
            expect(ENV).toHaveProperty('mode')
        })

        it('has boolean environment flags', async () => {
            const { ENV } = await import('./config')
            expect(typeof ENV.isDevelopment).toBe('boolean')
            expect(typeof ENV.isProduction).toBe('boolean')
        })
    })
})
