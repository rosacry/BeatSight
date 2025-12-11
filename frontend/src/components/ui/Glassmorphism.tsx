/**
 * Glassmorphism Components - Premium frosted glass UI elements
 * 
 * Modern, translucent components with blur effects for a sophisticated look.
 * These work best on colorful or gradient backgrounds.
 */

import React, { forwardRef } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'

// ============================================================================
// Glass Panel - Base glassmorphism container
// ============================================================================

const glassPanelVariants = cva(
    'relative overflow-hidden backdrop-blur-xl border transition-all duration-300',
    {
        variants: {
            variant: {
                default: 'bg-white/5 border-white/10 hover:bg-white/10',
                light: 'bg-white/10 border-white/20 hover:bg-white/15',
                dark: 'bg-black/20 border-white/5 hover:bg-black/30',
                frost: 'bg-white/[0.02] border-white/[0.05] hover:border-white/10',
                glow: 'bg-white/5 border-primary-500/20 shadow-[0_0_30px_rgba(0,212,255,0.1)]',
                gradient: 'bg-gradient-to-br from-white/10 to-white/5 border-white/10',
            },
            rounded: {
                none: 'rounded-none',
                sm: 'rounded-lg',
                md: 'rounded-xl',
                lg: 'rounded-2xl',
                xl: 'rounded-3xl',
                full: 'rounded-full',
            },
            padding: {
                none: 'p-0',
                sm: 'p-3',
                md: 'p-5',
                lg: 'p-8',
                xl: 'p-12',
            },
        },
        defaultVariants: {
            variant: 'default',
            rounded: 'lg',
            padding: 'md',
        },
    }
)

interface GlassPanelProps
    extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof glassPanelVariants> {
    children: React.ReactNode
    glow?: boolean
    glowColor?: string
}

export const GlassPanel = forwardRef<HTMLDivElement, GlassPanelProps>(
    ({ className, variant, rounded, padding, glow, glowColor = 'cyan', children, ...props }, ref) => {
        return (
            <div
                ref={ref}
                className={cn(
                    glassPanelVariants({ variant, rounded, padding }),
                    glow && `shadow-glow-${glowColor}`,
                    className
                )}
                {...props}
            >
                {children}
            </div>
        )
    }
)
GlassPanel.displayName = 'GlassPanel'

// ============================================================================
// Glass Card - Card with glassmorphism effect
// ============================================================================

interface GlassCardProps extends React.HTMLAttributes<HTMLDivElement> {
    children: React.ReactNode
    hover?: boolean
    glow?: boolean
}

export const GlassCard = forwardRef<HTMLDivElement, GlassCardProps>(
    ({ className, children, hover = true, glow = false, ...props }, ref) => {
        return (
            <div
                ref={ref}
                className={cn(
                    'relative overflow-hidden rounded-2xl',
                    'bg-gradient-to-br from-white/10 via-white/5 to-transparent',
                    'backdrop-blur-xl border border-white/10',
                    'shadow-xl',
                    hover && 'transition-all duration-300 hover:border-white/20 hover:shadow-2xl hover:-translate-y-1',
                    glow && 'shadow-lg shadow-primary-500/20',
                    className
                )}
                {...props}
            >
                {/* Shine effect overlay */}
                <div className="absolute inset-0 bg-gradient-to-br from-white/10 via-transparent to-transparent pointer-events-none" />

                <div className="relative z-10">
                    {children}
                </div>
            </div>
        )
    }
)
GlassCard.displayName = 'GlassCard'

// ============================================================================
// Glass Button - Frosted glass button
// ============================================================================

const glassButtonVariants = cva(
    [
        'relative overflow-hidden inline-flex items-center justify-center gap-2',
        'font-medium transition-all duration-300',
        'backdrop-blur-md border',
        'focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:ring-offset-2 focus:ring-offset-transparent',
        'disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none',
    ],
    {
        variants: {
            variant: {
                default: [
                    'bg-white/10 border-white/20 text-white',
                    'hover:bg-white/20 hover:border-white/30',
                ],
                primary: [
                    'bg-primary-500/20 border-primary-500/30 text-primary-300',
                    'hover:bg-primary-500/30 hover:border-primary-500/50 hover:text-primary-200',
                    'hover:shadow-[0_0_20px_rgba(255,102,171,0.3)]',
                ],
                accent: [
                    'bg-magenta-500/20 border-magenta-500/30 text-magenta-300',
                    'hover:bg-magenta-500/30 hover:border-magenta-500/50 hover:text-magenta-200',
                    'hover:shadow-[0_0_20px_rgba(255,50,150,0.3)]',
                ],
                gradient: [
                    'bg-gradient-to-r from-primary-500/20 to-magenta-500/20',
                    'border-transparent text-white',
                    'hover:from-primary-500/30 hover:to-magenta-500/30',
                ],
                ghost: [
                    'bg-transparent border-transparent text-white/70',
                    'hover:bg-white/10 hover:text-white',
                ],
            },
            size: {
                sm: 'px-3 py-1.5 text-sm rounded-lg',
                md: 'px-4 py-2 text-sm rounded-xl',
                lg: 'px-6 py-3 text-base rounded-xl',
                xl: 'px-8 py-4 text-lg rounded-2xl',
            },
        },
        defaultVariants: {
            variant: 'default',
            size: 'md',
        },
    }
)

