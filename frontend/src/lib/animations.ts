/**
 * Animation and motion utilities for consistent UI animations.
 * Provides CSS keyframes, Tailwind classes, React hooks, and micro-interactions.
 * Enhanced for BeatSight rhythm game aesthetics.
 */

import { useCallback, useEffect, useRef, useState } from 'react'

// ============================================================================
// TYPES
// ============================================================================

export type AnimationDirection = 'up' | 'down' | 'left' | 'right'
export type AnimationState = 'idle' | 'entering' | 'entered' | 'exiting' | 'exited'

export interface AnimationConfig {
    duration?: number
    delay?: number
    easing?: string
    reduceMotion?: boolean
}

export interface SpringConfig {
    stiffness?: number
    damping?: number
    mass?: number
}

// ============================================================================
// KEYFRAMES
// ============================================================================

/**
 * Animation keyframes to add to your CSS/Tailwind config
 */
export const keyframes = {
    // Slide animations
    'slide-in-right': {
        from: { transform: 'translateX(100%)', opacity: '0' },
        to: { transform: 'translateX(0)', opacity: '1' },
    },
    'slide-in-left': {
        from: { transform: 'translateX(-100%)', opacity: '0' },
        to: { transform: 'translateX(0)', opacity: '1' },
    },
    'slide-in-up': {
        from: { transform: 'translateY(100%)', opacity: '0' },
        to: { transform: 'translateY(0)', opacity: '1' },
    },
    'slide-in-down': {
        from: { transform: 'translateY(-100%)', opacity: '0' },
        to: { transform: 'translateY(0)', opacity: '1' },
    },
    'slide-out-right': {
        from: { transform: 'translateX(0)', opacity: '1' },
        to: { transform: 'translateX(100%)', opacity: '0' },
    },
    'slide-out-left': {
        from: { transform: 'translateX(0)', opacity: '1' },
        to: { transform: 'translateX(-100%)', opacity: '0' },
    },
    'slide-out-up': {
        from: { transform: 'translateY(0)', opacity: '1' },
        to: { transform: 'translateY(-100%)', opacity: '0' },
    },
    'slide-out-down': {
        from: { transform: 'translateY(0)', opacity: '1' },
        to: { transform: 'translateY(100%)', opacity: '0' },
    },

    // Fade animations
    'fade-in': {
        from: { opacity: '0' },
        to: { opacity: '1' },
    },
    'fade-out': {
        from: { opacity: '1' },
        to: { opacity: '0' },
    },
    'fade-in-scale': {
        from: { opacity: '0', transform: 'scale(0.95)' },
        to: { opacity: '1', transform: 'scale(1)' },
    },
    'fade-out-scale': {
        from: { opacity: '1', transform: 'scale(1)' },
        to: { opacity: '0', transform: 'scale(0.95)' },
    },
    'fade-in-blur': {
        from: { opacity: '0', filter: 'blur(8px)' },
        to: { opacity: '1', filter: 'blur(0)' },
    },

    // Glow animations
    'glow-pulse': {
        '0%, 100%': { boxShadow: '0 0 20px rgba(14, 165, 233, 0.3)' },
        '50%': { boxShadow: '0 0 40px rgba(14, 165, 233, 0.6)' },
    },
    'glow-pulse-accent': {
        '0%, 100%': { boxShadow: '0 0 20px rgba(236, 72, 153, 0.3)' },
        '50%': { boxShadow: '0 0 40px rgba(236, 72, 153, 0.6)' },
    },
    'gradient-shift': {
        '0%': { backgroundPosition: '0% 50%' },
        '50%': { backgroundPosition: '100% 50%' },
        '100%': { backgroundPosition: '0% 50%' },
    },
    'gradient-rotate': {
        from: { '--gradient-angle': '0deg' },
        to: { '--gradient-angle': '360deg' },
    },

    // Bounce and spring
    'bounce-in': {
        '0%': { transform: 'scale(0)', opacity: '0' },
        '50%': { transform: 'scale(1.1)' },
        '100%': { transform: 'scale(1)', opacity: '1' },
    },
    'bounce-out': {
        '0%': { transform: 'scale(1)', opacity: '1' },
        '50%': { transform: 'scale(1.1)' },
        '100%': { transform: 'scale(0)', opacity: '0' },
    },
    'spring': {
        '0%': { transform: 'scale(1)' },
        '25%': { transform: 'scale(0.95)' },
        '50%': { transform: 'scale(1.05)' },
        '100%': { transform: 'scale(1)' },
    },
    'elastic': {
        '0%': { transform: 'scale(0)' },
        '55%': { transform: 'scale(1.2)' },
        '70%': { transform: 'scale(0.9)' },
        '85%': { transform: 'scale(1.05)' },
        '100%': { transform: 'scale(1)' },
    },

    // Shake variations
    shake: {
        '0%, 100%': { transform: 'translateX(0)' },
        '10%, 30%, 50%, 70%, 90%': { transform: 'translateX(-4px)' },
        '20%, 40%, 60%, 80%': { transform: 'translateX(4px)' },
    },
    'shake-subtle': {
        '0%, 100%': { transform: 'translateX(0)' },
        '25%': { transform: 'translateX(-2px)' },
        '75%': { transform: 'translateX(2px)' },
    },
    wiggle: {
        '0%, 100%': { transform: 'rotate(0deg)' },
        '25%': { transform: 'rotate(-3deg)' },
        '75%': { transform: 'rotate(3deg)' },
    },

    // Shimmer
    shimmer: {
        from: { backgroundPosition: '-200% 0' },
        to: { backgroundPosition: '200% 0' },
    },

    // Spin variations
    'spin-slow': {
        from: { transform: 'rotate(0deg)' },
        to: { transform: 'rotate(360deg)' },
    },

    // Float
    float: {
        '0%, 100%': { transform: 'translateY(0)' },
        '50%': { transform: 'translateY(-10px)' },
    },
    'float-subtle': {
        '0%, 100%': { transform: 'translateY(0)' },
        '50%': { transform: 'translateY(-4px)' },
    },

    // ========================================================================
    // BEATSIGHT RHYTHM GAME SPECIFIC ANIMATIONS
    // ========================================================================

    // Hit feedback animations
    'hit-perfect': {
        '0%': { transform: 'scale(1)', opacity: '1' },
        '50%': { transform: 'scale(1.4)', opacity: '0.8' },
        '100%': { transform: 'scale(1.6)', opacity: '0' },
    },
    'hit-good': {
        '0%': { transform: 'scale(1)', opacity: '1' },
        '100%': { transform: 'scale(1.3)', opacity: '0' },
    },
    'hit-miss': {
        '0%': { transform: 'scale(1) rotate(0deg)', opacity: '1' },
        '100%': { transform: 'scale(0.8) rotate(-10deg)', opacity: '0' },
    },
    'combo-burst': {
        '0%': { transform: 'scale(1) translateY(0)', opacity: '1' },
        '50%': { transform: 'scale(1.2) translateY(-10px)' },
        '100%': { transform: 'scale(1) translateY(-20px)', opacity: '0' },
    },

    // Drum pad animations
    'drum-hit': {
        '0%': { transform: 'scale(1)', boxShadow: '0 0 0 rgba(14, 165, 233, 0)' },
        '20%': { transform: 'scale(0.95)', boxShadow: '0 0 30px rgba(14, 165, 233, 0.6)' },
        '100%': { transform: 'scale(1)', boxShadow: '0 0 0 rgba(14, 165, 233, 0)' },
    },
    ripple: {
        '0%': { transform: 'scale(0)', opacity: '1' },
        '100%': { transform: 'scale(2)', opacity: '0' },
    },
    'ripple-fast': {
        '0%': { transform: 'scale(0)', opacity: '0.7' },
        '100%': { transform: 'scale(1.5)', opacity: '0' },
    },

    // Note approach
    'note-approach': {
        from: { transform: 'translateY(-100%) scale(0.5)', opacity: '0.5' },
        to: { transform: 'translateY(0) scale(1)', opacity: '1' },
    },

    // Score animations
    'score-pop': {
        '0%': { transform: 'scale(1)' },
        '50%': { transform: 'scale(1.15)' },
        '100%': { transform: 'scale(1)' },
    },
    'number-tick': {
        '0%': { transform: 'translateY(0)' },
        '50%': { transform: 'translateY(-2px)' },
        '100%': { transform: 'translateY(0)' },
    },

    // BPM pulse
    'bpm-pulse': {
        '0%, 100%': { transform: 'scale(1)', opacity: '0.7' },
        '50%': { transform: 'scale(1.05)', opacity: '1' },
    },

    // Lane highlight
    'lane-flash': {
        '0%': { backgroundColor: 'rgba(14, 165, 233, 0.4)' },
        '100%': { backgroundColor: 'rgba(14, 165, 233, 0)' },
    },

    // ========================================================================
    // MICRO-INTERACTIONS
    // ========================================================================

    // Button hover
    'button-hover': {
        from: { transform: 'translateY(0)' },
        to: { transform: 'translateY(-2px)' },
    },
    'button-press': {
        '0%': { transform: 'scale(1)' },
        '50%': { transform: 'scale(0.97)' },
        '100%': { transform: 'scale(1)' },
    },

    // Icon animations
    'icon-spin': {
        from: { transform: 'rotate(0deg)' },
        to: { transform: 'rotate(180deg)' },
    },
    'icon-bounce': {
        '0%, 100%': { transform: 'translateY(0)' },
        '50%': { transform: 'translateY(-3px)' },
    },
    'check-mark': {
        from: { strokeDashoffset: '100' },
        to: { strokeDashoffset: '0' },
    },

    // Skeleton loading
    'skeleton-pulse': {
        '0%': { opacity: '0.4' },
        '50%': { opacity: '0.7' },
        '100%': { opacity: '0.4' },
    },

    // Progress
    'progress-indeterminate': {
        '0%': { left: '-40%' },
        '100%': { left: '100%' },
    },

    // Tooltip
    'tooltip-in': {
        from: { opacity: '0', transform: 'scale(0.95) translateY(4px)' },
        to: { opacity: '1', transform: 'scale(1) translateY(0)' },
    },

    // Dropdown
    'dropdown-in': {
        from: { opacity: '0', transform: 'scaleY(0.95)', transformOrigin: 'top' },
        to: { opacity: '1', transform: 'scaleY(1)', transformOrigin: 'top' },
    },
    'dropdown-out': {
        from: { opacity: '1', transform: 'scaleY(1)', transformOrigin: 'top' },
        to: { opacity: '0', transform: 'scaleY(0.95)', transformOrigin: 'top' },
    },

    // Modal
    'modal-overlay-in': {
        from: { opacity: '0' },
        to: { opacity: '1' },
    },
    'modal-content-in': {
        from: { opacity: '0', transform: 'scale(0.95) translateY(10px)' },
        to: { opacity: '1', transform: 'scale(1) translateY(0)' },
    },

    // Toast
    'toast-in': {
        from: { opacity: '0', transform: 'translateY(-100%)' },
        to: { opacity: '1', transform: 'translateY(0)' },
    },
    'toast-out': {
        from: { opacity: '1', transform: 'translateY(0)' },
        to: { opacity: '0', transform: 'translateY(-100%)' },
    },

    // Card flip
    'card-flip': {
        '0%': { transform: 'rotateY(0deg)' },
        '100%': { transform: 'rotateY(180deg)' },
    },
}

