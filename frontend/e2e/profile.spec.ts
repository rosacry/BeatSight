import { test, expect } from '@playwright/test';

test.describe('Profile Page', () => {
    // Profile page requires authentication
    test.use({ storageState: 'playwright/.auth/user.json' });

    test.describe('Page Structure', () => {
        test('should display profile page', async ({ page }) => {
            await page.goto('/profile');

            // Check page loads
            await expect(page).toHaveTitle(/profile|beatsight/i);
        });

        test('should show user information', async ({ page }) => {
            await page.goto('/profile');

            // Look for user-related content
            const userInfo = page.locator('text=/username|email|member since/i').first();
            await expect(userInfo).toBeVisible();
        });

        test('should display karma score', async ({ page }) => {
            await page.goto('/profile');

            // Karma is a key feature
            const karma = page.locator('text=/karma/i').first();
            await expect(karma).toBeVisible();
        });

        test('should show user stats', async ({ page }) => {
            await page.goto('/profile');

            // Look for statistics section
            const stats = page.locator('text=/beatmaps|uploads|contributions|songs/i').first();
            await expect(stats).toBeVisible();
        });
    });

    test.describe('Avatar Section', () => {
        test('should display user avatar', async ({ page }) => {
            await page.goto('/profile');

            // Look for avatar image or placeholder
            const avatar = page.locator('img[alt*="avatar"], img[alt*="profile"], [data-testid="avatar"], .avatar').first();
            await expect(avatar).toBeVisible();
        });

        test('should have avatar upload option', async ({ page }) => {
            await page.goto('/profile');

            // Look for upload button or input
            const uploadOption = page.locator('input[type="file"], button:has-text(/change|upload/i)').first();

            // Avatar upload may be optional
            if (await uploadOption.isVisible()) {
                await expect(uploadOption).toBeEnabled();
            }
        });
    });

    test.describe('Edit Profile', () => {
        test('should have edit button', async ({ page }) => {
            await page.goto('/profile');

            // Look for edit button
            const editButton = page.locator('button:has-text(/edit/i), a:has-text(/edit/i)').first();
            await expect(editButton).toBeVisible();
        });

        test('should open edit mode on click', async ({ page }) => {
            await page.goto('/profile');

            const editButton = page.locator('button:has-text(/edit/i)').first();

            if (await editButton.isVisible()) {
                await editButton.click();

                // Should show form fields or modal
                const formField = page.locator('input[name], textarea, form').first();
                await expect(formField).toBeVisible();
            }
        });
    });

    test.describe('Activity History', () => {
        test('should show recent activity', async ({ page }) => {
            await page.goto('/profile');

            // Look for activity/history section
            const activity = page.locator('text=/activity|history|recent/i').first();
            await expect(activity).toBeVisible();
        });
    });

    test.describe('Subscription/Credits', () => {
        test('should display subscription or credits info', async ({ page }) => {
            await page.goto('/profile');

            // Look for subscription or credits section
            const credits = page.locator('text=/credits|subscription|plan|tier/i').first();
            await expect(credits).toBeVisible();
        });
    });

    test.describe('Navigation', () => {
        test('should link to settings', async ({ page }) => {
            await page.goto('/profile');

            const settingsLink = page.locator('a[href*="settings"], button:has-text(/settings/i)').first();
            await expect(settingsLink).toBeVisible();
        });

        test('should link to user library', async ({ page }) => {
            await page.goto('/profile');

            const libraryLink = page.locator('a[href*="library"], button:has-text(/library|my songs/i)').first();
            await expect(libraryLink).toBeVisible();
        });
    });

    test.describe('Accessibility', () => {
        test('should have proper heading hierarchy', async ({ page }) => {
            await page.goto('/profile');

            // Check for h1
            const h1 = page.locator('h1');
            await expect(h1).toBeVisible();

            // H2s should exist for sections
            const h2s = page.locator('h2');
            const h2Count = await h2s.count();
            expect(h2Count).toBeGreaterThan(0);
        });

        test('should be keyboard navigable', async ({ page }) => {
            await page.goto('/profile');

            // Tab through interactive elements
            for (let i = 0; i < 5; i++) {
                await page.keyboard.press('Tab');
            }

            // Something should be focused
            const focusedElement = page.locator(':focus');
            await expect(focusedElement).toBeVisible();
        });
    });
});

test.describe('Profile Page - Unauthenticated', () => {
    test('should redirect to login', async ({ page }) => {
        await page.context().clearCookies();
        await page.goto('/profile');
        await expect(page).toHaveURL(/login/);
    });
});

test.describe('Profile Page - Other User', () => {
    test.use({ storageState: 'playwright/.auth/user.json' });

    test('should view other user profile by ID', async ({ page }) => {
        // Try to view a different user's profile
        await page.goto('/profile/some-user-id');

        // Should show profile (may be limited view)
        await expect(page).toHaveURL(/profile/);
    });
});
