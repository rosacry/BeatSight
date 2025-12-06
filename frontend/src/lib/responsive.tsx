/**
 * Responsive Layout Utilities
 * Helpers for building responsive, adaptive layouts.
 */

import { useState, useEffect, type ReactNode } from 'react'
import { cn } from './utils'

// ============================================================================
// BREAKPOINT DEFINITIONS
// ============================================================================

/**
 * Tailwind-compatible breakpoint values
 */
export const breakpoints = {
  xs: 0,
  sm: 640,
  md: 768,
  lg: 1024,
  xl: 1280,
  '2xl': 1536,
} as const

export type Breakpoint = keyof typeof breakpoints

/**
 * Get the current breakpoint based on window width
 */
export function getCurrentBreakpoint(width: number): Breakpoint {
  if (width >= breakpoints['2xl']) return '2xl'
  if (width >= breakpoints.xl) return 'xl'
  if (width >= breakpoints.lg) return 'lg'
  if (width >= breakpoints.md) return 'md'
  if (width >= breakpoints.sm) return 'sm'
  return 'xs'
}

// ============================================================================
// RESPONSIVE HOOKS
// ============================================================================

/**
 * Hook to get current window dimensions
 */
export function useWindowSize() {
  const [size, setSize] = useState({
    width: typeof window !== 'undefined' ? window.innerWidth : 0,
    height: typeof window !== 'undefined' ? window.innerHeight : 0,
  })

  useEffect(() => {
    const handleResize = () => {
      setSize({
        width: window.innerWidth,
        height: window.innerHeight,
      })
    }

    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  return size
}

/**
 * Hook to get current breakpoint
 */
export function useBreakpoint(): Breakpoint {
  const { width } = useWindowSize()
  return getCurrentBreakpoint(width)
}

/**
 * Hook to check if current viewport matches a media query
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false)

  useEffect(() => {
    const mediaQuery = window.matchMedia(query)
    setMatches(mediaQuery.matches)

    const handler = (e: MediaQueryListEvent) => setMatches(e.matches)
    mediaQuery.addEventListener('change', handler)
    return () => mediaQuery.removeEventListener('change', handler)
  }, [query])

  return matches
}

/**
 * Hook to check if viewport is at least a certain breakpoint
 */
export function useBreakpointUp(breakpoint: Breakpoint): boolean {
  const { width } = useWindowSize()
  return width >= breakpoints[breakpoint]
}

/**
 * Hook to check if viewport is below a certain breakpoint
 */
export function useBreakpointDown(breakpoint: Breakpoint): boolean {
  const { width } = useWindowSize()
  return width < breakpoints[breakpoint]
}

/**
 * Hook to check if viewport is between two breakpoints
 */
export function useBreakpointBetween(min: Breakpoint, max: Breakpoint): boolean {
  const { width } = useWindowSize()
  return width >= breakpoints[min] && width < breakpoints[max]
}

/**
 * Common device type queries
 */
export function useDeviceType() {
  const breakpoint = useBreakpoint()

  return {
    isMobile: breakpoint === 'xs' || breakpoint === 'sm',
    isTablet: breakpoint === 'md',
    isDesktop: breakpoint === 'lg' || breakpoint === 'xl' || breakpoint === '2xl',
    isLargeDesktop: breakpoint === 'xl' || breakpoint === '2xl',
  }
}

/**
 * Hook to detect touch device
 */
export function useTouchDevice(): boolean {
  const [isTouch, setIsTouch] = useState(false)

  useEffect(() => {
    setIsTouch(
      'ontouchstart' in window ||
      navigator.maxTouchPoints > 0 ||
      (navigator as unknown as { msMaxTouchPoints: number }).msMaxTouchPoints > 0
    )
  }, [])

  return isTouch
}

/**
 * Hook to detect reduced motion preference
 */
export function useReducedMotion(): boolean {
  return useMediaQuery('(prefers-reduced-motion: reduce)')
}

/**
 * Hook to detect dark mode preference
 */
export function usePrefersDarkMode(): boolean {
  return useMediaQuery('(prefers-color-scheme: dark)')
}

/**
 * Hook to detect high contrast preference
 */
export function usePrefersHighContrast(): boolean {
  return useMediaQuery('(prefers-contrast: more)')
}

// ============================================================================
// RESPONSIVE VALUE HELPER
// ============================================================================

/**
 * Type for responsive values that can change per breakpoint
 */
export type ResponsiveValue<T> = T | Partial<Record<Breakpoint, T>>

/**
 * Hook to resolve a responsive value based on current breakpoint
 */
export function useResponsiveValue<T>(value: ResponsiveValue<T>, defaultValue: T): T {
  const breakpoint = useBreakpoint()

  if (typeof value !== 'object' || value === null) {
    return value as T
  }

  const responsiveValue = value as Partial<Record<Breakpoint, T>>

  // Find the closest matching breakpoint (cascade down)
  const orderedBreakpoints: Breakpoint[] = ['2xl', 'xl', 'lg', 'md', 'sm', 'xs']
  const currentIndex = orderedBreakpoints.indexOf(breakpoint)

  for (let i = currentIndex; i < orderedBreakpoints.length; i++) {
    const bp = orderedBreakpoints[i]
    if (responsiveValue[bp] !== undefined) {
      return responsiveValue[bp]!
    }
  }

  return defaultValue
}

// ============================================================================
// CONTAINER QUERIES HOOK
// ============================================================================

/**
 * Hook to observe container size (for container queries polyfill)
 */
export function useContainerQuery<T extends HTMLElement>(
  ref: React.RefObject<T | null>,
  callback: (entry: ResizeObserverEntry) => void
) {
  useEffect(() => {
    if (!ref.current) return

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        callback(entry)
      }
    })

    observer.observe(ref.current)
    return () => observer.disconnect()
  }, [ref, callback])
}