// ============================================================================
// CSS ANIMATION CLASSES
// ============================================================================

/**
 * CSS classes for animations (to be used with @apply or directly)
 */
export const animationClasses = {
    // Entrance animations
    'animate-slide-in-right': 'animate-[slide-in-right_0.3s_ease-out]',
    'animate-slide-in-left': 'animate-[slide-in-left_0.3s_ease-out]',
    'animate-slide-in-up': 'animate-[slide-in-up_0.3s_ease-out]',
    'animate-slide-in-down': 'animate-[slide-in-down_0.3s_ease-out]',
    'animate-fade-in': 'animate-[fade-in_0.2s_ease-out]',
    'animate-fade-in-scale': 'animate-[fade-in-scale_0.2s_ease-out]',
    'animate-fade-in-blur': 'animate-[fade-in-blur_0.3s_ease-out]',
    'animate-bounce-in': 'animate-[bounce-in_0.4s_cubic-bezier(0.68,-0.55,0.265,1.55)]',
    'animate-elastic': 'animate-[elastic_0.6s_ease-out]',

    // Exit animations
    'animate-slide-out-right': 'animate-[slide-out-right_0.3s_ease-in_forwards]',
    'animate-slide-out-left': 'animate-[slide-out-left_0.3s_ease-in_forwards]',
    'animate-slide-out-up': 'animate-[slide-out-up_0.3s_ease-in_forwards]',
    'animate-slide-out-down': 'animate-[slide-out-down_0.3s_ease-in_forwards]',
    'animate-fade-out': 'animate-[fade-out_0.2s_ease-in_forwards]',
    'animate-fade-out-scale': 'animate-[fade-out-scale_0.2s_ease-in_forwards]',
    'animate-bounce-out': 'animate-[bounce-out_0.3s_ease-in_forwards]',

    // Continuous animations
    'animate-glow-pulse': 'animate-[glow-pulse_2s_ease-in-out_infinite]',
    'animate-glow-pulse-accent': 'animate-[glow-pulse-accent_2s_ease-in-out_infinite]',
    'animate-gradient-shift': 'animate-[gradient-shift_3s_ease_infinite] bg-[length:200%_200%]',
    'animate-float': 'animate-[float_3s_ease-in-out_infinite]',
    'animate-float-subtle': 'animate-[float-subtle_2s_ease-in-out_infinite]',
    'animate-shimmer': 'animate-[shimmer_2s_linear_infinite]',
    'animate-spin-slow': 'animate-[spin-slow_3s_linear_infinite]',
    'animate-skeleton': 'animate-[skeleton-pulse_1.5s_ease-in-out_infinite]',
    'animate-bpm-pulse': 'animate-[bpm-pulse_0.5s_ease-in-out_infinite]',

    // Interactive
    'animate-shake': 'animate-[shake_0.5s_ease-in-out]',
    'animate-shake-subtle': 'animate-[shake-subtle_0.3s_ease-in-out]',
    'animate-wiggle': 'animate-[wiggle_0.3s_ease-in-out]',
    'animate-spring': 'animate-[spring_0.3s_ease-out]',
    'animate-button-press': 'animate-[button-press_0.15s_ease-out]',

    // BeatSight specific
    'animate-hit-perfect': 'animate-[hit-perfect_0.3s_ease-out_forwards]',
    'animate-hit-good': 'animate-[hit-good_0.25s_ease-out_forwards]',
    'animate-hit-miss': 'animate-[hit-miss_0.3s_ease-out_forwards]',
    'animate-combo-burst': 'animate-[combo-burst_0.5s_ease-out_forwards]',
    'animate-drum-hit': 'animate-[drum-hit_0.15s_ease-out]',
    'animate-ripple': 'animate-[ripple_0.6s_ease-out_forwards]',
    'animate-ripple-fast': 'animate-[ripple-fast_0.3s_ease-out_forwards]',
    'animate-score-pop': 'animate-[score-pop_0.2s_ease-out]',
    'animate-lane-flash': 'animate-[lane-flash_0.2s_ease-out_forwards]',

    // UI Components
    'animate-tooltip-in': 'animate-[tooltip-in_0.15s_ease-out]',
    'animate-dropdown-in': 'animate-[dropdown-in_0.2s_ease-out]',
    'animate-dropdown-out': 'animate-[dropdown-out_0.15s_ease-in_forwards]',
    'animate-modal-overlay': 'animate-[modal-overlay-in_0.2s_ease-out]',
    'animate-modal-content': 'animate-[modal-content-in_0.3s_cubic-bezier(0.34,1.56,0.64,1)]',
    'animate-toast-in': 'animate-[toast-in_0.3s_ease-out]',
    'animate-toast-out': 'animate-[toast-out_0.2s_ease-in_forwards]',
}

