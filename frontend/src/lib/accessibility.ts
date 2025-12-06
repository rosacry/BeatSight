/**
 * BeatSight Accessibility Utilities
 * 
 * Comprehensive WCAG 2.1 AA compliant accessibility utilities including:
 * - Focus management
 * - Screen reader announcements
 * - Keyboard navigation
 * - ARIA utilities
 * - Color contrast checking
 * - Motion preferences
 */

import { useCallback, useEffect, useRef, useState } from 'react'

// ============================================================================
// TYPES
// ============================================================================

export type AriaLive = 'off' | 'polite' | 'assertive'
export type FocusableElement = HTMLElement & { focus(): void }

export interface FocusTrapOptions {
    initialFocus?: string | HTMLElement | null
    returnFocus?: boolean
    escapeDeactivates?: boolean
    clickOutsideDeactivates?: boolean
}

export interface SkipLinkConfig {
    id: string
    label: string
}

// ============================================================================
// KEY CODES
// ============================================================================

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
    PAGE_UP: 'PageUp',
    PAGE_DOWN: 'PageDown',
    BACKSPACE: 'Backspace',
    DELETE: 'Delete',
} as const

// Alias for convenience
export const Keys = KEYS

// ============================================================================
// CONSTANTS
// ============================================================================

/** WCAG 2.1 AA minimum contrast ratios */
export const WCAG_CONTRAST = {
    AA_NORMAL: 4.5,
    AA_LARGE: 3,
    AAA_NORMAL: 7,
    AAA_LARGE: 4.5,
} as const

/** Focusable element selectors */
export const FOCUSABLE_SELECTOR = [
    'a[href]',
    'area[href]',
    'input:not([disabled]):not([type="hidden"])',
    'select:not([disabled])',
    'textarea:not([disabled])',
    'button:not([disabled])',
    'iframe',
    'object',
    'embed',
    '[contenteditable]',
    '[tabindex]:not([tabindex="-1"])',
].join(',')

/** Tabbable element selectors (visible focusable elements) */
export const TABBABLE_SELECTOR = [
    'a[href]:not([tabindex="-1"])',
    'area[href]:not([tabindex="-1"])',
    'input:not([disabled]):not([type="hidden"]):not([tabindex="-1"])',
    'select:not([disabled]):not([tabindex="-1"])',
    'textarea:not([disabled]):not([tabindex="-1"])',
    'button:not([disabled]):not([tabindex="-1"])',
    'iframe:not([tabindex="-1"])',
    '[contenteditable]:not([tabindex="-1"])',
    '[tabindex]:not([tabindex="-1"])',
].join(',')

/**
 * Skip link target IDs
 */
export const SKIP_LINK_TARGETS = {
    MAIN_CONTENT: 'main-content',
    NAVIGATION: 'main-navigation',
    SEARCH: 'search',
    FOOTER: 'footer',
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
    DELETE: 'Delete',
    EDIT: 'Edit',
    SAVE: 'Save',
    CANCEL: 'Cancel',
    SUBMIT: 'Submit',
    CLEAR: 'Clear',
    FILTER: 'Filter',
    SORT: 'Sort',
    REFRESH: 'Refresh',
    DOWNLOAD: 'Download',
    SHARE: 'Share',
    FAVORITE: 'Add to favorites',
    UNFAVORITE: 'Remove from favorites',
    LIKE: 'Like',
    UNLIKE: 'Unlike',
} as const

// ============================================================================
// SCREEN READER ANNOUNCEMENTS
// ============================================================================

let announcer: HTMLElement | null = null

/**
 * Get or create the live region announcer element
 */
function getAnnouncer(): HTMLElement {
    if (announcer && document.body.contains(announcer)) return announcer

    announcer = document.createElement('div')
    announcer.setAttribute('role', 'status')
    announcer.setAttribute('aria-live', 'polite')
    announcer.setAttribute('aria-atomic', 'true')
    announcer.className = 'sr-only'
    announcer.style.cssText = `
        position: absolute !important;
        width: 1px !important;
        height: 1px !important;
        padding: 0 !important;
        margin: -1px !important;
        overflow: hidden !important;
        clip: rect(0, 0, 0, 0) !important;
        white-space: nowrap !important;
        border: 0 !important;
    `
    document.body.appendChild(announcer)
    return announcer
}

