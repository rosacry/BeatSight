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
 * 
 * NOTE: We no longer call removeStaleOverlays() here because it was causing
 * "Failed to execute 'removeChild' on 'Node'" errors by removing DOM elements
 * that React was still managing. Let React handle its own cleanup.
 */
export function forceUnlockBodyScroll(): void {
    lockCount = 0
    document.body.style.overflow = ''
    document.body.style.pointerEvents = ''

    // Also clear any styles on document.documentElement (html element) that might block interaction
    document.documentElement.style.overflow = ''
    document.documentElement.style.pointerEvents = ''

    // NOTE: Do NOT call removeStaleOverlays() here - it interferes with React's DOM management
    // and causes "removeChild" errors during navigation and logout flows.
    // React will handle cleanup of portal elements through its normal unmount cycle.
}

/**
 * Remove stale overlay elements that might be blocking page interaction.
 * 
 * DEPRECATED: This function should NOT be called during normal navigation flows
 * as it can interfere with React's DOM management and cause "removeChild" errors.
 * 
 * Only use this as a last resort for debugging stuck states, not in production code.
 * React portals will clean themselves up through normal unmount cycles.
 */
export function removeStaleOverlays(): void {
    // This function is intentionally a no-op now.
    // The previous implementation was removing DOM elements that React was still managing,
    // causing "NotFoundError: Failed to execute 'removeChild' on 'Node'" errors.
    // 
    // The proper fix is to ensure modal components correctly unmount through React's
    // lifecycle methods rather than manually removing DOM elements.
    console.debug('[bodyScrollLock] removeStaleOverlays called but is now a no-op - let React handle cleanup')
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
