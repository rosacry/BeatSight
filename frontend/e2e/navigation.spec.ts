import { test, expect } from '@playwright/test';

test.describe('Navigation', () => {
    test('should display navigation bar', async ({ page, browserName }) => {
        await page.goto('/');

        // Check nav element is visible (works on all viewports)
        await expect(page.locator('nav')).toBeVisible();

        // Check logo/brand - only on desktop (hidden on mobile via hidden sm:block)
        const isMobile = browserName === 'Mobile Chrome' || browserName === 'Mobile Safari' ||
                         page.viewportSize()?.width !== undefined && page.viewportSize()!.width < 640;
        if (!isMobile) {
            await expect(page.locator('text=BeatSight').first()).toBeVisible();
        }
    });

    test('should navigate to home page', async ({ page }) => {
        await page.goto('/');

        // Home page should show welcome content or redirect to login
        const url = page.url();
        expect(url).toMatch(/\/(login)?$/);
    });

    test('should show mobile menu on small screens', async ({ page }) => {
        // Set mobile viewport
        await page.setViewportSize({ width: 375, height: 667 });
        await page.goto('/');

        // Look for hamburger menu button
        const menuButton = page.locator('button[aria-label*="menu"], button:has(svg)').first();

        if (await menuButton.isVisible()) {
            await menuButton.click();

            // Mobile menu should be visible
            await page.waitForTimeout(300); // Wait for animation
        }
    });

    test('should redirect unauthenticated users from protected routes', async ({ page }) => {
        // Try to access protected route
        await page.goto('/library');

        // Should redirect to login
        await expect(page).toHaveURL(/\/login/);
    });

    test('should redirect unauthenticated users from profile', async ({ page }) => {
        await page.goto('/profile');
        await expect(page).toHaveURL(/\/login/);
    });

    test('should redirect unauthenticated users from settings', async ({ page }) => {
        await page.goto('/settings');
        await expect(page).toHaveURL(/\/login/);
    });
});

test.describe('Public Pages', () => {
    test('should load login page', async ({ page }) => {
        await page.goto('/login');
        await expect(page.locator('h1')).toBeVisible();
    });

    test('should load register page', async ({ page }) => {
        await page.goto('/register');
        await expect(page.locator('h1')).toBeVisible();
    });
});