/**
 * Announce a message to screen readers
 */
export function announce(
    message: string,
    priority: AriaLive = 'polite',
    timeout = 100
): void {
    const announcer = getAnnouncer()

    // Update aria-live based on priority
    announcer.setAttribute('aria-live', priority)

    // Clear and set message with delay to ensure announcement
    announcer.textContent = ''
    setTimeout(() => {
        announcer.textContent = message
    }, timeout)
}

/**
 * Announce message to screen readers (legacy function name)
 */
export function announceToScreenReader(
    message: string,
    priority: 'polite' | 'assertive' = 'polite'
): void {
    announce(message, priority)
}

/**
 * Hook for managing screen reader announcements
 */
export function useAnnounce() {
    const announceRef = useCallback(
        (message: string, priority: AriaLive = 'polite') => {
            announce(message, priority)
        },
        []
    )

    return announceRef
}

// ============================================================================
// KEYBOARD NAVIGATION
// ============================================================================

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
 * Check if an event is an activation key (Enter or Space)
 */
export function isActivationKey(event: KeyboardEvent | React.KeyboardEvent): boolean {
    return event.key === Keys.ENTER || event.key === Keys.SPACE
}

/**
 * Hook for handling keyboard shortcuts
 */
export function useKeyboardShortcut(
    key: string,
    callback: (event: KeyboardEvent) => void,
    options: {
        ctrl?: boolean
        shift?: boolean
        alt?: boolean
        meta?: boolean
        preventDefault?: boolean
        stopPropagation?: boolean
        enabled?: boolean
    } = {}
): void {
    const {
        ctrl = false,
        shift = false,
        alt = false,
        meta = false,
        preventDefault = true,
        stopPropagation = false,
        enabled = true,
    } = options

    useEffect(() => {
        if (!enabled) return

        const handler = (event: KeyboardEvent) => {
            const matchesKey = event.key.toLowerCase() === key.toLowerCase()
            const matchesModifiers =
                event.ctrlKey === ctrl &&
                event.shiftKey === shift &&
                event.altKey === alt &&
                event.metaKey === meta

            if (matchesKey && matchesModifiers) {
                if (preventDefault) event.preventDefault()
                if (stopPropagation) event.stopPropagation()
                callback(event)
            }
        }

        window.addEventListener('keydown', handler)
        return () => window.removeEventListener('keydown', handler)
    }, [key, callback, ctrl, shift, alt, meta, preventDefault, stopPropagation, enabled])
}

// ============================================================================
// FOCUS MANAGEMENT
// ============================================================================

/**
 * Get all focusable elements within a container
 */
export function getFocusableElements(
    container: HTMLElement,
    includeHidden = false
): HTMLElement[] {
    const selector = includeHidden ? FOCUSABLE_SELECTOR : TABBABLE_SELECTOR
    const elements = Array.from(container.querySelectorAll<HTMLElement>(selector))

    if (!includeHidden) {
        return elements.filter((el) => {
            // Check visibility
            const style = getComputedStyle(el)
            return style.display !== 'none' && style.visibility !== 'hidden'
        })
    }

    return elements
}

/**
 * Get the first focusable element in a container
 */
export function getFirstFocusable(container: HTMLElement): HTMLElement | null {
    const elements = getFocusableElements(container)
    return elements[0] || null
}

/**
 * Get the last focusable element in a container
 */
export function getLastFocusable(container: HTMLElement): HTMLElement | null {
    const elements = getFocusableElements(container)
    return elements[elements.length - 1] || null
}

/**
 * Trap focus within an element (for modals) - imperative version
 */