interface GlassButtonProps
    extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof glassButtonVariants> {
    children: React.ReactNode
    loading?: boolean
}

export const GlassButton = forwardRef<HTMLButtonElement, GlassButtonProps>(
    ({ className, variant, size, children, loading, disabled, ...props }, ref) => {
        return (
            <button
                ref={ref}
                className={cn(glassButtonVariants({ variant, size }), className)}
                disabled={disabled || loading}
                {...props}
            >
                {loading && (
                    <svg
                        className="animate-spin -ml-1 mr-2 h-4 w-4"
                        xmlns="http://www.w3.org/2000/svg"
                        fill="none"
                        viewBox="0 0 24 24"
                    >
                        <circle
                            className="opacity-25"
                            cx="12"
                            cy="12"
                            r="10"
                            stroke="currentColor"
                            strokeWidth="4"
                        />
                        <path
                            className="opacity-75"
                            fill="currentColor"
                            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                        />
                    </svg>
                )}
                {children}
            </button>
        )
    }
)
GlassButton.displayName = 'GlassButton'

// ============================================================================
// Glass Input - Frosted glass input field
// ============================================================================

interface GlassInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
    label?: string
    error?: string
    icon?: React.ReactNode
}

export const GlassInput = forwardRef<HTMLInputElement, GlassInputProps>(
    ({ className, label, error, icon, ...props }, ref) => {
        return (
            <div className="w-full">
                {label && (
                    <label className="block text-sm font-medium text-white/70 mb-2">
                        {label}
                    </label>
                )}
                <div className="relative">
                    {icon && (
                        <div className="absolute left-3 top-1/2 -translate-y-1/2 text-white/40">
                            {icon}
                        </div>
                    )}
                    <input
                        ref={ref}
                        className={cn(
                            'w-full rounded-xl px-4 py-3',
                            'bg-white/5 backdrop-blur-md',
                            'border border-white/10',
                            'text-white placeholder:text-white/30',
                            'transition-all duration-300',
                            'focus:outline-none focus:border-primary-500/50 focus:ring-2 focus:ring-primary-500/20',
                            'hover:bg-white/10 hover:border-white/20',
                            icon && 'pl-10',
                            error && 'border-red-500/50 focus:border-red-500/50 focus:ring-red-500/20',
                            className
                        )}
                        {...props}
                    />
                </div>
                {error && (
                    <p className="mt-2 text-sm text-red-400">{error}</p>
                )}
            </div>
        )
    }
)
GlassInput.displayName = 'GlassInput'

// ============================================================================
// Glass Select - Frosted glass dropdown
// ============================================================================

interface GlassSelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
    label?: string
    error?: string
    options: { value: string; label: string }[]
}

export const GlassSelect = forwardRef<HTMLSelectElement, GlassSelectProps>(
    ({ className, label, error, options, ...props }, ref) => {
        return (
            <div className="w-full">
                {label && (
                    <label className="block text-sm font-medium text-white/70 mb-2">
                        {label}
                    </label>
                )}
                <select
                    ref={ref}
                    className={cn(
                        'w-full rounded-xl px-4 py-3',
                        'bg-white/5 backdrop-blur-md',
                        'border border-white/10',
                        'text-white',
                        'transition-all duration-300',
                        'focus:outline-none focus:border-primary-500/50 focus:ring-2 focus:ring-primary-500/20',
                        'hover:bg-white/10 hover:border-white/20',
                        'cursor-pointer appearance-none',
                        'bg-[url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' fill=\'none\' viewBox=\'0 0 24 24\' stroke=\'white\'%3E%3Cpath stroke-linecap=\'round\' stroke-linejoin=\'round\' stroke-width=\'2\' d=\'M19 9l-7 7-7-7\'%3E%3C/path%3E%3C/svg%3E")] bg-[length:1.5rem] bg-no-repeat bg-[right_0.75rem_center]',
                        error && 'border-red-500/50',
                        className
                    )}
                    {...props}
                >
                    {options.map((option) => (
                        <option
                            key={option.value}
                            value={option.value}
                            className="bg-dark-500 text-white"
                        >
                            {option.label}
                        </option>
                    ))}
                </select>
                {error && (
                    <p className="mt-2 text-sm text-red-400">{error}</p>
                )}
            </div>
        )
    }
)
GlassSelect.displayName = 'GlassSelect'

// ============================================================================
// Glass Navigation - Frosted glass navbar
// ============================================================================

interface GlassNavProps {
    children: React.ReactNode
    className?: string
    sticky?: boolean
}

export function GlassNav({ children, className, sticky = true }: GlassNavProps) {
    return (
        <nav
            className={cn(
                'w-full px-6 py-4',
                'bg-black/30 backdrop-blur-xl',
                'border-b border-white/5',
                sticky && 'sticky top-0 z-50',
                className
            )}
        >
            {children}
        </nav>
    )
}

