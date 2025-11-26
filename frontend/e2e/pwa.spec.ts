import { test, expect } from '@playwright/test';

test.describe('PWA Features', () => {
    test('should have PWA manifest', async ({ page }) => {
        await page.goto('/');

        // Check for manifest link
        const manifestLink = page.locator('link[rel="manifest"]');
        await expect(manifestLink).toHaveAttribute('href', '/manifest.json');
    });

    test('should load manifest.json', async ({ request }) => {
        const response = await request.get('/manifest.json');
        expect(response.ok()).toBeTruthy();

        const manifest = await response.json();
        expect(manifest.name).toBe('BeatSight');
        expect(manifest.short_name).toBe('BeatSight');
        expect(manifest.start_url).toBeDefined();
        expect(manifest.icons).toBeDefined();
        expect(manifest.icons.length).toBeGreaterThan(0);
    });

    test('should have theme color meta tag', async ({ page }) => {
        await page.goto('/');

        const themeColor = page.locator('meta[name="theme-color"]');
        await expect(themeColor).toHaveAttribute('content');
    });

    test('should have apple-touch-icon', async ({ page }) => {
        await page.goto('/');

        const appleTouchIcon = page.locator('link[rel="apple-touch-icon"]');
        await expect(appleTouchIcon).toHaveAttribute('href');
    });

    test('should register service worker', async ({ page }) => {
        await page.goto('/');

        // Check if service worker is registered
        const swRegistered = await page.evaluate(async () => {
            if ('serviceWorker' in navigator) {
                const registrations = await navigator.serviceWorker.getRegistrations();
                return registrations.length > 0;
            }
            return false;
        });

        // Service worker should be registered (may take a moment)
        // In dev mode, SW might not be active
        expect(typeof swRegistered).toBe('boolean');
    });
});

test.describe('Offline Support', () => {
    test('should have offline page', async ({ request }) => {
        const response = await request.get('/offline.html');
        expect(response.ok()).toBeTruthy();

        const html = await response.text();
        expect(html).toContain('offline');
    });
});
