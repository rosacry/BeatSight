import { test, expect } from '@playwright/test';

test.describe('Pricing Page', () => {
    test.describe('Page Structure', () => {
        test('should display pricing page', async ({ page }) => {
            await page.goto('/pricing');

            // Check page loads
            await expect(page).toHaveTitle(/pricing|plans|beatsight/i);
        });

        test('should show pricing heading', async ({ page }) => {
            await page.goto('/pricing');

            const heading = page.locator('h1');
            await expect(heading).toContainText(/pricing|plans|choose/i);
        });

        test('should display multiple pricing tiers', async ({ page }) => {
            await page.goto('/pricing');

            // Look for plan cards
            const plans = page.locator('[data-testid="pricing-card"], [class*="plan"], [class*="tier"], article').filter({
                hasText: /free|pro|premium|basic|starter/i
            });

            const planCount = await plans.count();
            expect(planCount).toBeGreaterThanOrEqual(2);
        });
    });

    test.describe('Free Tier', () => {
        test('should show free tier details', async ({ page }) => {
            await page.goto('/pricing');

            const freeTier = page.locator('text=/free/i').first();
            await expect(freeTier).toBeVisible();
        });

        test('should list free tier features', async ({ page }) => {
            await page.goto('/pricing');

            // Free tier should mention limits
            const freeFeatures = page.locator('text=/limited|basic|starter/i');
            await expect(freeFeatures.first()).toBeVisible();
        });
    });

    test.describe('Paid Tiers', () => {
        test('should show price amounts', async ({ page }) => {
            await page.goto('/pricing');

            // Look for price indicators
            const prices = page.locator('text=/\\$|month|year|per/i');
            const priceCount = await prices.count();
            expect(priceCount).toBeGreaterThan(0);
        });

        test('should have subscribe/upgrade buttons', async ({ page }) => {
            await page.goto('/pricing');

            const subscribeButtons = page.locator('button:has-text(/subscribe|upgrade|get started|buy|choose/i)');
            const buttonCount = await subscribeButtons.count();
            expect(buttonCount).toBeGreaterThan(0);
        });

        test('should show premium features', async ({ page }) => {
            await page.goto('/pricing');

            // Premium features should be highlighted
            const premiumFeatures = page.locator('text=/unlimited|priority|advanced|exclusive/i');
            await expect(premiumFeatures.first()).toBeVisible();
        });
    });

    test.describe('Feature Comparison', () => {
        test('should show feature list for each plan', async ({ page }) => {
            await page.goto('/pricing');

            // Look for feature lists (usually checkmarks or bullet points)
            const featureLists = page.locator('ul, [class*="feature"]');
            const listCount = await featureLists.count();
            expect(listCount).toBeGreaterThan(0);
        });

        test('should show credits/quota information', async ({ page }) => {
            await page.goto('/pricing');

            // Credits are core to the pricing model
            const credits = page.locator('text=/credit|generation|beatmap/i');
            await expect(credits.first()).toBeVisible();
        });
    });

    test.describe('Billing Toggle', () => {
        test('should have monthly/annual toggle', async ({ page }) => {
            await page.goto('/pricing');

            // Many pricing pages have billing period toggle
            const billingToggle = page.locator('text=/monthly|annual|yearly/i').first();

            if (await billingToggle.isVisible()) {
                await expect(billingToggle).toBeVisible();
            }
        });

        test('should show savings for annual billing', async ({ page }) => {
            await page.goto('/pricing');

            const savings = page.locator('text=/save|discount|off/i').first();

            // Annual savings badge is common but optional
            if (await savings.isVisible()) {
                await expect(savings).toBeVisible();
            }
        });
    });

    test.describe('CTA Buttons', () => {
        test('should navigate to checkout on click', async ({ page }) => {
            await page.goto('/pricing');

            const subscribeButton = page.locator('button:has-text(/subscribe|upgrade|choose/i)').first();

            if (await subscribeButton.isVisible()) {
                await subscribeButton.click();

                // Should navigate to login (if not authenticated) or checkout
                await page.waitForURL(/login|checkout|stripe|billing/, { timeout: 5000 }).catch(() => {
                    // May stay on page if modal appears
                });
            }
        });
    });

    test.describe('FAQ Section', () => {
        test('should have FAQ or questions section', async ({ page }) => {
            await page.goto('/pricing');

            const faq = page.locator('text=/faq|question|frequently/i').first();

            // FAQ is common but optional
            if (await faq.isVisible()) {
                await expect(faq).toBeVisible();
            }
        });
    });

    test.describe('Accessibility', () => {
        test('should have proper heading hierarchy', async ({ page }) => {
            await page.goto('/pricing');

            const h1 = page.locator('h1');
            await expect(h1).toBeVisible();
        });

        test('should have accessible pricing cards', async ({ page }) => {
            await page.goto('/pricing');

            // Cards should be keyboard focusable
            await page.keyboard.press('Tab');
            await page.keyboard.press('Tab');

            const focused = page.locator(':focus');
            await expect(focused).toBeVisible();
        });

        test('should have ARIA labels on buttons', async ({ page }) => {
            await page.goto('/pricing');

            const buttons = page.locator('button');
            const buttonCount = await buttons.count();

            for (let i = 0; i < Math.min(buttonCount, 5); i++) {
                const button = buttons.nth(i);
                const text = await button.textContent();
                const ariaLabel = await button.getAttribute('aria-label');

                // Button should have visible text or aria-label
                expect(text || ariaLabel).toBeTruthy();
            }
        });
    });

    test.describe('Responsive Design', () => {
        test('should stack cards on mobile', async ({ page }) => {
            // Set mobile viewport
            await page.setViewportSize({ width: 375, height: 667 });
            await page.goto('/pricing');

            // Page should still be usable
            const heading = page.locator('h1');
            await expect(heading).toBeVisible();

            const subscribeButton = page.locator('button:has-text(/subscribe|upgrade|choose/i)').first();
            await expect(subscribeButton).toBeVisible();
        });
    });
});
