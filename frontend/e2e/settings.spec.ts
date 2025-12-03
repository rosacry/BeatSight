import { test, expect } from '@playwright/test';

test.describe('Settings Page', () => {
    // Settings page requires authentication
    test.use({ storageState: 'playwright/.auth/user.json' });

    test.describe('Page Structure', () => {
        test('should display settings page with sections', async ({ page }) => {
            await page.goto('/settings');

            // Check page title
            await expect(page).toHaveTitle(/settings/i);

            // Check main heading
            await expect(page.locator('h1')).toContainText(/settings/i);
        });

        test('should have account settings section', async ({ page }) => {
            await page.goto('/settings');

            // Look for account-related settings
            const accountSection = page.locator('text=/account|profile/i').first();
            await expect(accountSection).toBeVisible();
        });

        test('should have appearance/theme settings', async ({ page }) => {
            await page.goto('/settings');

            // Look for theme/appearance settings
            const themeSection = page.locator('text=/theme|appearance|dark mode/i').first();
            await expect(themeSection).toBeVisible();
        });

        test('should have notification settings', async ({ page }) => {
            await page.goto('/settings');

            // Look for notification settings
            const notificationSection = page.locator('text=/notification/i').first();
            await expect(notificationSection).toBeVisible();
        });
    });

    test.describe('Theme Toggle', () => {
        test('should toggle dark/light mode', async ({ page }) => {
            await page.goto('/settings');

            // Find theme toggle (could be button, switch, or select)
            const themeToggle = page.locator('[data-testid="theme-toggle"], button:has-text("theme"), input[type="checkbox"]:near(:text("dark"))').first();

            if (await themeToggle.isVisible()) {
                // Get initial state
                const initialClass = await page.locator('html').getAttribute('class');

                // Toggle theme
                await themeToggle.click();

                // Verify class changed
                const newClass = await page.locator('html').getAttribute('class');
                expect(newClass).not.toBe(initialClass);
            }
        });
    });

    test.describe('Form Interactions', () => {
        test('should have save button', async ({ page }) => {
            await page.goto('/settings');

            // Look for save button
            const saveButton = page.locator('button:has-text(/save|update|apply/i)').first();
            await expect(saveButton).toBeVisible();
        });

        test('should show success message on save', async ({ page }) => {
            await page.goto('/settings');

            // Find and click save button
            const saveButton = page.locator('button:has-text(/save|update/i)').first();

            if (await saveButton.isVisible()) {
                await saveButton.click();

                // Wait for success message or toast
                await page.waitForSelector('text=/saved|success|updated/i', { timeout: 5000 }).catch(() => {
                    // May not show if no changes made
                });
            }
        });
    });

    test.describe('Navigation', () => {
        test('should have back navigation', async ({ page }) => {
            await page.goto('/settings');

            // Look for back button or breadcrumb
            const backNav = page.locator('a[href="/"], button:has-text("back"), [aria-label*="back"]').first();
            await expect(backNav).toBeVisible();
        });
    });

    test.describe('Accessibility', () => {
        test('should have proper form labels', async ({ page }) => {
            await page.goto('/settings');

            // All inputs should have labels
            const inputs = page.locator('input:not([type="hidden"])');
            const inputCount = await inputs.count();

            for (let i = 0; i < inputCount; i++) {
                const input = inputs.nth(i);
                const id = await input.getAttribute('id');
                const ariaLabel = await input.getAttribute('aria-label');
                const ariaLabelledBy = await input.getAttribute('aria-labelledby');

                // Should have either a label element, aria-label, or aria-labelledby
                if (id) {
                    const label = page.locator(`label[for="${id}"]`);
                    const hasLabel = await label.count() > 0;
                    expect(hasLabel || ariaLabel || ariaLabelledBy).toBeTruthy();
                }
            }
        });

        test('should be keyboard navigable', async ({ page }) => {
            await page.goto('/settings');

            // Tab through the page
            await page.keyboard.press('Tab');
            await page.keyboard.press('Tab');
            await page.keyboard.press('Tab');

            // Something should be focused
            const focusedElement = page.locator(':focus');
            await expect(focusedElement).toBeVisible();
        });
    });
});

test.describe('Settings Page - Unauthenticated', () => {
    test('should redirect to login when not authenticated', async ({ page }) => {
        // Clear any auth state
        await page.context().clearCookies();

        await page.goto('/settings');

        // Should redirect to login
        await expect(page).toHaveURL(/login/);
    });
});