// ============================================================================
// Glass Modal Overlay
// ============================================================================

interface GlassOverlayProps {
    children: React.ReactNode
    className?: string
    onClose?: () => void
}

export function GlassOverlay({ children, className, onClose }: GlassOverlayProps) {
    return (
        <div
            className={cn(
                'fixed inset-0 z-50',
                'flex items-center justify-center',
                'bg-black/40 backdrop-blur-sm',
                className
            )}
            onClick={(e) => {
                if (e.target === e.currentTarget && onClose) {
                    onClose()
                }
            }}
        >
            {children}
        </div>
    )
}

// ============================================================================
// Glass Badge - Small glass status indicator
// ============================================================================

const glassBadgeVariants = cva(
    'inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-full backdrop-blur-md border',
    {
        variants: {
            variant: {
                default: 'bg-white/10 border-white/20 text-white',
                success: 'bg-green-500/20 border-green-500/30 text-green-300',
                warning: 'bg-yellow-500/20 border-yellow-500/30 text-yellow-300',
                error: 'bg-red-500/20 border-red-500/30 text-red-300',
                info: 'bg-primary-500/20 border-primary-500/30 text-primary-300',
                premium: 'bg-gradient-to-r from-yellow-500/20 to-orange-500/20 border-yellow-500/30 text-yellow-300',
            },
        },
        defaultVariants: {
            variant: 'default',
        },
    }
)

interface GlassBadgeProps
    extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof glassBadgeVariants> {
    children: React.ReactNode
    dot?: boolean
}

export function GlassBadge({ className, variant, children, dot, ...props }: GlassBadgeProps) {
    return (
        <span className={cn(glassBadgeVariants({ variant }), className)} {...props}>
            {dot && (
                <span className={cn(
                    'w-1.5 h-1.5 rounded-full',
                    variant === 'success' && 'bg-green-400',
                    variant === 'warning' && 'bg-yellow-400',
                    variant === 'error' && 'bg-red-400',
                    variant === 'info' && 'bg-primary-400',
                    variant === 'premium' && 'bg-yellow-400',
                    !variant && 'bg-white/50',
                )} />
            )}
            {children}
        </span>
    )
}

// ============================================================================
// Glass Divider
// ============================================================================

interface GlassDividerProps {
    className?: string
    orientation?: 'horizontal' | 'vertical'
    gradient?: boolean
}

export function GlassDivider({
    className,
    orientation = 'horizontal',
    gradient = false
}: GlassDividerProps) {
    if (orientation === 'vertical') {
        return (
            <div
                className={cn(
                    'w-px self-stretch',
                    gradient
                        ? 'bg-gradient-to-b from-transparent via-white/20 to-transparent'
                        : 'bg-white/10',
                    className
                )}
            />
        )
    }

    return (
        <div
            className={cn(
                'h-px w-full',
                gradient
                    ? 'bg-gradient-to-r from-transparent via-white/20 to-transparent'
                    : 'bg-white/10',
                className
            )}
        />
    )
}

// ============================================================================
// Glass Skeleton - Loading placeholder
// ============================================================================

interface GlassSkeletonProps {
    className?: string
    width?: string | number
    height?: string | number
    rounded?: 'none' | 'sm' | 'md' | 'lg' | 'full'
}

export function GlassSkeleton({
    className,
    width,
    height,
    rounded = 'md'
}: GlassSkeletonProps) {
    const roundedClasses = {
        none: 'rounded-none',
        sm: 'rounded',
        md: 'rounded-lg',
        lg: 'rounded-xl',
        full: 'rounded-full',
    }

    return (
        <div
            className={cn(
                'bg-white/5 animate-pulse',
                roundedClasses[rounded],
                className
            )}
            style={{ width, height }}
        />
    )
}

// ============================================================================
// Glass Progress Bar
// ============================================================================

interface GlassProgressProps {
    value: number
    max?: number
    className?: string
    showLabel?: boolean
    color?: 'cyan' | 'magenta' | 'gradient'
}

export function GlassProgress({
    value,
    max = 100,
    className,
    showLabel = false,
    color = 'cyan'
}: GlassProgressProps) {
    const percentage = Math.min(Math.max((value / max) * 100, 0), 100)

    const colorClasses = {
        cyan: 'bg-primary-500',
        magenta: 'bg-magenta-500',
        gradient: 'bg-gradient-to-r from-primary-500 to-magenta-500',
    }

    return (
        <div className={cn('w-full', className)}>
            {showLabel && (
                <div className="flex justify-between text-sm text-white/70 mb-2">
                    <span>Progress</span>
                    <span>{Math.round(percentage)}%</span>
                </div>
            )}
            <div className="h-2 rounded-full bg-white/10 backdrop-blur-md overflow-hidden">
                <div
                    className={cn(
                        'h-full rounded-full transition-all duration-500 ease-out',
                        colorClasses[color]
                    )}
                    style={{ width: `${percentage}%` }}
                />
            </div>
        </div>
    )
}