// ============================================================================
// DURATION & EASING
// ============================================================================

/**
 * Duration constants (in milliseconds)
 */
export const durations = {
    instant: 0,
    ultraFast: 50,
    fast: 150,
    normal: 300,
    slow: 500,
    slower: 800,
    slowest: 1000,
}

/**
 * Easing functions
 */
export const easings = {
    default: 'cubic-bezier(0.4, 0, 0.2, 1)',
    linear: 'linear',
    in: 'cubic-bezier(0.4, 0, 1, 1)',
    out: 'cubic-bezier(0, 0, 0.2, 1)',
    inOut: 'cubic-bezier(0.4, 0, 0.2, 1)',
    bounce: 'cubic-bezier(0.68, -0.55, 0.265, 1.55)',
    spring: 'cubic-bezier(0.175, 0.885, 0.32, 1.275)',
    elastic: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
    // Material Design inspired
    standard: 'cubic-bezier(0.2, 0, 0, 1)',
    emphasized: 'cubic-bezier(0.2, 0, 0, 1)',
    decelerate: 'cubic-bezier(0, 0, 0, 1)',
    accelerate: 'cubic-bezier(0.3, 0, 1, 1)',
}

// ============================================================================
// HOOKS
// ============================================================================

// ============================================================================
// HOOKS
// ============================================================================

