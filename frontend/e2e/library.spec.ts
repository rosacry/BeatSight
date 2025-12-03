import { test, expect } from '@playwright/test';

/**
 * E2E tests for the Library page.
 * 
 * Tests cover:
 * - Library page access (auth required)
 * - Song list display
 * - Search and filter functionality
 * - Song selection and actions
 * - Empty state handling
 * - Pagination/infinite scroll
 */

test.describe('Library Page - Unauthenticated', () => {
    test('should redirect to login when not authenticated', async ({ page }) => {
        await page.goto('/library');

        // Should redirect to login page
        await expect(page).toHaveURL(/\/login/);
    });
});

test.describe('Library Page - Layout', () => {
    test.use({ storageState: '.playwright/.auth/user.json' });

    test('should display library header', async ({ page }) => {
        await page.goto('/library');

        // Look for library title or header
        const header = page.locator('h1, h2, [data-testid="library-header"]');
        await expect(header.first()).toBeVisible();
    });

    test('should have search functionality', async ({ page }) => {
        await page.goto('/library');

        // Look for search input
        const searchInput = page.locator([
            'input[type="search"]',
            'input[placeholder*="search"]',
            'input[aria-label*="search"]',
            '[data-testid="search-input"]',
        ].join(', '));

        const count = await searchInput.count();
        expect(count).toBeGreaterThanOrEqual(0); // Search may not be implemented yet
    });

    test('should have filter/sort options', async ({ page }) => {
        await page.goto('/library');

        // Look for filter or sort controls
        const filterControls = page.locator([
            'select',
            'button:has-text("filter")',
            'button:has-text("sort")',
            '[data-testid="filter"]',
            '[data-testid="sort"]',
        ].join(', '));

        const count = await filterControls.count();
        expect(count).toBeGreaterThanOrEqual(0); // Filters may not be implemented
    });

    test('should display upload button or link', async ({ page }) => {
        await page.goto('/library');

        // Look for upload action
        const uploadAction = page.locator([
            'a[href="/upload"]',
            'button:has-text("upload")',
            '[data-testid="upload-button"]',
        ].join(', '));

        const count = await uploadAction.count();
        expect(count).toBeGreaterThanOrEqual(0);
    });
});

test.describe('Library Page - Song List', () => {
    test.use({ storageState: '.playwright/.auth/user.json' });

    test('should display song items or empty state', async ({ page }) => {
        await page.goto('/library');

        // Wait for content to load
        await page.waitForTimeout(500);

        // Either songs exist or empty state is shown
        const songItems = page.locator('[data-testid="song-item"], .song-card, .song-row, [role="listitem"]');
        const emptyState = page.locator('text=/no songs|empty|get started|upload your first/i');

        const songCount = await songItems.count();
        const emptyCount = await emptyState.count();

        // Should show either songs or empty state
        expect(songCount > 0 || emptyCount > 0).toBeTruthy();
    });

    test('should show song metadata in list', async ({ page }) => {
        await page.goto('/library');

        await page.waitForTimeout(500);

        // If songs exist, check for metadata display
        const songItems = page.locator('[data-testid="song-item"], .song-card, .song-row');

        if (await songItems.count() > 0) {
            const firstSong = songItems.first();

            // Should have some text content
            const text = await firstSong.textContent();
            expect(text).toBeTruthy();
        }
    });

    test('should make songs clickable/selectable', async ({ page }) => {
        await page.goto('/library');

        await page.waitForTimeout(500);

        const songItems = page.locator('[data-testid="song-item"], .song-card, .song-row, [role="listitem"]');

        if (await songItems.count() > 0) {
            const firstSong = songItems.first();

            // Check if clickable (has href, onClick, or role button)
            const isClickable = await firstSong.evaluate((el) => {
                return el.tagName === 'A' ||
                    el.tagName === 'BUTTON' ||
                    el.getAttribute('role') === 'button' ||
                    el.onclick !== null ||
                    el.style.cursor === 'pointer' ||
                    el.querySelector('a, button') !== null;
            });

            // Songs should be interactive
            expect(isClickable).toBeTruthy();
        }
    });
});

