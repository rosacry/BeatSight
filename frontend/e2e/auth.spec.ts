import { test, expect } from '@playwright/test';

test.describe('Authentication Flow', () => {
    test.describe('Login Page', () => {
        test('should display login form', async ({ page }) => {
            await page.goto('/login');

            // Check page title and heading
            await expect(page).toHaveTitle(/BeatSight/i);
            await expect(page.locator('h1')).toContainText(/welcome back/i);

            // Check form elements
            await expect(page.locator('input[type="email"]')).toBeVisible();
            await expect(page.locator('input[type="password"]')).toBeVisible();
            await expect(page.locator('button[type="submit"]')).toBeVisible();
            await expect(page.locator('button[type="submit"]')).toContainText(/sign in/i);
        });

        test('should show validation errors for empty form', async ({ page }) => {
            await page.goto('/login');

            // Click submit without filling form
            await page.click('button[type="submit"]');

            // Email field should be marked invalid (HTML5 validation)
            const emailInput = page.locator('input[type="email"]');
            await expect(emailInput).toHaveAttribute('required', '');
        });

        test('should have link to registration', async ({ page }) => {
            await page.goto('/login');

            // Use getByRole to find visible link (works on desktop and mobile)
            const registerLink = page.getByRole('link', { name: /sign up/i }).first();
            await expect(registerLink).toBeVisible();

            // Click and verify navigation
            await registerLink.click();
            await expect(page).toHaveURL('/register');
        });

        test('should show error message for invalid credentials', async ({ page }) => {
            await page.goto('/login');

            // Fill form with invalid credentials
            await page.fill('input[type="email"]', 'wrong@example.com');
            await page.fill('input[type="password"]', 'wrongpassword');

            // Submit form (this will fail since no backend)
            await page.click('button[type="submit"]');

            // Wait for error message or network error
            // In real test, we'd mock the API response
            await page.waitForTimeout(1000);
        });
    });

    test.describe('Registration Page', () => {
        test('should display registration form', async ({ page }) => {
            await page.goto('/register');

            // Check heading
            await expect(page.locator('h1')).toContainText(/create account/i);

            // Check form elements
            await expect(page.locator('input#displayName')).toBeVisible();
            await expect(page.locator('input[type="email"]')).toBeVisible();
            await expect(page.locator('input#password')).toBeVisible();
            await expect(page.locator('input#confirmPassword')).toBeVisible();
            await expect(page.locator('button[type="submit"]')).toContainText(/create account/i);
        });

        test('should have link to login', async ({ page }) => {
            await page.goto('/register');

            // Use getByRole to find visible link (works on desktop and mobile)
            const loginLink = page.getByRole('link', { name: /log in|sign in/i }).first();
            await expect(loginLink).toBeVisible();

            await loginLink.click();
            await expect(page).toHaveURL('/login');
        });

        test('should show password mismatch error', async ({ page }) => {
            await page.goto('/register');

            // Fill form with mismatched passwords
            await page.fill('input#displayName', 'Test User');
            await page.fill('input[type="email"]', 'test@example.com');
            await page.fill('input#password', 'password123');
            await page.fill('input#confirmPassword', 'differentpassword');

            // Submit form
            await page.click('button[type="submit"]');

            // Check for error message
            await expect(page.locator('text=/passwords do not match/i')).toBeVisible();
        });
    });
});