/**
 * Hook for detecting reduced motion preference
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
 * Hook for triggering animation on mount
 */
export function useAnimateOnMount(delay = 0): boolean {
    const [animate, setAnimate] = useState(false)
    const prefersReducedMotion = usePrefersReducedMotion()

    useEffect(() => {
        if (prefersReducedMotion) {
            setAnimate(true)
            return
        }

        const timeout = setTimeout(() => setAnimate(true), delay)
        return () => clearTimeout(timeout)
    }, [delay, prefersReducedMotion])

    return animate
}

/**
 * Hook for staggered animations
 */
export function useStaggeredAnimation(
    itemCount: number,
    baseDelay = 0,
    staggerDelay = 50
): boolean[] {
    const [animatedItems, setAnimatedItems] = useState<boolean[]>(
        new Array(itemCount).fill(false)
    )
    const prefersReducedMotion = usePrefersReducedMotion()

    useEffect(() => {
        if (prefersReducedMotion) {
            setAnimatedItems(new Array(itemCount).fill(true))
            return
        }

        const timeouts: ReturnType<typeof setTimeout>[] = []

        for (let i = 0; i < itemCount; i++) {
            const timeout = setTimeout(() => {
                setAnimatedItems((prev) => {
                    const next = [...prev]
                    next[i] = true
                    return next
                })
            }, baseDelay + i * staggerDelay)
            timeouts.push(timeout)
        }

        return () => timeouts.forEach(clearTimeout)
    }, [itemCount, baseDelay, staggerDelay, prefersReducedMotion])

    return animatedItems
}

