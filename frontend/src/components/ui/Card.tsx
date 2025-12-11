/**
 * Modern Card component system with hover effects and variants.
 */

import { forwardRef, type HTMLAttributes, type ReactNode } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { clsx } from 'clsx'

const cardVariants = cva(
    // Base styles
    [
        'rounded-xl transition-all duration-200',
        'bg-dark-400',
    ],
    {
        variants: {
            variant: {
                default: 'border border-dark-300',
                elevated: [
                    'border border-dark-300',
                    'shadow-xl shadow-black/20',
                    'hover:shadow-2xl hover:shadow-black/30',
                ],
                outlined: 'border-2 border-dark-300',
                ghost: 'bg-transparent border-none',
                glow: [
                    'border border-primary-500/30',
                    'shadow-lg shadow-primary-500/10',
                    'hover:shadow-xl hover:shadow-primary-500/20',
                    'hover:border-primary-500/50',
                ],
                gradient: [
                    'border border-transparent',
                    'bg-dark-400',
                    'shadow-lg',
                ],
                interactive: [
                    'border border-dark-300',
                    'hover:bg-dark-300',
                    'hover:border-dark-200',
                    'cursor-pointer',
                ],
            },
            padding: {
                none: 'p-0',
                sm: 'p-4',
                md: 'p-6',
                lg: 'p-8',
            },
            hoverEffect: {
                none: '',
                lift: 'hover:-translate-y-1',
                scale: 'hover:scale-[1.02]',
                glow: 'hover:shadow-[0_0_30px_rgba(14,165,233,0.15)]',
            },
        },
        defaultVariants: {
            variant: 'default',
            padding: 'md',
            hoverEffect: 'none',
        },
    }
)

export interface CardProps
    extends HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof cardVariants> { }

export const Card = forwardRef<HTMLDivElement, CardProps>(
    ({ className, variant, padding, hoverEffect, ...props }, ref) => {
        return (
            <div
                ref={ref}
                className={clsx(cardVariants({ variant, padding, hoverEffect }), className)}
                {...props}
            />
        )
    }
)

Card.displayName = 'Card'

/**
 * Card Header component
 */
interface CardHeaderProps extends HTMLAttributes<HTMLDivElement> {
    title?: string
    description?: string
    action?: ReactNode
}

export const CardHeader = forwardRef<HTMLDivElement, CardHeaderProps>(
    ({ className, title, description, action, children, ...props }, ref) => {
        return (
            <div
                ref={ref}
                className={clsx('flex items-start justify-between gap-4', className)}
                {...props}
            >
                <div className="space-y-1">
                    {title && <h3 className="text-lg font-semibold text-white">{title}</h3>}
                    {description && <p className="text-sm text-gray-400">{description}</p>}
                    {children}
                </div>
                {action && <div className="shrink-0">{action}</div>}
            </div>
        )
    }
)

CardHeader.displayName = 'CardHeader'

/**
 * Card Content component
 */
export const CardContent = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
    ({ className, ...props }, ref) => {
        return <div ref={ref} className={clsx('mt-4', className)} {...props} />
    }
)

CardContent.displayName = 'CardContent'

/**
 * Card Footer component
 */
export const CardFooter = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
    ({ className, ...props }, ref) => {
        return (
            <div
                ref={ref}
                className={clsx(
                    'mt-6 pt-4 border-t border-white/10/50 flex items-center gap-3',
                    className
                )}
                {...props}
            />
        )
    }
)

CardFooter.displayName = 'CardFooter'

/**
 * Feature Card - Card optimized for feature showcases
 */
interface FeatureCardProps extends HTMLAttributes<HTMLDivElement> {
    icon?: ReactNode
    title: string
    description: string
}

export const FeatureCard = forwardRef<HTMLDivElement, FeatureCardProps>(
    ({ className, icon, title, description, ...props }, ref) => {
        return (
            <Card
                ref={ref}
                variant="elevated"
                hoverEffect="lift"
                className={clsx('group', className)}
                {...props}
            >
                {icon && (
                    <div className="mb-4 inline-flex p-3 rounded-xl bg-primary-500/10 text-primary-400 group-hover:bg-primary-500/20 transition-colors">
                        {icon}
                    </div>
                )}
                <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
                <p className="text-gray-400 text-sm">{description}</p>
            </Card>
        )
    }
)

FeatureCard.displayName = 'FeatureCard'

/**
 * Stat Card - Card for displaying metrics/statistics
 */
interface StatCardProps extends HTMLAttributes<HTMLDivElement> {
    label: string
    value: string | number
    change?: {
        value: number
        trend: 'up' | 'down' | 'neutral'
    }
    icon?: ReactNode
}

export const StatCard = forwardRef<HTMLDivElement, StatCardProps>(
    ({ className, label, value, change, icon, ...props }, ref) => {
        const trendColors = {
            up: 'text-green-400',
            down: 'text-red-400',
            neutral: 'text-gray-400',
        }

        const trendIcons = {
            up: '↑',
            down: '↓',
            neutral: '→',
        }

        return (
            <Card ref={ref} variant="default" className={className} {...props}>
                <div className="flex items-start justify-between">
                    <div>
                        <p className="text-sm text-gray-400 mb-1">{label}</p>
                        <p className="text-3xl font-bold text-white">{value}</p>
                        {change && (
                            <p className={clsx('text-sm mt-1 flex items-center gap-1', trendColors[change.trend])}>
                                <span>{trendIcons[change.trend]}</span>
                                <span>{Math.abs(change.value)}%</span>
                            </p>
                        )}
                    </div>
                    {icon && (
                        <div className="p-2 rounded-lg bg-dark-300/50 text-gray-400">
                            {icon}
                        </div>
                    )}
                </div>
            </Card>
        )
    }
)

StatCard.displayName = 'StatCard'

/**
 * Glowing Border Card - Card with animated gradient border
 */
interface GlowingCardProps extends HTMLAttributes<HTMLDivElement> {
    gradientFrom?: string
    gradientTo?: string
}

export const GlowingCard = forwardRef<HTMLDivElement, GlowingCardProps>(
    ({ className, gradientFrom = 'from-primary-500', gradientTo = 'to-accent-500', children, ...props }, ref) => {
        return (
            <div
                ref={ref}
                className={clsx(
                    'relative p-[1px] rounded-xl overflow-hidden',
                    'bg-gradient-to-r',
                    gradientFrom,
                    gradientTo,
                    className
                )}
                {...props}
            >
                {/* Animated glow effect */}
                <div
                    className="absolute inset-0 bg-gradient-to-r opacity-50 blur-xl animate-pulse-slow"
                    style={{
                        backgroundImage: `linear-gradient(to right, var(--tw-gradient-from), var(--tw-gradient-to))`,
                    }}
                />

                {/* Card content */}
                <div className="relative bg-dark-500 rounded-xl p-6">
                    {children}
                </div>
            </div>
        )
    }
)

GlowingCard.displayName = 'GlowingCard'

export { cardVariants }