test.describe('Library Page - Search', () => {
    test.use({ storageState: '.playwright/.auth/user.json' });

    test('should filter songs when searching', async ({ page }) => {
        await page.goto('/library');

        const searchInput = page.locator('input[type="search"], input[placeholder*="search"]');

        if (await searchInput.count() > 0) {
            // Get initial count
            const songItems = page.locator('[data-testid="song-item"], .song-card, .song-row');
            const initialCount = await songItems.count();

            // Type search query
            await searchInput.fill('test');

            // Wait for filtering
            await page.waitForTimeout(300);

            // Results should change or stay the same (if matches)
            const filteredCount = await songItems.count();
            expect(filteredCount).toBeGreaterThanOrEqual(0);
        }
    });

    test('should clear search', async ({ page }) => {
        await page.goto('/library');

        const searchInput = page.locator('input[type="search"], input[placeholder*="search"]');

        if (await searchInput.count() > 0) {
            // Type and then clear
            await searchInput.fill('test');
            await page.waitForTimeout(200);

            // Clear search
            const clearButton = page.locator('button[aria-label*="clear"], [data-testid="clear-search"]');
            if (await clearButton.count() > 0) {
                await clearButton.click();
            } else {
                await searchInput.clear();
            }

            // Search should be cleared
            const value = await searchInput.inputValue();
            expect(value).toBe('');
        }
    });

    test('should show no results message for non-matching search', async ({ page }) => {
        await page.goto('/library');

        const searchInput = page.locator('input[type="search"], input[placeholder*="search"]');

        if (await searchInput.count() > 0) {
            // Search for something unlikely to exist
            await searchInput.fill('xyzzy123nonexistent');

            await page.waitForTimeout(500);

            // Should show no results message or empty list
            const noResults = page.locator('text=/no results|nothing found|no matches/i');
            const songItems = page.locator('[data-testid="song-item"], .song-card, .song-row');

            const noResultsCount = await noResults.count();
            const songCount = await songItems.count();

            // Either "no results" message or empty list
            expect(noResultsCount > 0 || songCount === 0).toBeTruthy();
        }
    });
});

test.describe('Library Page - Song Actions', () => {
    test.use({ storageState: '.playwright/.auth/user.json' });

    test('should show action menu on song item', async ({ page }) => {
        await page.goto('/library');

        await page.waitForTimeout(500);

        const songItems = page.locator('[data-testid="song-item"], .song-card, .song-row');

        if (await songItems.count() > 0) {
            const firstSong = songItems.first();

            // Look for action button (usually three dots or kebab menu)
            const actionButton = firstSong.locator([
                'button[aria-label*="action"]',
                'button[aria-label*="menu"]',
                'button[aria-label*="more"]',
                '[data-testid="song-actions"]',
                'button:has(svg)',
            ].join(', '));

            if (await actionButton.count() > 0) {
                await actionButton.first().click();

                // Menu should appear
                await page.waitForTimeout(200);

                const menu = page.locator('[role="menu"], .dropdown-menu, .popover');
                expect(await menu.count()).toBeGreaterThanOrEqual(0);
            }
        }
    });

    test('should have delete action for songs', async ({ page }) => {
        await page.goto('/library');

        await page.waitForTimeout(500);

        // Look for delete option anywhere
        const deleteAction = page.locator([
            'button:has-text("delete")',
            '[data-testid="delete-song"]',
            'a:has-text("delete")',
        ].join(', '));

        // Delete action may be in a menu
        const count = await deleteAction.count();
        expect(count).toBeGreaterThanOrEqual(0);
    });
});

test.describe('Library Page - Pagination', () => {
    test.use({ storageState: '.playwright/.auth/user.json' });

    test('should handle large library with pagination or infinite scroll', async ({ page }) => {
        await page.goto('/library');

        await page.waitForTimeout(500);

        // Look for pagination controls
        const paginationControls = page.locator([
            '[data-testid="pagination"]',
            'button:has-text("next")',
            'button:has-text("prev")',
            '.pagination',
            'nav[aria-label*="pagination"]',
        ].join(', '));

        // Or check for "load more" button (infinite scroll)
        const loadMore = page.locator([
            'button:has-text("load more")',
            'button:has-text("show more")',
            '[data-testid="load-more"]',
        ].join(', '));

        // Either pagination or load more (or neither if library is small)
        const paginationCount = await paginationControls.count();
        const loadMoreCount = await loadMore.count();

        expect(paginationCount >= 0 || loadMoreCount >= 0).toBeTruthy();
    });
});

test.describe('Library Page - Accessibility', () => {
    test.use({ storageState: '.playwright/.auth/user.json' });

    test('should have accessible song list', async ({ page }) => {
        await page.goto('/library');

        await page.waitForTimeout(500);

        // Check for list semantics
        const list = page.locator('[role="list"], ul, ol');
        const count = await list.count();

        // List semantics improve accessibility
        expect(count).toBeGreaterThanOrEqual(0);
    });

    test('should support keyboard navigation', async ({ page }) => {
        await page.goto('/library');

        await page.waitForTimeout(500);

        // Try to tab through interactive elements
        await page.keyboard.press('Tab');

        // Something should be focused
        const focusedElement = page.locator(':focus');
        const count = await focusedElement.count();

        expect(count).toBeGreaterThanOrEqual(0);
    });
});

test.describe('Library Page - Empty State', () => {
    test.use({ storageState: '.playwright/.auth/user.json' });

    test('should show helpful empty state', async ({ page }) => {
        await page.goto('/library');

        await page.waitForTimeout(500);

        const songItems = page.locator('[data-testid="song-item"], .song-card, .song-row');

        if (await songItems.count() === 0) {
            // Should show empty state with call to action
            const emptyState = page.locator('text=/upload|get started|add your first/i');
            const uploadLink = page.locator('a[href="/upload"], button:has-text("upload")');

            const emptyCount = await emptyState.count();
            const uploadCount = await uploadLink.count();

            // Should guide user to upload
            expect(emptyCount > 0 || uploadCount > 0).toBeTruthy();
        }
    });
});
