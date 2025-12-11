/**
 * Unified Transitions System
 * 
 * Provides consistent, smooth animations for all tab content, page transitions,
 * and sub-navigation throughout the application. Designed to eliminate visual
 * glitches and provide a polished, cohesive experience.
 */

import { ReactNode, useRef, useEffect, useState } from 'react'
import { motion, AnimatePresence, Variants } from 'framer-motion'
import { cn } from '../../lib/utils'

// ============================================================================
// ANIMATION CONSTANTS - Single source of truth for all transitions
// ============================================================================

export const TRANSITION_DURATION = 0.2
export const STAGGER_DELAY = 0.05
export const EASE_CURVE = [0.25, 0.46, 0.45, 0.94] as const

// ============================================================================
// SHARED ANIMATION VARIANTS
// ============================================================================

/**
 * Standard tab content transition - used for all tab panels
 */
export const tabContentVariants: Variants = {
    initial: {
        opacity: 0,
        x: 16,
    },
    animate: {
        opacity: 1,
        x: 0,
        transition: {
            duration: TRANSITION_DURATION,
            ease: EASE_CURVE,
        },
    },
    exit: {
        opacity: 0,
        x: -16,
        transition: {
            duration: TRANSITION_DURATION * 0.75,
            ease: EASE_CURVE,
        },
    },
}

/**
 * Staggered container for animating child elements sequentially
 */
export const staggerContainerVariants: Variants = {
    initial: { opacity: 0 },
    animate: {
        opacity: 1,
        transition: {
            staggerChildren: STAGGER_DELAY,
            delayChildren: 0.05,
        },
    },
    exit: { opacity: 0 },
}

/**
 * Individual stagger item animation
 */
export const staggerItemVariants: Variants = {
    initial: {
        opacity: 0,
        y: 12,
    },
    animate: {
        opacity: 1,
        y: 0,
        transition: {
            duration: 0.3,
            ease: EASE_CURVE,
        },
    },
    exit: {
        opacity: 0,
        y: -8,
        transition: {
            duration: 0.15,
        },
    },
}

/**
 * Page-level transition variants - for top-level route changes
 */
export const pageVariants: Variants = {
    initial: {
        opacity: 0,
    },
    animate: {
        opacity: 1,
        transition: {
            duration: 0.15,
            ease: 'easeOut',
        },
    },
    exit: {
        opacity: 0,
        transition: {
            duration: 0.1,
        },
    },
}

/**
 * Modal/overlay content variants
 */
export const overlayContentVariants: Variants = {
    initial: {
        opacity: 0,
        scale: 0.96,
    },
    animate: {
        opacity: 1,
        scale: 1,
        transition: {
            duration: TRANSITION_DURATION,
            ease: EASE_CURVE,
        },
    },
    exit: {
        opacity: 0,
        scale: 0.96,
        transition: {
            duration: 0.15,
        },
    },
}

// ============================================================================
// TAB CONTENT WRAPPER
// ============================================================================

interface TabContentWrapperProps {
    /** Unique key for the tab content - triggers animation on change */
    tabKey: string
    /** Tab content to render */
    children: ReactNode
    /** Additional CSS classes */
    className?: string
    /** Whether to animate children with stagger effect */
    stagger?: boolean
    /** Animation mode: wait for exit before enter, or sync */
    mode?: 'wait' | 'sync' | 'popLayout'
}

/**
 * Wraps tab content with consistent enter/exit animations.
 * Use this around the content of each tab panel.
 */
export function TabContentWrapper({
    tabKey,
    children,
    className,
    stagger = false,
    mode = 'wait',
}: TabContentWrapperProps) {
    return (
        <AnimatePresence mode={mode} initial={false}>
            <motion.div
                key={tabKey}
                initial="initial"
                animate="animate"
                exit="exit"
                variants={stagger ? staggerContainerVariants : tabContentVariants}
                className={cn('w-full', className)}
            >
                {children}
            </motion.div>
        </AnimatePresence>
    )
}

// ============================================================================
// STAGGER ITEM WRAPPER
// ============================================================================

interface StaggerItemProps {
    children: ReactNode
    className?: string
}

/**
 * Wrap individual items within a TabContentWrapper (with stagger=true) 
 * to animate them in sequence.
 */
export function StaggerItem({ children, className }: StaggerItemProps) {
    return (
        <motion.div variants={staggerItemVariants} className={className}>
            {children}
        </motion.div>
    )
}

// ============================================================================
// PRE-RENDERED TAB SYSTEM
// ============================================================================