/**
 * Hook for animated presence (enter/exit states)
 */
export function useAnimatedPresence(
    isVisible: boolean,
    duration = durations.normal
): { state: AnimationState; shouldRender: boolean } {
    const [state, setState] = useState<AnimationState>(isVisible ? 'entered' : 'exited')
    const [shouldRender, setShouldRender] = useState(isVisible)
    const prefersReducedMotion = usePrefersReducedMotion()

    useEffect(() => {
        if (prefersReducedMotion) {
            setState(isVisible ? 'entered' : 'exited')
            setShouldRender(isVisible)
            return
        }

        if (isVisible) {
            setShouldRender(true)
            setState('entering')
            const timeout = setTimeout(() => setState('entered'), duration)
            return () => clearTimeout(timeout)
        } else {
            setState('exiting')
            const timeout = setTimeout(() => {
                setState('exited')
                setShouldRender(false)
            }, duration)
            return () => clearTimeout(timeout)
        }
    }, [isVisible, duration, prefersReducedMotion])

    return { state, shouldRender }
}

/**
 * Hook for counting/number animations
 */
export function useAnimatedNumber(
    targetValue: number,
    duration = durations.slow
): number {
    const [displayValue, setDisplayValue] = useState(targetValue)
    const previousValue = useRef(targetValue)
    const prefersReducedMotion = usePrefersReducedMotion()

    useEffect(() => {
        if (prefersReducedMotion) {
            setDisplayValue(targetValue)
            previousValue.current = targetValue
            return
        }

        const startValue = previousValue.current
        const difference = targetValue - startValue
        const startTime = performance.now()

        const animate = (currentTime: number) => {
            const elapsed = currentTime - startTime
            const progress = Math.min(elapsed / duration, 1)

            // Ease out quad
            const easeProgress = 1 - (1 - progress) * (1 - progress)
            const currentValue = startValue + difference * easeProgress

            setDisplayValue(Math.round(currentValue))

            if (progress < 1) {
                requestAnimationFrame(animate)
            } else {
                previousValue.current = targetValue
            }
        }

        requestAnimationFrame(animate)
    }, [targetValue, duration, prefersReducedMotion])

    return displayValue
}

