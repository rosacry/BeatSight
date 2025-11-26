import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright E2E test configuration for BeatSight web app.
 * @see https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
    testDir: './e2e',

    // Run tests in parallel
    fullyParallel: true,

    // Fail the build on CI if you accidentally left test.only in the source code
    forbidOnly: !!process.env.CI,

    // Retry on CI only
    retries: process.env.CI ? 2 : 0,

    // Opt out of parallel tests on CI
    workers: process.env.CI ? 1 : undefined,

    // Reporter to use
    reporter: [
        ['html', { open: 'never' }],
        ['list'],
    ],

    // Shared settings for all projects
    use: {
        // Base URL to use in actions like `await page.goto('/')`
        baseURL: 'http://localhost:3000',

        // Collect trace when retrying the failed test
        trace: 'on-first-retry',

        // Screenshot on failure
        screenshot: 'only-on-failure',

        // Video on failure
        video: 'on-first-retry',
    },

    // Configure projects for major browsers
    projects: [
        // Setup project - runs before all tests
        {
            name: 'setup',
            testMatch: /.*\.setup\.ts/,
        },

        {
            name: 'chromium',
            use: {
                ...devices['Desktop Chrome'],
            },
            dependencies: ['setup'],
        },

        // Uncomment to add more browsers
        // {
        //   name: 'firefox',
        //   use: { ...devices['Desktop Firefox'] },
        //   dependencies: ['setup'],
        // },
        // {
        //   name: 'webkit',
        //   use: { ...devices['Desktop Safari'] },
        //   dependencies: ['setup'],
        // },

        // Mobile viewport
        {
            name: 'mobile-chrome',
            use: { ...devices['Pixel 5'] },
            dependencies: ['setup'],
        },
    ],

    // Run local dev server before starting the tests
    webServer: {
        command: 'npm run dev',
        url: 'http://localhost:3000',
        reuseExistingServer: !process.env.CI,
        timeout: 120 * 1000,
    },
});