interface Tab {
    id: string
    label: string
    icon?: ReactNode
}

interface PreRenderedTabsProps<T extends string> {
    tabs: Tab[]
    activeTab: T
    onTabChange: (tab: T) => void
    children: (tabId: T) => ReactNode
    className?: string
    tabListClassName?: string
    contentClassName?: string
    /** Variant style for the tab buttons */
    variant?: 'default' | 'pills' | 'underline'
}

/**
 * Pre-rendered tabs system that keeps all tab content in the DOM
 * but only shows the active tab. This eliminates flash/glitches
 * caused by content not being ready when switching tabs.
 */
export function PreRenderedTabs<T extends string>({
    tabs,
    activeTab,
    onTabChange,
    children,
    className,
    tabListClassName,
    contentClassName,
    variant = 'default',
}: PreRenderedTabsProps<T>) {
    // Track which tabs have been visited to pre-render them
    const [visitedTabs, setVisitedTabs] = useState<Set<T>>(new Set([activeTab]))

    useEffect(() => {
        setVisitedTabs((prev) => new Set([...prev, activeTab]))
    }, [activeTab])

    const getTabButtonClasses = (isActive: boolean) => {
        const base = 'relative flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap'

        if (variant === 'underline') {
            return cn(
                'px-4 py-2.5 -mb-px border-b-2 rounded-none',
                isActive
                    ? 'border-primary-500 text-primary-400'
                    : 'border-transparent text-gray-400 hover:text-white hover:border-gray-600'
            )
        }

        if (variant === 'pills') {
            return cn(
                'px-4 py-2 rounded-lg',
                isActive
                    ? 'bg-primary-500 text-white'
                    : 'text-gray-400 hover:text-white hover:bg-dark-400'
            )
        }

        // Default variant
        return cn(
            base,
            isActive
                ? 'text-white bg-dark-300'
                : 'text-gray-400 hover:text-white hover:bg-dark-400'
        )
    }

    return (
        <div className={cn('flex flex-col', className)}>
            {/* Tab Navigation */}
            <nav
                className={cn(
                    'flex gap-1 overflow-x-auto pb-2 -mx-4 px-4 md:mx-0 md:px-0 md:pb-0 flex-shrink-0',
                    variant === 'underline' && 'border-b border-white/10 gap-4',
                    tabListClassName
                )}
            >
                {tabs.map((tab) => (
                    <motion.button
                        key={tab.id}
                        onClick={() => onTabChange(tab.id as T)}
                        className={getTabButtonClasses(activeTab === tab.id)}
                        whileTap={{ scale: 0.98 }}
                        transition={{ duration: 0.1 }}
                    >
                        {tab.icon && <span className="flex-shrink-0">{tab.icon}</span>}
                        <span>{tab.label}</span>
                    </motion.button>
                ))}
            </nav>

            {/* Tab Content - All visited tabs stay in DOM */}
            <div className={cn('flex-1 relative', contentClassName)}>
                <AnimatePresence mode="wait" initial={false}>
                    {[...visitedTabs].map((tabId) => {
                        const isActive = tabId === activeTab

                        // Only render the active tab with animation
                        if (!isActive) return null

                        return (
                            <motion.div
                                key={tabId}
                                initial="initial"
                                animate="animate"
                                exit="exit"
                                variants={tabContentVariants}
                                className="w-full"
                            >
                                {children(tabId)}
                            </motion.div>
                        )
                    })}
                </AnimatePresence>
            </div>
        </div>
    )
}

// ============================================================================
// SMOOTH TAB CONTENT - Uses CSS for instant visibility, Framer for animation
// ============================================================================

interface SmoothTabContentProps {
    /** Current active tab ID */
    activeTab: string
    /** Tab content to display */
    children: ReactNode
    /** Loading state - shows skeleton while loading */
    isLoading?: boolean
    /** Custom loading component */
    loadingComponent?: ReactNode
    /** Additional classes for the content container */
    className?: string
}

/**
 * Tab content container with smooth animations and loading state handling.
 * Ensures content is visually prepared before being shown.
 */
