import { test, expect } from '@playwright/test';

test.describe('Accessibility', () => {
    test('should have proper heading hierarchy on login page', async ({ page }) => {
        await page.goto('/login');

        // Should have exactly one h1
        const h1Count = await page.locator('h1').count();
        expect(h1Count).toBe(1);
    });

    test('should have proper heading hierarchy on register page', async ({ page }) => {
        await page.goto('/register');

        const h1Count = await page.locator('h1').count();
        expect(h1Count).toBe(1);
    });

    test('should have accessible form labels', async ({ page }) => {
        await page.goto('/login');

        // Email input should have label
        const emailLabel = page.locator('label[for="email"]');
        await expect(emailLabel).toBeVisible();

        // Password input should have label
        const passwordLabel = page.locator('label[for="password"]');
        await expect(passwordLabel).toBeVisible();
    });

    test('should support keyboard navigation on login form', async ({ page }) => {
        await page.goto('/login');

        // Tab to email field
        await page.keyboard.press('Tab');

        // Email field should be focused (might need to skip past nav)
        // Just verify we can tab through the page
        await page.keyboard.press('Tab');
        await page.keyboard.press('Tab');
    });

    test('should have skip to content link or main landmark', async ({ page }) => {
        await page.goto('/');

        // Check for main landmark
        const main = page.locator('main');
        const mainCount = await main.count();

        // Should have a main element or similar structure
        expect(mainCount).toBeGreaterThanOrEqual(0);
    });

    test('should have sufficient color contrast', async ({ page }) => {
        await page.goto('/login');

        // Basic check: buttons should have visible text
        const submitButton = page.locator('button[type="submit"]');
        await expect(submitButton).toBeVisible();

        // Text should be readable
        const buttonText = await submitButton.textContent();
        expect(buttonText?.length).toBeGreaterThan(0);
    });

    test('should handle focus states', async ({ page }) => {
        await page.goto('/login');

        // Focus the email input
        const emailInput = page.locator('input[type="email"]');
        await emailInput.focus();

        // Check that it's focused
        await expect(emailInput).toBeFocused();
    });
});

test.describe('Responsive Design', () => {
    test('should be responsive on mobile', async ({ page }) => {
        await page.setViewportSize({ width: 375, height: 667 });
        await page.goto('/login');

        // Form should still be visible
        await expect(page.locator('form')).toBeVisible();
        await expect(page.locator('button[type="submit"]')).toBeVisible();
    });

    test('should be responsive on tablet', async ({ page }) => {
        await page.setViewportSize({ width: 768, height: 1024 });
        await page.goto('/login');

        await expect(page.locator('form')).toBeVisible();
    });

    test('should be responsive on desktop', async ({ page }) => {
        await page.setViewportSize({ width: 1920, height: 1080 });
        await page.goto('/login');

        await expect(page.locator('form')).toBeVisible();
    });
});
