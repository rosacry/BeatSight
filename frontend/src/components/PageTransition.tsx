/**
 * PageTransition - Animated page transitions using Framer Motion
 * 
 * Provides smooth fade and slide animations between route changes,
 * inspired by osu!'s fluid navigation experience.
 */

import { ReactNode } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useLocation } from 'react-router-dom'

interface PageTransitionProps {
    children: ReactNode
    mode?: 'fade' | 'slide' | 'scale' | 'slideUp'
}

const variants = {
    fade: {
        initial: { opacity: 0 },
        animate: { opacity: 1 },
        exit: { opacity: 0 },
    },
    slide: {
        initial: { opacity: 0, x: 20 },
        animate: { opacity: 1, x: 0 },
        exit: { opacity: 0, x: -20 },
    },
    slideUp: {
        initial: { opacity: 0, y: 20 },
        animate: { opacity: 1, y: 0 },
        exit: { opacity: 0, y: -20 },
    },
    scale: {
        initial: { opacity: 0, scale: 0.95 },
        animate: { opacity: 1, scale: 1 },
        exit: { opacity: 0, scale: 1.05 },
    },
}

/**
 * Wraps page content with animated transitions
 * Use around individual page content for per-page animations
 */
export function PageTransition({ children, mode = 'slideUp' }: PageTransitionProps) {
    const location = useLocation()
    const variant = variants[mode]

    return (
        <AnimatePresence mode="wait">
            <motion.div
                key={location.pathname}
                initial={variant.initial}
                animate={variant.animate}
                exit={variant.exit}
                transition={{
                    duration: 0.25,
                    ease: [0.25, 0.46, 0.45, 0.94], // Custom ease curve
                }}
            >
                {children}
            </motion.div>
        </AnimatePresence>
    )
}

/**
 * Wrapper for AnimatedRoutes - wraps around Routes component
 */
interface AnimatedRoutesProps {
    children: ReactNode
}

export function AnimatedRoutes({ children }: AnimatedRoutesProps) {
    const location = useLocation()

    return (
        <AnimatePresence mode="wait">
            <motion.div
                key={location.pathname}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{
                    duration: 0.2,
                    ease: [0.25, 0.46, 0.45, 0.94],
                }}
                className="min-h-full"
            >
                {children}
            </motion.div>
        </AnimatePresence>
    )
}

/**
 * Individual page wrapper for staggered content animation
 * Children with data-animate attribute will animate in sequence
 */
interface StaggeredPageProps {
    children: ReactNode
    className?: string
}

export function StaggeredPage({ children, className = '' }: StaggeredPageProps) {
    return (
        <motion.div
            className={className}
            initial="hidden"
            animate="visible"
            variants={{
                hidden: { opacity: 0 },
                visible: {
                    opacity: 1,
                    transition: {
                        staggerChildren: 0.08,
                        delayChildren: 0.1,
                    },
                },
            }}
        >
            {children}
        </motion.div>
    )
}

/**
 * Child element for StaggeredPage
 */
interface StaggerItemProps {
    children: ReactNode
    className?: string
}

export function StaggerItem({ children, className = '' }: StaggerItemProps) {
    return (
        <motion.div
            className={className}
            variants={{
                hidden: { opacity: 0, y: 20 },
                visible: {
                    opacity: 1,
                    y: 0,
                    transition: {
                        duration: 0.4,
                        ease: [0.25, 0.46, 0.45, 0.94],
                    },
                },
            }}
        >
            {children}
        </motion.div>
    )
}