export function trapFocus(element: HTMLElement): () => void {
    const focusableElements = getFocusableElements(element)
    const firstFocusable = focusableElements[0]
    const lastFocusable = focusableElements[focusableElements.length - 1]

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
 * Hook for creating a focus trap
 */
export function useFocusTrap(
    isActive: boolean,
    options: FocusTrapOptions = {}
): React.RefObject<HTMLDivElement> {
    const containerRef = useRef<HTMLDivElement>(null)
    const previousActiveElement = useRef<Element | null>(null)

    const {
        initialFocus,
        returnFocus = true,
        escapeDeactivates = true,
        clickOutsideDeactivates = false,
    } = options

    useEffect(() => {
        if (!isActive || !containerRef.current) return

        const container = containerRef.current
        previousActiveElement.current = document.activeElement

        // Set initial focus
        const setInitialFocus = () => {
            if (initialFocus) {
                const element =
                    typeof initialFocus === 'string'
                        ? container.querySelector<HTMLElement>(initialFocus)
                        : initialFocus
                element?.focus()
            } else {
                const firstFocusable = getFirstFocusable(container)
                firstFocusable?.focus()
            }
        }

        // Small delay to ensure DOM is ready
        requestAnimationFrame(setInitialFocus)

        // Handle tab key for trapping focus
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Tab') {
                const focusable = getFocusableElements(container)
                if (focusable.length === 0) return

                const firstFocusable = focusable[0]
                const lastFocusable = focusable[focusable.length - 1]

                if (e.shiftKey) {
                    // Shift + Tab
                    if (document.activeElement === firstFocusable) {
                        e.preventDefault()
                        lastFocusable.focus()
                    }
                } else {
                    // Tab
                    if (document.activeElement === lastFocusable) {
                        e.preventDefault()
                        firstFocusable.focus()
                    }
                }
            }

            // Escape key
            if (escapeDeactivates && e.key === 'Escape') {
                // Parent component should handle deactivation
            }
        }

        // Handle click outside
        const handleClickOutside = (e: MouseEvent) => {
            if (clickOutsideDeactivates && !container.contains(e.target as Node)) {
                // Parent component should handle deactivation
            }
        }

        document.addEventListener('keydown', handleKeyDown)
        if (clickOutsideDeactivates) {
            document.addEventListener('mousedown', handleClickOutside)
        }

        return () => {
            document.removeEventListener('keydown', handleKeyDown)
            if (clickOutsideDeactivates) {
                document.removeEventListener('mousedown', handleClickOutside)
            }

            // Return focus to previous element
            if (returnFocus && previousActiveElement.current instanceof HTMLElement) {
                previousActiveElement.current.focus()
            }
        }
    }, [isActive, initialFocus, returnFocus, escapeDeactivates, clickOutsideDeactivates])

    return containerRef as React.RefObject<HTMLDivElement>
}

/**
 * Hook for roving focus (arrow key navigation within a group)
 */
export function useRovingFocus<T extends HTMLElement>(
    itemCount: number,
    options: {
        orientation?: 'horizontal' | 'vertical' | 'both'
        loop?: boolean
    } = {}
): {
    currentIndex: number
    setCurrentIndex: (index: number) => void
    getItemProps: (index: number) => {
        tabIndex: number
        onKeyDown: (e: React.KeyboardEvent) => void
        ref: (el: T | null) => void
    }
} {
    const { orientation = 'both', loop = true } = options
    const [currentIndex, setCurrentIndex] = useState(0)
    const itemRefs = useRef<(T | null)[]>([])

    const focusItem = useCallback((index: number) => {
        const item = itemRefs.current[index]
        if (item) {
            item.focus()
            setCurrentIndex(index)
        }
    }, [])

    const getItemProps = useCallback(
        (index: number) => ({
            tabIndex: index === currentIndex ? 0 : -1,
            onKeyDown: (e: React.KeyboardEvent) => {
                const isHorizontal = orientation === 'horizontal' || orientation === 'both'
                const isVertical = orientation === 'vertical' || orientation === 'both'

                let nextIndex = currentIndex

                switch (e.key) {
                    case 'ArrowRight':
                        if (isHorizontal) {
                            e.preventDefault()
                            nextIndex = currentIndex + 1
                            if (nextIndex >= itemCount) {
                                nextIndex = loop ? 0 : currentIndex
                            }
                        }
                        break
                    case 'ArrowLeft':
                        if (isHorizontal) {
                            e.preventDefault()
                            nextIndex = currentIndex - 1
                            if (nextIndex < 0) {
                                nextIndex = loop ? itemCount - 1 : 0
                            }
                        }
                        break
                    case 'ArrowDown':
                        if (isVertical) {
                            e.preventDefault()
                            nextIndex = currentIndex + 1
                            if (nextIndex >= itemCount) {
                                nextIndex = loop ? 0 : currentIndex
                            }
                        }
                        break
                    case 'ArrowUp':
                        if (isVertical) {
                            e.preventDefault()
                            nextIndex = currentIndex - 1
                            if (nextIndex < 0) {
                                nextIndex = loop ? itemCount - 1 : 0
                            }
                        }
                        break
                    case 'Home':
                        e.preventDefault()
                        nextIndex = 0
                        break
                    case 'End':
                        e.preventDefault()
                        nextIndex = itemCount - 1
                        break
                }

                if (nextIndex !== currentIndex) {
                    focusItem(nextIndex)
                }
            },
            ref: (el: T | null) => {
                itemRefs.current[index] = el
            },
        }),
        [currentIndex, itemCount, orientation, loop, focusItem]
    )

    return { currentIndex, setCurrentIndex, getItemProps }
}

