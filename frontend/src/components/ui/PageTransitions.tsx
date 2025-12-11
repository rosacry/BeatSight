/**
 * Page Transitions & Route Animations
 * Smooth animated transitions between pages for a polished SPA experience.
 */

import React, {
    createContext,
    useContext,
    useState,
    useEffect,
    useRef,
    type ReactNode,
} from 'react'
import { useLocation } from 'react-router-dom'
import { cn } from '../../lib/utils'

// ============================================================================
// TRANSITION CONTEXT
// ============================================================================

interface TransitionContextValue {
    isTransitioning: boolean
    direction: 'forward' | 'backward'
    startTransition: (direction?: 'forward' | 'backward') => void
}

const TransitionContext = createContext<TransitionContextValue | null>(null)

export function usePageTransition() {
    const context = useContext(TransitionContext)
    if (!context) {
        throw new Error('usePageTransition must be used within TransitionProvider')
    }
    return context
}

// ============================================================================
// TRANSITION PROVIDER
// ============================================================================

interface TransitionProviderProps {
    children: ReactNode
    duration?: number
}

export function TransitionProvider({
    children,
    duration = 300,
}: TransitionProviderProps) {
    const [isTransitioning, setIsTransitioning] = useState(false)
    const [direction, setDirection] = useState<'forward' | 'backward'>('forward')
    const location = useLocation()
    const prevPath = useRef(location.pathname)

    useEffect(() => {
        if (location.pathname !== prevPath.current) {
            // Determine direction based on browser history
            setIsTransitioning(true)

            setTimeout(() => {
                setIsTransitioning(false)
                prevPath.current = location.pathname
            }, duration)
        }
    }, [location.pathname, duration])

    const startTransition = (dir: 'forward' | 'backward' = 'forward') => {
        setDirection(dir)
        setIsTransitioning(true)
        setTimeout(() => setIsTransitioning(false), duration)
    }

    return (
        <TransitionContext.Provider value={{ isTransitioning, direction, startTransition }}>
            {children}
        </TransitionContext.Provider>
    )
}

// ============================================================================
// PAGE TRANSITION WRAPPER
// ============================================================================

export type TransitionType = 'fade' | 'slide' | 'scale' | 'slideUp' | 'slideDown' | 'none'

export interface PageTransitionProps {
    children: ReactNode
    className?: string
    type?: TransitionType
    duration?: number
}

const transitionClasses: Record<TransitionType, { enter: string; exit: string }> = {
    fade: {
        enter: 'opacity-0',
        exit: 'opacity-100',
    },
    slide: {
        enter: 'opacity-0 translate-x-8',
        exit: 'opacity-100 translate-x-0',
    },
    scale: {
        enter: 'opacity-0 scale-95',
        exit: 'opacity-100 scale-100',
    },
    slideUp: {
        enter: 'opacity-0 translate-y-8',
        exit: 'opacity-100 translate-y-0',
    },
    slideDown: {
        enter: 'opacity-0 -translate-y-8',
        exit: 'opacity-100 translate-y-0',
    },
    none: {
        enter: '',
        exit: '',
    },
}

export function PageTransition({
    children,
    className,
    type = 'fade',
    duration = 300,
}: PageTransitionProps) {
    const [mounted, setMounted] = useState(false)
    const location = useLocation()

    useEffect(() => {
        setMounted(false)
        const timer = setTimeout(() => setMounted(true), 50)
        return () => clearTimeout(timer)
    }, [location.pathname])

    const classes = transitionClasses[type]

    return (
        <div
            className={cn(
                'transition-all ease-out',
                mounted ? classes.exit : classes.enter,
                className
            )}
            style={{ transitionDuration: `${duration}ms` }}
        >
            {children}
        </div>
    )
}

// ============================================================================
// ANIMATED OUTLET (for React Router)
// ============================================================================

interface AnimatedOutletProps {
    children: ReactNode
    type?: TransitionType
}

export function AnimatedOutlet({ children, type = 'fade' }: AnimatedOutletProps) {
    const location = useLocation()

    return (
        <PageTransition key={location.pathname} type={type}>
            {children}
        </PageTransition>
    )
}

// ============================================================================
// STAGGERED PAGE CONTENT
// ============================================================================

export interface StaggeredContentProps {
    children: ReactNode
    className?: string
    staggerDelay?: number
    initialDelay?: number
}

export function StaggeredContent({
    children,
    className,
    staggerDelay = 100,
    initialDelay = 100,
}: StaggeredContentProps) {
    const location = useLocation()
    const [key, setKey] = useState(0)

    useEffect(() => {
        setKey((k) => k + 1)
    }, [location.pathname])

    return (
        <div key={key} className={className}>
            {React.Children.map(children, (child, index) => (
                <div
                    className="opacity-0 translate-y-4 animate-[fadeInUp_0.5s_ease-out_forwards]"
                    style={{
                        animationDelay: `${initialDelay + index * staggerDelay}ms`,
                    }}
                >
                    {child}
                </div>
            ))}
        </div>
    )
}

// ============================================================================
// PAGE HEADER WITH ANIMATION
// ============================================================================

export interface AnimatedPageHeaderProps {
    title: string
    subtitle?: string
    badge?: string
    actions?: ReactNode
    className?: string
}

