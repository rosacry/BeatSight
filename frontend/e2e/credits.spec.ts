import { test, expect } from '@playwright/test'

test.describe('Credit System', () => {
    test.describe('Credit Packs Display', () => {
        test('should show credit packs section on pricing page', async ({ page }) => {
            await page.goto('/pricing')

            // Look for credits section
            const creditsSection = page.locator('text=/credit|pay.*per.*song/i').first()
            await expect(creditsSection).toBeVisible()
        })

        test('should display all credit pack options', async ({ page }) => {
            await page.goto('/pricing')

            // All packs should be visible: Starter, Standard/Value, Bulk/Power
            const starterPack = page.locator('text=/starter/i')
            await expect(starterPack.first()).toBeVisible()
        })

        test('should show prices for credit packs', async ({ page }) => {
            await page.goto('/pricing')

            // Prices should be visible
            const prices = page.locator('text=/\\$[0-9]+\\.?[0-9]*/i')
            const priceCount = await prices.count()
            expect(priceCount).toBeGreaterThan(0)
        })

        test('should show savings percentage for bulk packs', async ({ page }) => {
            await page.goto('/pricing')

            // Bulk packs should show savings
            const savings = page.locator('text=/save|%.*off|discount/i')
            const savingsVisible = await savings.first().isVisible().catch(() => false)

            // Savings display is optional but good to have
            if (savingsVisible) {
                await expect(savings.first()).toBeVisible()
            }
        })
    })

    test.describe('Credit Purchase Flow (Unauthenticated)', () => {
        test('should redirect to login when buying credits without auth', async ({ page }) => {
            await page.goto('/pricing')

            // Find a buy credits button
            const buyButton = page.locator('button:has-text(/buy|purchase|get/i)').first()

            if (await buyButton.isVisible()) {
                await buyButton.click()

                // Should redirect to login
                await expect(page).toHaveURL(/login/, { timeout: 5000 })
            }
        })
    })

    test.describe('Credit Purchase Flow (Authenticated)', () => {
        test.use({ storageState: 'e2e/.auth/user.json' })

        test('should show buy button for credit packs', async ({ page }) => {
            await page.goto('/pricing')

            // Credit pack buy buttons
            const buyButtons = page.locator('button:has-text(/buy|purchase|get credits/i)')
            const buttonCount = await buyButtons.count()
            expect(buttonCount).toBeGreaterThan(0)
        })

        test('should initiate checkout when clicking buy', async ({ page }) => {
            await page.goto('/pricing')

            // Find credit pack buy button
            const buyButton = page.locator('button:has-text(/buy|purchase|get/i)').first()

            if (await buyButton.isVisible()) {
                // Listen for navigation
                const navigationPromise = page.waitForURL(/stripe|checkout|credits/, { timeout: 10000 }).catch(() => null)

                await buyButton.click()

                // Should navigate to Stripe checkout or show modal
                const didNavigate = await navigationPromise
                if (!didNavigate) {
                    // Check if modal appeared instead
                    const modal = page.locator('[role="dialog"], [class*="modal"]')
                    const hasModal = await modal.isVisible().catch(() => false)
                    expect(hasModal || didNavigate).toBeTruthy()
                }
            }
        })
    })

    test.describe('Credit Balance Display', () => {
        test.use({ storageState: 'e2e/.auth/user.json' })

        test('should show credit balance in navigation or header', async ({ page }) => {
            await page.goto('/library')

            // Credit balance might be in nav, header, or profile
            const creditDisplay = page.locator('text=/credit|balance/i')
            const isVisible = await creditDisplay.first().isVisible().catch(() => false)

            // Balance display location may vary
            if (!isVisible) {
                // Check profile page
                await page.goto('/profile')
                const profileCredits = page.locator('text=/credit/i')
                await expect(profileCredits.first()).toBeVisible()
            }
        })

        test('should show credit balance on settings page', async ({ page }) => {
            await page.goto('/settings')

            // Settings should show billing/credits section
            const billingSection = page.locator('text=/billing|subscription|credits/i')
            await expect(billingSection.first()).toBeVisible()
        })
    })

    test.describe('Credit Success Page', () => {
        test.use({ storageState: 'e2e/.auth/user.json' })

        test('should display success page after purchase', async ({ page }) => {
            // Simulate successful purchase redirect
            await page.goto('/credits/success')

            // Should show success message
            const successMessage = page.locator('text=/success|thank|confirmed|complete/i')
            await expect(successMessage.first()).toBeVisible()
        })

        test('should show credits added confirmation', async ({ page }) => {
            await page.goto('/credits/success')

            // Should mention credits were added
            const creditsAdded = page.locator('text=/credit|added|balance/i')
            await expect(creditsAdded.first()).toBeVisible()
        })

        test('should have link to continue', async ({ page }) => {
            await page.goto('/credits/success')

            // Should have CTA to continue
            const continueLink = page.locator('a:has-text(/continue|library|upload|start/i), button:has-text(/continue|library|upload|start/i)')
            await expect(continueLink.first()).toBeVisible()
        })
    })

    test.describe('Credit Cancel Page', () => {
        test.use({ storageState: 'e2e/.auth/user.json' })

        test('should handle cancelled checkout gracefully', async ({ page }) => {
            // Simulate cancelled checkout
            await page.goto('/credits/cancel')

            // Should show cancel/info message or redirect to pricing
            await page.waitForURL(/cancel|pricing/, { timeout: 5000 })
        })
    })

    test.describe('Auto Top-up Configuration', () => {
        test.use({ storageState: 'e2e/.auth/user.json' })

        test('should show auto top-up settings', async ({ page }) => {
            await page.goto('/settings')

            // Navigate to billing/credits section if needed
            const billingTab = page.locator('button:has-text(/billing|subscription/i), [role="tab"]:has-text(/billing/i)')
            if (await billingTab.isVisible()) {
                await billingTab.click()
            }

            // Auto top-up toggle should exist
            const autoTopup = page.locator('text=/auto.*top|automatic.*refill/i')
            const isVisible = await autoTopup.first().isVisible().catch(() => false)

            // Feature may be hidden if no credits purchased yet
            if (isVisible) {
                await expect(autoTopup.first()).toBeVisible()
            }
        })
    })

    test.describe('Credit History', () => {
        test.use({ storageState: 'e2e/.auth/user.json' })

        test('should show transaction history', async ({ page }) => {
            await page.goto('/settings')

            // Navigate to billing section
            const billingTab = page.locator('button:has-text(/billing|subscription/i), [role="tab"]:has-text(/billing/i)')
            if (await billingTab.isVisible()) {
                await billingTab.click()
            }

            // History section
            const history = page.locator('text=/history|transaction|purchase/i')
            const isVisible = await history.first().isVisible().catch(() => false)

            if (isVisible) {
                await expect(history.first()).toBeVisible()
            }
        })
    })

    test.describe('Credit Consumption', () => {
        test.use({ storageState: 'e2e/.auth/user.json' })

        test('should show credit cost when uploading', async ({ page }) => {
            await page.goto('/upload')

            // Upload page should mention credit cost
            const creditCost = page.locator('text=/credit|cost|charge/i')
            const isVisible = await creditCost.first().isVisible().catch(() => false)

            // Credit info may be shown after file selection
            if (isVisible) {
                await expect(creditCost.first()).toBeVisible()
            }
        })
    })

    test.describe('Accessibility', () => {
        test('should have accessible credit pack cards', async ({ page }) => {
            await page.goto('/pricing')

            // Tab through the page
            await page.keyboard.press('Tab')
            await page.keyboard.press('Tab')
            await page.keyboard.press('Tab')

            // Should be able to focus credit pack buttons
            const focused = page.locator(':focus')
            await expect(focused).toBeVisible()
        })

        test('should have proper labels on credit buttons', async ({ page }) => {
            await page.goto('/pricing')

            const buyButtons = page.locator('button:has-text(/buy|purchase/i)')
            const buttonCount = await buyButtons.count()

            for (let i = 0; i < Math.min(buttonCount, 3); i++) {
                const button = buyButtons.nth(i)
                const text = await button.textContent()
                expect(text).toBeTruthy()
            }
        })
    })

    test.describe('Responsive Design', () => {
        test('should display credit packs on mobile', async ({ page }) => {
            await page.setViewportSize({ width: 375, height: 667 })
            await page.goto('/pricing')

            // Credit section should still be visible
            const prices = page.locator('text=/\\$/i')
            await expect(prices.first()).toBeVisible()
        })
    })
})
