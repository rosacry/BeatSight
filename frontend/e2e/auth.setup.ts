import { test as setup, expect } from '@playwright/test';
import path from 'path';

const authFile = path.join(__dirname, '../.playwright/.auth/user.json');

/**
 * Global setup: Create authenticated state for tests that need it.
 * This runs once before all tests and saves auth state to a file.
 */
setup('authenticate', async ({ page }) => {
    // For tests that don't need real backend, we'll mock the auth state
    // In a real scenario, you'd login here and save the session

    // Navigate to login page
    await page.goto('/login');

    // Check if we're on the login page
    await expect(page.locator('h1')).toContainText(/welcome back|sign in/i);

    // For now, we'll just verify the page loads correctly
    // Real auth would be:
    // await page.fill('input[type="email"]', 'test@example.com');
    // await page.fill('input[type="password"]', 'password123');
    // await page.click('button[type="submit"]');
    // await page.waitForURL('/library');

    // Save signed-in state (empty for now since we're not using real backend)
    await page.context().storageState({ path: authFile });
});