// ============================================================================
// LAYOUT UTILITY CLASSES
// ============================================================================

/**
 * Responsive container classes
 */
export const containerStyles = {
  /** Full-width on mobile, max-width on larger screens with auto margins */
  responsive: 'w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8',

  /** Narrow container for content-focused layouts */
  narrow: 'w-full max-w-3xl mx-auto px-4 sm:px-6',

  /** Wide container for dashboard layouts */
  wide: 'w-full max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-8',

  /** Full bleed (no max-width) */
  full: 'w-full px-4 sm:px-6 lg:px-8',
} as const

/**
 * Responsive grid classes
 */
export const gridStyles = {
  /** 1 column on mobile, 2 on tablet, 3 on desktop */
  cards: 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6',

  /** 1 column on mobile, 2 on tablet, 4 on desktop */
  gallery: 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4',

  /** Sidebar layout: full width on mobile, sidebar on desktop */
  sidebar: 'grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6',

  /** Two-column on tablet+, stack on mobile */
  twoCol: 'grid grid-cols-1 md:grid-cols-2 gap-6',

  /** Three-column on desktop, 2 on tablet, 1 on mobile */
  threeCol: 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6',

  /** Auto-fill grid with minimum column width */
  autoFill: 'grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4',
} as const

/**
 * Responsive spacing classes
 */
export const spacingStyles = {
  /** Section spacing (vertical padding) */
  section: 'py-8 sm:py-12 lg:py-16',

  /** Page padding */
  page: 'p-4 sm:p-6 lg:p-8',

  /** Stack gap */
  stack: 'space-y-4 sm:space-y-6 lg:space-y-8',

  /** Inline gap */
  inline: 'space-x-2 sm:space-x-4',
} as const

// ============================================================================
// VISIBILITY UTILITIES
// ============================================================================

/**
 * Visibility utility classes
 */
export const visibilityStyles = {
  /** Hide on mobile only */
  hideOnMobile: 'hidden sm:block',

  /** Show on mobile only */
  showOnMobile: 'block sm:hidden',

  /** Hide on tablet and below */
  hideOnTablet: 'hidden lg:block',

  /** Show on tablet and below */
  showOnTablet: 'block lg:hidden',

  /** Hide on desktop */
  hideOnDesktop: 'lg:hidden',

  /** Screen reader only */
  srOnly: 'sr-only',

  /** Not screen reader only on focus */
  notSrOnlyFocus: 'sr-only focus:not-sr-only',
} as const

// ============================================================================
// ASPECT RATIO UTILITIES
// ============================================================================

/**
 * Common aspect ratios
 */
export const aspectRatios = {
  square: 'aspect-square',        // 1:1
  video: 'aspect-video',          // 16:9
  photo: 'aspect-[4/3]',          // 4:3
  portrait: 'aspect-[3/4]',       // 3:4
  wide: 'aspect-[21/9]',          // 21:9
  ultrawide: 'aspect-[32/9]',     // 32:9
  album: 'aspect-square',         // CD artwork
  poster: 'aspect-[2/3]',         // Movie poster
} as const

// ============================================================================
// COMPONENT HELPERS
// ============================================================================

interface ShowProps {
  when: boolean
  fallback?: ReactNode
  children: ReactNode
}

/**
 * Conditional rendering component
 */
export function Show({ when, fallback = null, children }: ShowProps) {
  return when ? <>{children}</> : <>{fallback}</>
}

interface HideProps {
  when: boolean
  children: ReactNode
}

/**
 * Hide content conditionally
 */
export function Hide({ when, children }: HideProps) {
  return when ? null : <>{children}</>
}

interface ResponsiveShowProps {
  above?: Breakpoint
  below?: Breakpoint
  children: ReactNode
}

/**
 * Show content based on breakpoint
 */
export function ResponsiveShow({ above, below, children }: ResponsiveShowProps) {
  // Always call hooks unconditionally (React hooks rules)
  const isAboveResult = useBreakpointUp(above ?? 'xs')
  const isBelowResult = useBreakpointDown(below ?? '2xl')

  const isAbove = above ? isAboveResult : true
  const isBelow = below ? isBelowResult : true

  return isAbove && isBelow ? <>{children}</> : null
}

// ============================================================================
// CSS CLASS UTILITIES
// ============================================================================

/**
 * Generate responsive class names
 */
export function responsive(
  classes: Partial<Record<Breakpoint, string>>
): string {
  return Object.entries(classes)
    .filter(([, value]) => value)
    .map(([breakpoint, value]) => {
      if (breakpoint === 'xs') return value
      return value!.split(' ').map(c => `${breakpoint}:${c}`).join(' ')
    })
    .join(' ')
}

/**
 * Combine container and content classes
 */
export function layout(
  container: keyof typeof containerStyles,
  ...additionalClasses: string[]
): string {
  return cn(containerStyles[container], ...additionalClasses)
}

/**
 * Create responsive padding classes
 */
export function responsivePadding(
  base: number,
  sm?: number,
  md?: number,
  lg?: number
): string {
  const classes = [`p-${base}`]
  if (sm) classes.push(`sm:p-${sm}`)
  if (md) classes.push(`md:p-${md}`)
  if (lg) classes.push(`lg:p-${lg}`)
  return classes.join(' ')
}

/**
 * Create responsive gap classes
 */
export function responsiveGap(
  base: number,
  sm?: number,
  md?: number,
  lg?: number
): string {
  const classes = [`gap-${base}`]
  if (sm) classes.push(`sm:gap-${sm}`)
  if (md) classes.push(`md:gap-${md}`)
  if (lg) classes.push(`lg:gap-${lg}`)
  return classes.join(' ')
}