export function AnimatedPageHeader({
    title,
    subtitle,
    badge,
    actions,
    className,
}: AnimatedPageHeaderProps) {
    return (
        <div className={cn('mb-8', className)}>
            {badge && (
                <div
                    className="inline-flex items-center gap-2 px-3 py-1.5 bg-primary-500/10 
                     border border-primary-500/30 rounded-full mb-4
                     opacity-0 animate-[fadeInUp_0.5s_ease-out_forwards]"
                    style={{ animationDelay: '100ms' }}
                >
                    <span className="text-primary-400 text-sm font-medium">{badge}</span>
                </div>
            )}

            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                    <h1
                        className="text-3xl sm:text-4xl font-bold text-white
                       opacity-0 animate-[fadeInUp_0.5s_ease-out_forwards]"
                        style={{ animationDelay: '150ms' }}
                    >
                        {title}
                    </h1>
                    {subtitle && (
                        <p
                            className="mt-2 text-gray-400 text-lg
                         opacity-0 animate-[fadeInUp_0.5s_ease-out_forwards]"
                            style={{ animationDelay: '200ms' }}
                        >
                            {subtitle}
                        </p>
                    )}
                </div>

                {actions && (
                    <div
                        className="flex items-center gap-3
                       opacity-0 animate-[fadeInUp_0.5s_ease-out_forwards]"
                        style={{ animationDelay: '250ms' }}
                    >
                        {actions}
                    </div>
                )}
            </div>
        </div>
    )
}

// ============================================================================
// SECTION REVEAL ON SCROLL
// ============================================================================

export interface RevealOnScrollProps {
    children: ReactNode
    className?: string
    threshold?: number
    delay?: number
}

export function RevealOnScroll({
    children,
    className,
    threshold = 0.1,
    delay = 0,
}: RevealOnScrollProps) {
    const ref = useRef<HTMLDivElement>(null)
    const [isVisible, setIsVisible] = useState(false)

    useEffect(() => {
        const observer = new IntersectionObserver(
            ([entry]) => {
                if (entry.isIntersecting) {
                    setIsVisible(true)
                    observer.disconnect()
                }
            },
            { threshold }
        )

        if (ref.current) {
            observer.observe(ref.current)
        }

        return () => observer.disconnect()
    }, [threshold])

    return (
        <div
            ref={ref}
            className={cn(
                'transition-all duration-700 ease-out',
                isVisible
                    ? 'opacity-100 translate-y-0'
                    : 'opacity-0 translate-y-8',
                className
            )}
            style={{ transitionDelay: `${delay}ms` }}
        >
            {children}
        </div>
    )
}

// ============================================================================
// HERO SECTION WITH PARALLAX TEXT
// ============================================================================

export interface ParallaxHeroProps {
    title: string
    highlightedText?: string
    subtitle?: string
    badge?: ReactNode
    actions?: ReactNode
    className?: string
}

export function ParallaxHero({
    title,
    highlightedText,
    subtitle,
    badge,
    actions,
    className,
}: ParallaxHeroProps) {
    const [scrollY, setScrollY] = useState(0)

    useEffect(() => {
        const handleScroll = () => setScrollY(window.scrollY)
        window.addEventListener('scroll', handleScroll, { passive: true })
        return () => window.removeEventListener('scroll', handleScroll)
    }, [])

    const parallaxOffset = scrollY * 0.3

    return (
        <section className={cn('relative overflow-hidden py-24 sm:py-32', className)}>
            {/* Animated background gradient */}
            <div
                className="absolute inset-0 bg-gradient-to-br from-primary-900/30 via-dark-500 to-dark-500"
                style={{ transform: `translateY(${parallaxOffset * 0.5}px)` }}
            />
            <div
                className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] 
                   from-primary-500/20 via-transparent to-transparent"
                style={{ transform: `translateY(${parallaxOffset * 0.3}px)` }}
            />

            {/* Grid pattern overlay */}
            <div
                className="absolute inset-0 opacity-20"
                style={{
                    backgroundImage: `linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
                           linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)`,
                    backgroundSize: '60px 60px',
                    transform: `translateY(${parallaxOffset * 0.1}px)`,
                }}
            />

            <div className="relative max-w-7xl mx-auto px-4 text-center">
                {badge && (
                    <div
                        className="mb-8 opacity-0 animate-[fadeInUp_0.6s_ease-out_forwards]"
                        style={{ animationDelay: '100ms' }}
                    >
                        {badge}
                    </div>
                )}

                <h1
                    className="text-5xl sm:text-7xl font-bold text-white mb-6 tracking-tight
                     opacity-0 animate-[fadeInUp_0.6s_ease-out_forwards]"
                    style={{
                        animationDelay: '200ms',
                        transform: `translateY(${-parallaxOffset * 0.1}px)`,
                    }}
                >
                    {title}
                    {highlightedText && (
                        <>
                            <br />
                            <span className="bg-gradient-to-r from-primary-400 to-accent-400 bg-clip-text text-transparent">
                                {highlightedText}
                            </span>
                        </>
                    )}
                </h1>

                {subtitle && (
                    <p
                        className="text-xl text-gray-400 max-w-2xl mx-auto mb-10
                       opacity-0 animate-[fadeInUp_0.6s_ease-out_forwards]"
                        style={{ animationDelay: '300ms' }}
                    >
                        {subtitle}
                    </p>
                )}

                {actions && (
                    <div
                        className="flex flex-col sm:flex-row gap-4 justify-center
                       opacity-0 animate-[fadeInUp_0.6s_ease-out_forwards]"
                        style={{ animationDelay: '400ms' }}
                    >
                        {actions}
                    </div>
                )}
            </div>
        </section>
    )
}

// ============================================================================
// CSS KEYFRAMES (ensure these exist in tailwind config)
// ============================================================================

/*
Add to tailwind.config.js keyframes:

fadeInUp: {
  '0%': { opacity: '0', transform: 'translateY(20px)' },
  '100%': { opacity: '1', transform: 'translateY(0)' },
},
*/