export function SmoothTabContent({
    activeTab,
    children,
    isLoading = false,
    loadingComponent,
    className,
}: SmoothTabContentProps) {
    const [isReady, setIsReady] = useState(false)
    const contentRef = useRef<HTMLDivElement>(null)

    // Small delay to ensure content is painted before animating
    useEffect(() => {
        setIsReady(false)
        const timer = requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                setIsReady(true)
            })
        })
        return () => cancelAnimationFrame(timer)
    }, [activeTab])

    const defaultLoader = (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex items-center justify-center py-12"
        >
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
        </motion.div>
    )

    return (
        <AnimatePresence mode="wait" initial={false}>
            {isLoading ? (
                <motion.div
                    key="loading"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.15 }}
                >
                    {loadingComponent || defaultLoader}
                </motion.div>
            ) : (
                <motion.div
                    key={activeTab}
                    ref={contentRef}
                    initial="initial"
                    animate={isReady ? 'animate' : 'initial'}
                    exit="exit"
                    variants={tabContentVariants}
                    className={cn('w-full', className)}
                >
                    {children}
                </motion.div>
            )}
        </AnimatePresence>
    )
}

// ============================================================================
// ANIMATED LIST CONTAINER
// ============================================================================

interface AnimatedListProps {
    children: ReactNode
    className?: string
    /** Key that triggers re-animation when changed */
    animationKey?: string
}

/**
 * Container for lists that should animate their children in a staggered fashion.
 */
export function AnimatedList({ children, className, animationKey }: AnimatedListProps) {
    return (
        <motion.div
            key={animationKey}
            initial="initial"
            animate="animate"
            exit="exit"
            variants={staggerContainerVariants}
            className={className}
        >
            {children}
        </motion.div>
    )
}

// ============================================================================
// ANIMATED SECTION
// ============================================================================

interface AnimatedSectionProps {
    children: ReactNode
    className?: string
    delay?: number
}

/**
 * Individual animated section - fades in with a slight y-offset.
 * Can be used standalone or within AnimatedList for stagger effect.
 */
export function AnimatedSection({ children, className, delay = 0 }: AnimatedSectionProps) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{
                opacity: 1,
                y: 0,
                transition: {
                    duration: 0.4,
                    delay,
                    ease: EASE_CURVE,
                }
            }}
            className={className}
        >
            {children}
        </motion.div>
    )
}

// ============================================================================
// FADE TRANSITION WRAPPER
// ============================================================================

interface FadeTransitionProps {
    show: boolean
    children: ReactNode
    className?: string
    duration?: number
}

/**
 * Simple fade in/out wrapper for conditional content.
 */
export function FadeTransition({
    show,
    children,
    className,
    duration = TRANSITION_DURATION
}: FadeTransitionProps) {
    return (
        <AnimatePresence mode="wait">
            {show && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration }}
                    className={className}
                >
                    {children}
                </motion.div>
            )}
        </AnimatePresence>
    )
}

// ============================================================================
// HOOK: USE PREPARED CONTENT
// ============================================================================

/**
 * Hook that ensures content is "prepared" (rendered to DOM) before showing.
 * This helps prevent visual glitches from content that takes time to render.
 */
export function usePreparedContent(key: string | number): {
    isReady: boolean
    currentKey: string | number
} {
    const [state, setState] = useState({
        isReady: true,
        currentKey: key,
    })

    useEffect(() => {
        if (key !== state.currentKey) {
            setState({ isReady: false, currentKey: key })

            // Use double rAF to ensure the DOM has painted
            const frame1 = requestAnimationFrame(() => {
                const frame2 = requestAnimationFrame(() => {
                    setState({ isReady: true, currentKey: key })
                })
                return () => cancelAnimationFrame(frame2)
            })
            return () => cancelAnimationFrame(frame1)
        }
    }, [key, state.currentKey])

    return state
}

// ============================================================================
// PAGE WRAPPER - Consistent page-level animations
// ============================================================================

interface PageWrapperProps {
    /** Page content to animate */
    children: ReactNode
    /** Additional CSS classes */
    className?: string
    /** Whether to use stagger animation for children */
    stagger?: boolean
}

/**
 * Wraps page content with consistent enter animations.
 * Use this at the top level of each page component to ensure
 * smooth, consistent transitions when navigating between pages.
 */
export function PageWrapper({ children, className, stagger = false }: PageWrapperProps) {
    return (
        <motion.div
            initial="initial"
            animate="animate"
            exit="exit"
            variants={stagger ? staggerContainerVariants : pageVariants}
            className={className}
        >
            {children}
        </motion.div>
    )
}

// ============================================================================
// ANIMATED TAB CONTENT - Standard tab transition wrapper
// ============================================================================

interface AnimatedTabContentProps<T extends string> {
    /** Current active tab key */
    activeTab: T
    /** Tab content to render */
    children: ReactNode
    /** Additional CSS classes */
    className?: string
    /** Whether page is still loading */
    isLoading?: boolean
    /** Custom loading component */
    loadingComponent?: ReactNode
}

