/**
 * AnimatedComponents - Premium Framer Motion powered components
 * 
 * High-quality, physics-based animations for a polished user experience.
 * These components complement the existing CSS animations with JS-driven motion.
 */

import React, { forwardRef, useState } from 'react'
import { motion, AnimatePresence, Variants, useMotionValue, useTransform, useSpring, animate } from 'framer-motion'
import { cn } from '../../lib/utils'

// ============================================================================
// Animation Presets
// ============================================================================

export const fadeInUp: Variants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
        opacity: 1,
        y: 0,
        transition: { duration: 0.5, ease: [0.25, 0.46, 0.45, 0.94] }
    },
    exit: { opacity: 0, y: -10, transition: { duration: 0.3 } }
}

export const fadeInScale: Variants = {
    hidden: { opacity: 0, scale: 0.95 },
    visible: {
        opacity: 1,
        scale: 1,
        transition: { duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] }
    },
    exit: { opacity: 0, scale: 0.95, transition: { duration: 0.2 } }
}

export const staggerContainer: Variants = {
    hidden: { opacity: 0 },
    visible: {
        opacity: 1,
        transition: {
            staggerChildren: 0.1,
            delayChildren: 0.1,
        }
    }
}

export const slideInFromLeft: Variants = {
    hidden: { opacity: 0, x: -30 },
    visible: {
        opacity: 1,
        x: 0,
        transition: { duration: 0.5, ease: 'easeOut' }
    }
}

export const slideInFromRight: Variants = {
    hidden: { opacity: 0, x: 30 },
    visible: {
        opacity: 1,
        x: 0,
        transition: { duration: 0.5, ease: 'easeOut' }
    }
}

// ============================================================================
// Animated Container
// ============================================================================

interface AnimatedContainerProps {
    children: React.ReactNode
    className?: string
    variants?: Variants
    delay?: number
    once?: boolean
}

export const AnimatedContainer = forwardRef<HTMLDivElement, AnimatedContainerProps>(
    ({ children, className, variants = fadeInUp, delay = 0, once = true }, ref) => {
        return (
            <motion.div
                ref={ref}
                initial="hidden"
                whileInView="visible"
                viewport={{ once, margin: '-50px' }}
                variants={variants}
                transition={{ delay }}
                className={className}
            >
                {children}
            </motion.div>
        )
    }
)
AnimatedContainer.displayName = 'AnimatedContainer'

// ============================================================================
// Stagger List
// ============================================================================

interface StaggerListProps {
    children: React.ReactNode
    className?: string
    itemClassName?: string
    delay?: number
}

export function StaggerList({ children, className, itemClassName, delay = 0 }: StaggerListProps) {
    return (
        <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
            transition={{ delay }}
            className={className}
        >
            {React.Children.map(children, (child, index) => (
                <motion.div key={index} variants={fadeInUp} className={itemClassName}>
                    {child}
                </motion.div>
            ))}
        </motion.div>
    )
}

// ============================================================================
// Magnetic Button - Follows cursor with magnetic effect
// ============================================================================

interface MagneticButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    children: React.ReactNode
    strength?: number
}

export function MagneticButton({
    children,
    className,
    strength = 0.3,
    ...props
}: MagneticButtonProps) {
    const x = useMotionValue(0)
    const y = useMotionValue(0)

    const springConfig = { damping: 15, stiffness: 150 }
    const springX = useSpring(x, springConfig)
    const springY = useSpring(y, springConfig)

    const handleMouseMove = (e: React.MouseEvent<HTMLButtonElement>) => {
        const rect = e.currentTarget.getBoundingClientRect()
        const centerX = rect.left + rect.width / 2
        const centerY = rect.top + rect.height / 2

        x.set((e.clientX - centerX) * strength)
        y.set((e.clientY - centerY) * strength)
    }

    const handleMouseLeave = () => {
        x.set(0)
        y.set(0)
    }

    // Exclude conflicting event handlers from props to avoid type conflicts with Framer Motion
    const { onDrag, onDragStart, onDragEnd, ...restProps } = props as any;

    return (
        <motion.button
            style={{ x: springX, y: springY }}
            onMouseMove={handleMouseMove}
            onMouseLeave={handleMouseLeave}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className={cn(
                'relative overflow-hidden rounded-lg px-6 py-3',
                'bg-gradient-to-r from-cyan-500 to-magenta-500',
                'text-white font-semibold shadow-lg',
                'transition-shadow hover:shadow-glow-cyan',
                className
            )}
            {...restProps}
        >
            {children}
        </motion.button>
    )
}

// ============================================================================
// Floating Card - Gentle floating animation with 3D tilt
// ============================================================================

interface FloatingCardProps {
    children: React.ReactNode
    className?: string
    intensity?: number
}

