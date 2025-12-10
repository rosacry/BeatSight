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
 */
export function forceUnlockBodyScroll(): void {
    lockCount = 0
    document.body.style.overflow = ''
    document.body.style.pointerEvents = ''
}

/**
 * Get the current lock count (for debugging).
 */
export function getBodyScrollLockCount(): number {
    return lockCount
}