/**
 * Hook for spring physics animations
 */
export function useSpring(
    targetValue: number,
    config: SpringConfig = {}
): number {
    const { stiffness = 170, damping = 26, mass = 1 } = config
    const [value, setValue] = useState(targetValue)
    const velocity = useRef(0)
    const prefersReducedMotion = usePrefersReducedMotion()

    useEffect(() => {
        if (prefersReducedMotion) {
            setValue(targetValue)
            return
        }

        let animationFrame: number
        let currentValue = value

        const animate = () => {
            const displacement = currentValue - targetValue
            const springForce = -stiffness * displacement
            const dampingForce = -damping * velocity.current
            const acceleration = (springForce + dampingForce) / mass

            velocity.current += acceleration * 0.016 // ~60fps
            currentValue += velocity.current * 0.016

            // Stop when motion is negligible
            if (Math.abs(velocity.current) < 0.01 && Math.abs(displacement) < 0.01) {
                setValue(targetValue)
                velocity.current = 0
                return
            }

            setValue(currentValue)
            animationFrame = requestAnimationFrame(animate)
        }

        animationFrame = requestAnimationFrame(animate)
        return () => cancelAnimationFrame(animationFrame)
    }, [targetValue, stiffness, damping, mass, prefersReducedMotion, value])

    return value
}

/**
 * Hook for intersection-based animations (animate on scroll)
 */
export function useAnimateOnScroll(
    options: IntersectionObserverInit = {}
): { ref: React.RefObject<HTMLDivElement>; isVisible: boolean } {
    const ref = useRef<HTMLDivElement>(null)
    const [isVisible, setIsVisible] = useState(false)
    const prefersReducedMotion = usePrefersReducedMotion()

    useEffect(() => {
        if (prefersReducedMotion) {
            setIsVisible(true)
            return
        }

        const element = ref.current
        if (!element) return

        const observer = new IntersectionObserver(
            ([entry]) => {
                if (entry.isIntersecting) {
                    setIsVisible(true)
                    observer.unobserve(element)
                }
            },
            { threshold: 0.1, ...options }
        )

        observer.observe(element)
        return () => observer.disconnect()
    }, [options, prefersReducedMotion])

    return { ref: ref as React.RefObject<HTMLDivElement>, isVisible }
}

/**
 * Hook for BPM-synced animations
 */
export function useBPMPulse(bpm: number, enabled = true): boolean {
    const [isPulsing, setIsPulsing] = useState(false)
    const prefersReducedMotion = usePrefersReducedMotion()

    useEffect(() => {
        if (!enabled || prefersReducedMotion || bpm <= 0) return

        const intervalMs = (60 / bpm) * 1000

        const interval = setInterval(() => {
            setIsPulsing(true)
            setTimeout(() => setIsPulsing(false), intervalMs / 4)
        }, intervalMs)

        return () => clearInterval(interval)
    }, [bpm, enabled, prefersReducedMotion])

    return isPulsing
}

/**
 * Hook for ripple effect
 */
export function useRipple(): {
    ripples: Array<{ id: number; x: number; y: number }>
    addRipple: (event: React.MouseEvent) => void
} {
    const [ripples, setRipples] = useState<Array<{ id: number; x: number; y: number }>>([])
    const nextId = useRef(0)

    const addRipple = useCallback((event: React.MouseEvent) => {
        const rect = event.currentTarget.getBoundingClientRect()
        const x = event.clientX - rect.left
        const y = event.clientY - rect.top
        const id = nextId.current++

        setRipples((prev) => [...prev, { id, x, y }])

        setTimeout(() => {
            setRipples((prev) => prev.filter((r) => r.id !== id))
        }, 600)
    }, [])

    return { ripples, addRipple }
}

// ============================================================================
// CSS UTILITIES
// ============================================================================