export function FloatingCard({ children, className, intensity = 10 }: FloatingCardProps) {
    const x = useMotionValue(0)
    const y = useMotionValue(0)

    const rotateX = useTransform(y, [-100, 100], [intensity, -intensity])
    const rotateY = useTransform(x, [-100, 100], [-intensity, intensity])

    const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
        const rect = e.currentTarget.getBoundingClientRect()
        const centerX = rect.left + rect.width / 2
        const centerY = rect.top + rect.height / 2

        x.set(e.clientX - centerX)
        y.set(e.clientY - centerY)
    }

    const handleMouseLeave = () => {
        x.set(0)
        y.set(0)
    }

    return (
        <motion.div
            style={{
                rotateX,
                rotateY,
                transformStyle: 'preserve-3d',
            }}
            onMouseMove={handleMouseMove}
            onMouseLeave={handleMouseLeave}
            animate={{ y: [0, -8, 0] }}
            transition={{
                y: { duration: 4, repeat: Infinity, ease: 'easeInOut' }
            }}
            className={cn(
                'relative rounded-2xl p-6',
                'bg-gradient-to-br from-gray-900/90 to-gray-800/90',
                'border border-white/10 backdrop-blur-xl',
                'shadow-2xl',
                className
            )}
        >
            <div style={{ transform: 'translateZ(20px)' }}>
                {children}
            </div>
        </motion.div>
    )
}

// ============================================================================
// Reveal Text - Character by character reveal animation
// ============================================================================

interface RevealTextProps {
    text: string
    className?: string
    delay?: number
    speed?: number
}

export function RevealText({ text, className, delay = 0, speed = 0.03 }: RevealTextProps) {
    const words = text.split(' ')

    const container: Variants = {
        hidden: { opacity: 0 },
        visible: {
            opacity: 1,
            transition: { staggerChildren: speed, delayChildren: delay }
        }
    }

    const child: Variants = {
        hidden: {
            opacity: 0,
            y: 20,
            rotateX: -90,
        },
        visible: {
            opacity: 1,
            y: 0,
            rotateX: 0,
            transition: {
                type: 'spring',
                damping: 12,
                stiffness: 100,
            }
        }
    }

    return (
        <motion.span
            variants={container}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            className={cn('inline-flex flex-wrap', className)}
        >
            {words.map((word, wordIndex) => (
                <span key={wordIndex} className="mr-2 inline-flex overflow-hidden">
                    {word.split('').map((char, charIndex) => (
                        <motion.span
                            key={charIndex}
                            variants={child}
                            className="inline-block"
                        >
                            {char}
                        </motion.span>
                    ))}
                </span>
            ))}
        </motion.span>
    )
}

// ============================================================================
// Gradient Border Card - Animated gradient border
// ============================================================================

interface GradientBorderCardProps {
    children: React.ReactNode
    className?: string
    borderWidth?: number
    animate?: boolean
}

export function GradientBorderCard({
    children,
    className,
    borderWidth = 2,
    animate = true
}: GradientBorderCardProps) {
    return (
        <div className={cn('relative p-[2px] rounded-2xl overflow-hidden', className)}>
            {/* Animated gradient border */}
            <motion.div
                className="absolute inset-0"
                style={{
                    background: 'linear-gradient(90deg, #00d4ff, #ff3296, #00d4ff)',
                    backgroundSize: '200% 100%',
                }}
                animate={animate ? {
                    backgroundPosition: ['0% 0%', '200% 0%'],
                } : undefined}
                transition={{
                    duration: 3,
                    repeat: Infinity,
                    ease: 'linear',
                }}
            />

            {/* Content container */}
            <div
                className="relative rounded-2xl bg-gray-900 p-6"
                style={{ margin: borderWidth }}
            >
                {children}
            </div>
        </div>
    )
}

// ============================================================================
// Spotlight Card - Follows cursor with spotlight effect
// ============================================================================

interface SpotlightCardProps {
    children: React.ReactNode
    className?: string
    spotlightColor?: string
}

export function SpotlightCard({
    children,
    className,
    spotlightColor = 'rgba(0, 212, 255, 0.15)'
}: SpotlightCardProps) {
    const [position, setPosition] = useState({ x: 0, y: 0 })
    const [isHovering, setIsHovering] = useState(false)

    const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
        const rect = e.currentTarget.getBoundingClientRect()
        setPosition({
            x: e.clientX - rect.left,
            y: e.clientY - rect.top,
        })
    }

    return (
        <motion.div
            className={cn(
                'relative overflow-hidden rounded-2xl',
                'bg-gray-900/80 border border-white/10',
                'backdrop-blur-xl',
                className
            )}
            onMouseMove={handleMouseMove}
            onMouseEnter={() => setIsHovering(true)}
            onMouseLeave={() => setIsHovering(false)}
            whileHover={{ scale: 1.02 }}
            transition={{ duration: 0.2 }}
        >
            {/* Spotlight effect */}
            <AnimatePresence>
                {isHovering && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="pointer-events-none absolute inset-0"
                        style={{
                            background: `radial-gradient(600px circle at ${position.x}px ${position.y}px, ${spotlightColor}, transparent 40%)`,
                        }}
                    />
                )}
            </AnimatePresence>

            <div className="relative z-10 p-6">
                {children}
            </div>
        </motion.div>
    )
}