// ============================================================================
// ID GENERATION
// ============================================================================

/**
 * Generate unique IDs for ARIA relationships
 */
let idCounter = 0
export function generateId(prefix = 'beatsight'): string {
    return `${prefix}-${++idCounter}`
}

/**
 * Hook for generating stable unique IDs
 */
export function useId(prefix = 'beatsight'): string {
    const idRef = useRef<string>()
    if (!idRef.current) {
        idRef.current = generateId(prefix)
    }
    return idRef.current
}

/**
 * Create ARIA describedby string from multiple IDs
 */
export function combineAriaDescribedBy(...ids: (string | undefined | null)[]): string | undefined {
    const validIds = ids.filter(Boolean)
    return validIds.length > 0 ? validIds.join(' ') : undefined
}

// ============================================================================
// ARIA UTILITIES
// ============================================================================

/**
 * Props for accessible buttons that behave like links
 */
export const linkButtonProps = {
    role: 'link' as const,
    tabIndex: 0,
}

/**
 * Props for accessible clickable divs
 */
export function getClickableProps(onClick: () => void) {
    return {
        role: 'button' as const,
        tabIndex: 0,
        onClick,
        onKeyDown: (e: React.KeyboardEvent) => {
            if (isActivationKey(e)) {
                e.preventDefault()
                onClick()
            }
        },
    }
}

// ============================================================================
// COLOR CONTRAST
// ============================================================================

/**
 * Convert hex color to RGB
 */
export function hexToRgb(hex: string): { r: number; g: number; b: number } | null {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
    return result
        ? {
            r: parseInt(result[1], 16),
            g: parseInt(result[2], 16),
            b: parseInt(result[3], 16),
        }
        : null
}

/**
 * Calculate relative luminance of a color
 */
export function getLuminance(r: number, g: number, b: number): number {
    const [rs, gs, bs] = [r, g, b].map((c) => {
        c = c / 255
        return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)
    })
    return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs
}

/**
 * Calculate contrast ratio between two colors
 */
export function getContrastRatio(color1: string, color2: string): number {
    const rgb1 = hexToRgb(color1)
    const rgb2 = hexToRgb(color2)

    if (!rgb1 || !rgb2) return 0

    const lum1 = getLuminance(rgb1.r, rgb1.g, rgb1.b)
    const lum2 = getLuminance(rgb2.r, rgb2.g, rgb2.b)

    const lighter = Math.max(lum1, lum2)
    const darker = Math.min(lum1, lum2)

    return (lighter + 0.05) / (darker + 0.05)
}

/**
 * Check if contrast meets WCAG requirements
 */
export function meetsContrastRequirement(
    foreground: string,
    background: string,
    level: 'AA' | 'AAA' = 'AA',
    isLargeText = false
): boolean {
    const ratio = getContrastRatio(foreground, background)
    const required = isLargeText
        ? level === 'AAA'
            ? WCAG_CONTRAST.AAA_LARGE
            : WCAG_CONTRAST.AA_LARGE
        : level === 'AAA'
            ? WCAG_CONTRAST.AAA_NORMAL
            : WCAG_CONTRAST.AA_NORMAL

    return ratio >= required
}

/**
 * Get a readable text color (black or white) for a given background
 */
export function getReadableTextColor(backgroundColor: string): '#000000' | '#ffffff' {
    const rgb = hexToRgb(backgroundColor)
    if (!rgb) return '#000000'

    const luminance = getLuminance(rgb.r, rgb.g, rgb.b)
    return luminance > 0.179 ? '#000000' : '#ffffff'
}