/**
 * CSS for shimmer effect
 */
export const shimmerGradient = `
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(255, 255, 255, 0.1) 50%,
    transparent 100%
  );
  background-size: 200% 100%;
`

/**
 * Transition utility classes
 */
export const transitions = {
    all: 'transition-all',
    colors: 'transition-colors',
    opacity: 'transition-opacity',
    transform: 'transition-transform',
    shadow: 'transition-shadow',

    // With durations
    fast: 'transition-all duration-150',
    normal: 'transition-all duration-300',
    slow: 'transition-all duration-500',

    // Specific transitions
    fadeIn: 'transition-opacity duration-200 ease-out',
    fadeOut: 'transition-opacity duration-150 ease-in',
    scaleIn: 'transition-transform duration-200 ease-out',
    slideIn: 'transition-transform duration-300 ease-out',
}

// ============================================================================
// ANIMATION HELPERS
// ============================================================================

/**
 * Get animation class with reduced motion support
 */
export function getAnimationClass(
    animation: keyof typeof animationClasses,
    prefersReducedMotion: boolean
): string {
    if (prefersReducedMotion) {
        return '' // No animation for reduced motion
    }
    return animationClasses[animation]
}

/**
 * Create a CSS transition string
 */
export function createTransition(
    properties: string | string[],
    duration = durations.normal,
    easing = easings.default
): string {
    const props = Array.isArray(properties) ? properties : [properties]
    return props.map((p) => `${p} ${duration}ms ${easing}`).join(', ')
}

/**
 * Create animation style object
 */
export function createAnimationStyle(
    animation: string,
    duration = durations.normal,
    easing = easings.default,
    delay = 0,
    fillMode: 'forwards' | 'backwards' | 'both' | 'none' = 'forwards'
): React.CSSProperties {
    return {
        animation: `${animation} ${duration}ms ${easing} ${delay}ms ${fillMode}`,
    }
}

/**
 * Variants for common animation patterns
 */
export const animationVariants = {
    fadeIn: {
        initial: { opacity: 0 },
        animate: { opacity: 1 },
        exit: { opacity: 0 },
    },
    slideUp: {
        initial: { opacity: 0, y: 20 },
        animate: { opacity: 1, y: 0 },
        exit: { opacity: 0, y: -20 },
    },
    slideDown: {
        initial: { opacity: 0, y: -20 },
        animate: { opacity: 1, y: 0 },
        exit: { opacity: 0, y: 20 },
    },
    scaleIn: {
        initial: { opacity: 0, scale: 0.95 },
        animate: { opacity: 1, scale: 1 },
        exit: { opacity: 0, scale: 0.95 },
    },
    bounceIn: {
        initial: { opacity: 0, scale: 0 },
        animate: { opacity: 1, scale: 1 },
        exit: { opacity: 0, scale: 0 },
    },
} as const

// ============================================================================
// BEATSIGHT GAME UTILITIES
// ============================================================================

/**
 * Hit accuracy to animation mapping
 */
export const hitAnimations = {
    perfect: 'animate-hit-perfect',
    great: 'animate-hit-good',
    good: 'animate-hit-good',
    bad: 'animate-hit-miss',
    miss: 'animate-hit-miss',
} as const

/**
 * Get glow color based on hit accuracy
 */
export function getHitGlowColor(accuracy: keyof typeof hitAnimations): string {
    const colors = {
        perfect: 'rgba(34, 197, 94, 0.6)', // green
        great: 'rgba(14, 165, 233, 0.6)', // cyan
        good: 'rgba(250, 204, 21, 0.6)', // yellow
        bad: 'rgba(249, 115, 22, 0.6)', // orange
        miss: 'rgba(239, 68, 68, 0.5)', // red
    }
    return colors[accuracy]
}

/**
 * Create note approach animation timing based on BPM
 */
export function getNoteApproachDuration(bpm: number, measures: number): number {
    const beatDuration = 60000 / bpm
    return beatDuration * 4 * measures
}

// ============================================================================
// DEFAULT EXPORT
// ============================================================================

export default {
    keyframes,
    animationClasses,
    durations,
    easings,
    transitions,
    animationVariants,
    hitAnimations,
}