/**
 * Standard animated container for tab content.
 * Handles loading states and provides consistent animations.
 * Use this to wrap the content area of any tabbed interface.
 */
export function AnimatedTabContent<T extends string>({
    activeTab,
    children,
    className,
    isLoading = false,
    loadingComponent,
}: AnimatedTabContentProps<T>) {
    const defaultLoader = (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: TRANSITION_DURATION }}
            className="flex items-center justify-center py-12"
        >
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
        </motion.div>
    )

    return (
        <AnimatePresence mode="wait" initial={false}>
            {isLoading ? (
                <motion.div
                    key="loading"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: TRANSITION_DURATION }}
                >
                    {loadingComponent || defaultLoader}
                </motion.div>
            ) : (
                <motion.div
                    key={activeTab}
                    initial="initial"
                    animate="animate"
                    exit="exit"
                    variants={tabContentVariants}
                    className={cn('w-full', className)}
                >
                    {children}
                </motion.div>
            )}
        </AnimatePresence>
    )
}

// ============================================================================
// ANIMATED TAB BUTTON - Consistent tab button with animations
// ============================================================================

interface AnimatedTabButtonProps {
    /** Whether this tab is currently active */
    isActive: boolean
    /** Click handler */
    onClick: () => void
    /** Tab icon (optional) */
    icon?: ReactNode
    /** Tab label */
    label: string
    /** Badge content (optional) */
    badge?: ReactNode
    /** Button variant style */
    variant?: 'default' | 'pills' | 'underline'
    /** Additional CSS classes */
    className?: string
}

/**
 * Consistent animated tab button with hover and press effects.
 */
export function AnimatedTabButton({
    isActive,
    onClick,
    icon,
    label,
    badge,
    variant = 'default',
    className,
}: AnimatedTabButtonProps) {
    const getVariantClasses = () => {
        if (variant === 'underline') {
            return cn(
                'pb-3 sm:pb-4 text-sm font-medium border-b-2 transition-colors whitespace-nowrap',
                isActive
                    ? 'border-primary-500 text-primary-400'
                    : 'border-transparent text-gray-400 hover:text-white'
            )
        }

        if (variant === 'pills') {
            return cn(
                'px-3 sm:px-4 py-2 text-xs sm:text-sm font-medium rounded-lg transition-all whitespace-nowrap',
                isActive
                    ? 'bg-primary-500 text-white'
                    : 'text-gray-400 hover:text-white hover:bg-dark-400'
            )
        }

        // Default variant (sidebar style like settings)
        return cn(
            'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all relative whitespace-nowrap',
            isActive
                ? 'text-white bg-dark-300'
                : 'text-gray-400 hover:text-white hover:bg-dark-400'
        )
    }

    return (
        <motion.button
            onClick={onClick}
            className={cn(getVariantClasses(), className)}
            whileTap={{ scale: 0.98 }}
            transition={{ duration: 0.1 }}
        >
            <span className="relative z-10 flex items-center gap-3">
                {icon}
                {label}
                {badge}
            </span>
        </motion.button>
    )
}

// ============================================================================
// STAGGER PAGE CONTENT - For animating page sections
// ============================================================================

interface StaggerPageContentProps {
    /** Page sections to animate */
    children: ReactNode
    /** Additional CSS classes */
    className?: string
    /** Animation key - changes trigger re-animation */
    animationKey?: string
}

/**
 * Wraps page content sections for staggered animation.
 * Each direct child will animate in sequence.
 */
export function StaggerPageContent({ children, className, animationKey }: StaggerPageContentProps) {
    return (
        <motion.div
            key={animationKey}
            initial="initial"
            animate="animate"
            exit="exit"
            variants={staggerContainerVariants}
            className={className}
        >
            {children}
        </motion.div>
    )
}

/**
 * Individual stagger section - use as direct children of StaggerPageContent.
 */
export function StaggerSection({ children, className }: StaggerItemProps) {
    return (
        <motion.div variants={staggerItemVariants} className={className}>
            {children}
        </motion.div>
    )
}

// ============================================================================
// EXPORTS
// ============================================================================

export {
    type Tab,
    type TabContentWrapperProps,
    type StaggerItemProps,
    type PreRenderedTabsProps,
    type SmoothTabContentProps,
    type AnimatedListProps,
    type AnimatedSectionProps,
    type FadeTransitionProps,
    type PageWrapperProps,
    type AnimatedTabContentProps,
    type AnimatedTabButtonProps,
    type StaggerPageContentProps,
}