// ============================================================================
// MOTION PREFERENCES
// ============================================================================

/**
 * Hook for detecting prefers-reduced-motion
 */
export function usePrefersReducedMotion(): boolean {
    const [prefersReducedMotion, setPrefersReducedMotion] = useState(false)

    useEffect(() => {
        const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
        setPrefersReducedMotion(mediaQuery.matches)

        const handler = (event: MediaQueryListEvent) => {
            setPrefersReducedMotion(event.matches)
        }

        mediaQuery.addEventListener('change', handler)
        return () => mediaQuery.removeEventListener('change', handler)
    }, [])

    return prefersReducedMotion
}

/**
 * Hook for detecting prefers-high-contrast
 */
export function usePrefersHighContrast(): boolean {
    const [prefersHighContrast, setPrefersHighContrast] = useState(false)

    useEffect(() => {
        const mediaQuery = window.matchMedia('(prefers-contrast: more)')
        setPrefersHighContrast(mediaQuery.matches)

        const handler = (event: MediaQueryListEvent) => {
            setPrefersHighContrast(event.matches)
        }

        mediaQuery.addEventListener('change', handler)
        return () => mediaQuery.removeEventListener('change', handler)
    }, [])

    return prefersHighContrast
}

/**
 * Hook for detecting if user is using keyboard navigation
 */
export function useKeyboardNavigation(): boolean {
    const [isKeyboardNav, setIsKeyboardNav] = useState(false)

    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Tab') {
                setIsKeyboardNav(true)
            }
        }

        const handleMouseDown = () => {
            setIsKeyboardNav(false)
        }

        window.addEventListener('keydown', handleKeyDown)
        window.addEventListener('mousedown', handleMouseDown)

        return () => {
            window.removeEventListener('keydown', handleKeyDown)
            window.removeEventListener('mousedown', handleMouseDown)
        }
    }, [])

    return isKeyboardNav
}

// ============================================================================
// SKIP LINKS
// ============================================================================

/**
 * Default skip link targets for BeatSight
 */
export const defaultSkipLinks: SkipLinkConfig[] = [
    { id: 'main-content', label: 'Skip to main content' },
    { id: 'main-navigation', label: 'Skip to navigation' },
    { id: 'search', label: 'Skip to search' },
]

/**
 * Hook for skip link visibility
 */
export function useSkipLinks(): {
    isVisible: boolean
    show: () => void
    hide: () => void
} {
    const [isVisible, setIsVisible] = useState(false)

    const show = useCallback(() => setIsVisible(true), [])
    const hide = useCallback(() => setIsVisible(false), [])

    return { isVisible, show, hide }
}

// ============================================================================
// CSS UTILITIES
// ============================================================================

/**
 * Screen reader only styles (use with className)
 */
export const srOnlyStyles = `
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
`

/**
 * Tailwind class for screen reader only content
 */
export const srOnlyClass = 'sr-only'

/**
 * Make content visually hidden but accessible to screen readers
 */
export const visuallyHiddenStyles: React.CSSProperties = {
    position: 'absolute',
    width: '1px',
    height: '1px',
    padding: 0,
    margin: '-1px',
    overflow: 'hidden',
    clip: 'rect(0, 0, 0, 0)',
    whiteSpace: 'nowrap',
    border: 0,
}

/**
 * Focus visible styles for keyboard navigation
 */
export const focusVisibleStyles = `
    focus:outline-none
    focus-visible:outline-2
    focus-visible:outline-offset-2
    focus-visible:outline-primary-500
`

/**
 * Focus ring class for interactive elements
 */
export const focusRingClass = 'focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background focus:outline-none'

// ============================================================================
// DEFAULT EXPORT
// ============================================================================

export default {
    announce,
    announceToScreenReader,
    useAnnounce,
    trapFocus,
    useFocusTrap,
    useRovingFocus,
    useKeyboardShortcut,
    generateId,
    useId,
    usePrefersReducedMotion,
    usePrefersHighContrast,
    useKeyboardNavigation,
    getContrastRatio,
    meetsContrastRequirement,
    getReadableTextColor,
    handleKeyboardClick,
    isActivationKey,
    getClickableProps,
    Keys,
    KEYS,
    WCAG_CONTRAST,
    ARIA_LABELS,
    SKIP_LINK_TARGETS,
}
