/**
 * Body scroll lock utility.
 * 
 * Manages body overflow and pointer-events styles safely across multiple
 * modal/dialog components. Uses a counter to handle nested modals.
 * 
 * This prevents the "stuck" screen issue where body styles aren't cleaned up
 * properly during navigation (e.g., after logout).
 */

let lockCount = 0
let originalOverflow = ''
let originalPointerEvents = ''

/**
 * Lock body scroll and optionally pointer events.
 * Safe to call multiple times - uses a counter.
 */
export function lockBodyScroll(): void {
    if (lockCount === 0) {
        // Store original values before first lock
        originalOverflow = document.body.style.overflow
        originalPointerEvents = document.body.style.pointerEvents
        document.body.style.overflow = 'hidden'
    }
    lockCount++
}

/**
 * Unlock body scroll.
 * Only restores original styles when all locks are released.
 */
export function unlockBodyScroll(): void {
    if (lockCount > 0) {
        lockCount--
        if (lockCount === 0) {
            document.body.style.overflow = originalOverflow
            document.body.style.pointerEvents = originalPointerEvents
        }
    }
}

/**
 * Force unlock body scroll, ignoring the counter.
 * Use this in cleanup scenarios like navigation or error recovery.
 * Also removes any stale modal overlays that might be blocking interaction.
 */
export function forceUnlockBodyScroll(): void {
    lockCount = 0
    document.body.style.overflow = ''
    document.body.style.pointerEvents = ''

    // Also clear any styles on document.documentElement (html element) that might block interaction
    document.documentElement.style.overflow = ''
    document.documentElement.style.pointerEvents = ''

    // Remove any stale modal overlays that might be blocking interaction
    // These can occur when modals unmount during navigation without proper cleanup
    removeStaleOverlays()
}

/**
 * Remove stale overlay elements that might be blocking page interaction.
 * This catches cases where modal portals don't clean up properly during navigation.
 */
export function removeStaleOverlays(): void {
    // Find and remove any overlay elements that are direct children of body
    // These are typically from createPortal() that didn't unmount properly
    const overlaySelectors = [
        // High z-index fixed overlays that could block interaction
        'body > div[class*="fixed"][class*="inset-0"][class*="z-"]',
        'body > div[class*="fixed inset-0"]',
    ]

    overlaySelectors.forEach(selector => {
        try {
            const elements = document.querySelectorAll(selector)
            elements.forEach(el => {
                // Only remove if it looks like a stale modal overlay (has backdrop blur or high opacity bg)
                const style = window.getComputedStyle(el)
                const zIndex = parseInt(style.zIndex, 10)

                // Remove elements with very high z-index that are likely stale modal overlays
                // Check if they have the characteristics of a modal backdrop
                if (zIndex >= 50 && (
                    el.className.includes('backdrop') ||
                    el.className.includes('bg-black') ||
                    style.backdropFilter !== 'none' ||
                    style.backgroundColor.includes('rgba')
                )) {
                    // Check if this element is not part of an active React component tree
                    // by looking for data attributes that indicate it should stay
                    if (!el.hasAttribute('data-persistent') && !el.closest('[data-radix-portal]')) {
                        el.remove()
                    }
                }
            })
        } catch {
            // Ignore selector errors in case of invalid selectors
        }
    })
}

/**
 * Get the current lock count (for debugging).
 */
export function getBodyScrollLockCount(): number {
    return lockCount
}

/**
 * Check if the page is currently in a "stuck" state where body styles
 * might be blocking interaction. Useful for debugging.
 */
export function isBodyLocked(): boolean {
    return (
        lockCount > 0 ||
        document.body.style.overflow === 'hidden' ||
        document.body.style.pointerEvents === 'none'
    )
}