// ============================================================================
// Counter Animation - Animated number counter
// ============================================================================

interface AnimatedCounterProps {
    value: number
    duration?: number
    className?: string
    prefix?: string
    suffix?: string
    decimals?: number
}

export function AnimatedCounter({
    value,
    duration = 2,
    className,
    prefix = '',
    suffix = '',
    decimals = 0
}: AnimatedCounterProps) {
    const count = useMotionValue(0)
    const rounded = useTransform(count, (latest) => {
        const formatted = latest.toFixed(decimals)
        return `${prefix}${formatted}${suffix}`
    })

    React.useEffect(() => {
        const controls = animate(count, value, {
            duration,
            ease: 'easeOut',
        })
        return () => controls.stop()
    }, [value, duration, count])

    return (
        <motion.span className={className}>
            {rounded}
        </motion.span>
    )
}

// ============================================================================
// Scroll Progress Bar
// ============================================================================

interface ScrollProgressProps {
    className?: string
    color?: string
}

export function ScrollProgress({ className, color = '#00d4ff' }: ScrollProgressProps) {
    const [progress, setProgress] = useState(0)

    React.useEffect(() => {
        const handleScroll = () => {
            const scrollTop = window.scrollY
            const docHeight = document.documentElement.scrollHeight - window.innerHeight
            const scrollProgress = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0
            setProgress(scrollProgress)
        }

        window.addEventListener('scroll', handleScroll)
        return () => window.removeEventListener('scroll', handleScroll)
    }, [])

    return (
        <motion.div
            className={cn('fixed top-0 left-0 right-0 h-1 z-50', className)}
            style={{
                scaleX: progress / 100,
                transformOrigin: '0%',
                backgroundColor: color,
            }}
        />
    )
}

// ============================================================================
// Animated List Item - For lists with staggered animations
// ============================================================================

interface AnimatedListItemProps {
    children: React.ReactNode
    className?: string
    index?: number
}

export function AnimatedListItem({ children, className, index = 0 }: AnimatedListItemProps) {
    return (
        <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            transition={{
                duration: 0.3,
                delay: index * 0.05,
                ease: 'easeOut'
            }}
            className={className}
        >
            {children}
        </motion.div>
    )
}

// ============================================================================
// Parallax Container
// ============================================================================

interface ParallaxContainerProps {
    children: React.ReactNode
    className?: string
    speed?: number
}

export function ParallaxContainer({ children, className, speed = 0.5 }: ParallaxContainerProps) {
    const [scrollY, setScrollY] = useState(0)

    React.useEffect(() => {
        const handleScroll = () => setScrollY(window.scrollY)
        window.addEventListener('scroll', handleScroll)
        return () => window.removeEventListener('scroll', handleScroll)
    }, [])

    return (
        <motion.div
            style={{ y: scrollY * speed }}
            className={className}
        >
            {children}
        </motion.div>
    )
}

// ============================================================================
// Morphing Shape Background
// ============================================================================

interface MorphingBackgroundProps {
    className?: string
    colors?: [string, string]
}

export function MorphingBackground({
    className,
    colors = ['#00d4ff', '#ff3296']
}: MorphingBackgroundProps) {
    return (
        <div className={cn('absolute inset-0 overflow-hidden', className)}>
            <motion.div
                className="absolute -inset-[100%] opacity-30"
                style={{
                    background: `radial-gradient(circle, ${colors[0]} 0%, transparent 50%)`,
                }}
                animate={{
                    x: ['0%', '50%', '0%'],
                    y: ['0%', '30%', '0%'],
                    scale: [1, 1.2, 1],
                }}
                transition={{
                    duration: 20,
                    repeat: Infinity,
                    ease: 'easeInOut',
                }}
            />
            <motion.div
                className="absolute -inset-[100%] opacity-30"
                style={{
                    background: `radial-gradient(circle, ${colors[1]} 0%, transparent 50%)`,
                }}
                animate={{
                    x: ['50%', '0%', '50%'],
                    y: ['30%', '0%', '30%'],
                    scale: [1.2, 1, 1.2],
                }}
                transition={{
                    duration: 20,
                    repeat: Infinity,
                    ease: 'easeInOut',
                }}
            />
        </div>
    )
}

// ============================================================================
// Animated Presence Wrapper - For route transitions
// ============================================================================

interface PageTransitionProps {
    children: React.ReactNode
    className?: string
}

export function PageTransition({ children, className }: PageTransitionProps) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{
                duration: 0.4,
                ease: [0.25, 0.46, 0.45, 0.94]
            }}
            className={className}
        >
            {children}
        </motion.div>
    )
}

// Re-export AnimatePresence for convenience
export { AnimatePresence, motion }
