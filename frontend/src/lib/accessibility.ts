/**
 * Accessibility utilities and constants
 * Provides helpers for keyboard navigation, screen readers, and focus management
 */

/**
 * Key codes for keyboard navigation
 */
export const KEYS = {
    ENTER: 'Enter',
    SPACE: ' ',
    ESCAPE: 'Escape',
    TAB: 'Tab',
    ARROW_UP: 'ArrowUp',
    ARROW_DOWN: 'ArrowDown',
    ARROW_LEFT: 'ArrowLeft',
    ARROW_RIGHT: 'ArrowRight',
    HOME: 'Home',
    END: 'End',
} as const

/**
 * Handle click-like keyboard events (Enter and Space)
 */
export function handleKeyboardClick(
    handler: () => void
): React.KeyboardEventHandler {
    return (event) => {
        if (event.key === KEYS.ENTER || event.key === KEYS.SPACE) {
            event.preventDefault()
            handler()
        }
    }
}

/**
 * Generate unique ID for ARIA relationships
 */
let idCounter = 0
export function generateId(prefix: string): string {
    return `${prefix}-${++idCounter}`
}

/**
 * Announce message to screen readers
 */
export function announceToScreenReader(message: string, priority: 'polite' | 'assertive' = 'polite'): void {
    const announcement = document.createElement('div')
    announcement.setAttribute('aria-live', priority)
    announcement.setAttribute('aria-atomic', 'true')
    announcement.className = 'sr-only'
    announcement.textContent = message

    document.body.appendChild(announcement)

    // Remove after announcement is made
    setTimeout(() => {
        document.body.removeChild(announcement)
    }, 1000)
}

/**
 * Trap focus within an element (for modals)
 */
export function trapFocus(element: HTMLElement): () => void {
    const focusableElements = element.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    )
    const firstFocusable = focusableElements[0] as HTMLElement
    const lastFocusable = focusableElements[focusableElements.length - 1] as HTMLElement

    function handleKeyDown(event: KeyboardEvent) {
        if (event.key !== KEYS.TAB) return

        if (event.shiftKey) {
            if (document.activeElement === firstFocusable) {
                event.preventDefault()
                lastFocusable?.focus()
            }
        } else {
            if (document.activeElement === lastFocusable) {
                event.preventDefault()
                firstFocusable?.focus()
            }
        }
    }

    element.addEventListener('keydown', handleKeyDown)
    firstFocusable?.focus()

    return () => {
        element.removeEventListener('keydown', handleKeyDown)
    }
}

/**
 * Skip link target IDs
 */
export const SKIP_LINK_TARGETS = {
    MAIN_CONTENT: 'main-content',
    NAVIGATION: 'main-navigation',
} as const

/**
 * Common ARIA labels for icons and buttons
 */
export const ARIA_LABELS = {
    CLOSE: 'Close',
    MENU: 'Open menu',
    MENU_CLOSE: 'Close menu',
    SEARCH: 'Search',
    SETTINGS: 'Settings',
    NOTIFICATIONS: 'Notifications',
    PROFILE: 'Profile menu',
    UPLOAD: 'Upload song',
    PLAY: 'Play',
    PAUSE: 'Pause',
    NEXT: 'Next track',
    PREVIOUS: 'Previous track',
    VOLUME: 'Volume',
    MUTE: 'Mute',
    UNMUTE: 'Unmute',
    LOADING: 'Loading',
    EXPAND: 'Expand',
    COLLAPSE: 'Collapse',
    EXTERNAL_LINK: 'Opens in new tab',
} as const
