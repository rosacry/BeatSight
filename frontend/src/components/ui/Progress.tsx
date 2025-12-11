/**
 * Progress Components
 * Modern progress indicators with various styles and animations.
 */

import React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'

// ============================================================================
// Progress Bar Variants
// ============================================================================

const progressVariants = cva(
    ['relative overflow-hidden rounded-full bg-dark-400/50'],
    {
        variants: {
            size: {
                xs: 'h-1',
                sm: 'h-1.5',
                md: 'h-2',
                lg: 'h-3',
                xl: 'h-4',
            },
        },
        defaultVariants: {
            size: 'md',
        },
    }
)

const progressBarVariants = cva(
    ['h-full rounded-full transition-all duration-300 ease-out'],
    {
        variants: {
            variant: {
                default: 'bg-primary-500',
                gradient: 'bg-gradient-to-r from-primary-500 to-fuchsia-500',
                success: 'bg-green-500',
                warning: 'bg-amber-500',
                danger: 'bg-red-500',
                rainbow: 'bg-gradient-to-r from-primary-500 via-fuchsia-500 to-amber-500',
            },
            animated: {
                true: '',
                false: '',
            },
        },
        compoundVariants: [
            {
                animated: true,
                className: 'animate-pulse',
            },
        ],
        defaultVariants: {
            variant: 'default',
            animated: false,
        },
    }
)

// ============================================================================
// Progress Bar Component
// ============================================================================

export interface ProgressBarProps
    extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof progressVariants>,
    VariantProps<typeof progressBarVariants> {
    value: number
    max?: number
    showValue?: boolean
    label?: string
    formatValue?: (value: number, max: number) => string
    indeterminate?: boolean
    glow?: boolean
}

export function ProgressBar({
    value,
    max = 100,
    showValue = false,
    label,
    formatValue,
    indeterminate = false,
    glow = false,
    size,
    variant,
    animated,
    className,
    ...props
}: ProgressBarProps) {
    const percentage = Math.min(100, Math.max(0, (value / max) * 100))

    const displayValue = formatValue
        ? formatValue(value, max)
        : `${Math.round(percentage)}%`

    return (
        <div className={cn('w-full', className)} {...props}>
            {(label || showValue) && (
                <div className="flex justify-between items-center mb-1.5">
                    {label && <span className="text-sm text-gray-300">{label}</span>}
                    {showValue && <span className="text-sm text-gray-400">{displayValue}</span>}
                </div>
            )}
            <div className={cn(progressVariants({ size }))}>
                <div
                    className={cn(
                        progressBarVariants({ variant, animated }),
                        indeterminate && 'w-1/3 animate-indeterminate',
                        glow && 'shadow-lg shadow-cyan-500/30'
                    )}
                    style={{ width: indeterminate ? undefined : `${percentage}%` }}
                    role="progressbar"
                    aria-valuenow={indeterminate ? undefined : value}
                    aria-valuemin={0}
                    aria-valuemax={max}
                />
            </div>
        </div>
    )
}

// ============================================================================
// Circular Progress Component
// ============================================================================

export interface CircularProgressProps extends React.HTMLAttributes<HTMLDivElement> {
    value: number
    max?: number
    size?: number
    strokeWidth?: number
    variant?: 'default' | 'gradient' | 'success' | 'warning' | 'danger'
    showValue?: boolean
    label?: string
    formatValue?: (value: number, max: number) => string
    indeterminate?: boolean
    glow?: boolean
}

export function CircularProgress({
    value,
    max = 100,
    size = 64,
    strokeWidth = 4,
    variant = 'default',
    showValue = true,
    label,
    formatValue,
    indeterminate = false,
    glow = false,
    className,
    ...props
}: CircularProgressProps) {
    const percentage = Math.min(100, Math.max(0, (value / max) * 100))
    const radius = (size - strokeWidth) / 2
    const circumference = radius * 2 * Math.PI
    const offset = circumference - (percentage / 100) * circumference

    const displayValue = formatValue
        ? formatValue(value, max)
        : `${Math.round(percentage)}%`

    const colorMap = {
        default: '#00d4ff',
        gradient: 'url(#gradient)',
        success: '#22c55e',
        warning: '#f59e0b',
        danger: '#ef4444',
    }

    return (
        <div className={cn('relative inline-flex flex-col items-center', className)} {...props}>
            <svg
                width={size}
                height={size}
                viewBox={`0 0 ${size} ${size}`}
                className={cn(
                    indeterminate && 'animate-spin',
                    glow && 'drop-shadow-[0_0_8px_rgba(0,212,255,0.5)]'
                )}
            >
                {variant === 'gradient' && (
                    <defs>
                        <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                            <stop offset="0%" stopColor="#00d4ff" />
                            <stop offset="100%" stopColor="#ff3296" />
                        </linearGradient>
                    </defs>
                )}

                {/* Background circle */}
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={strokeWidth}
                    className="text-slate-800/50"
                />

                {/* Progress circle */}
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke={colorMap[variant]}
                    strokeWidth={strokeWidth}
                    strokeLinecap="round"
                    strokeDasharray={circumference}
                    strokeDashoffset={indeterminate ? circumference * 0.75 : offset}
                    className="transition-all duration-300 ease-out origin-center -rotate-90"
                    style={{ transformOrigin: '50% 50%' }}
                />
            </svg>

            {showValue && !indeterminate && (
                <div className="absolute inset-0 flex items-center justify-center">
                    <span className={cn(
                        'font-medium text-gray-200',
                        size < 48 && 'text-xs',
                        size >= 48 && size < 80 && 'text-sm',
                        size >= 80 && 'text-base'
                    )}>
                        {displayValue}
                    </span>
                </div>
            )}

            {label && (
                <span className="mt-2 text-sm text-gray-400">{label}</span>
            )}
        </div>
    )
}

// ============================================================================
// Steps Progress Component
// ============================================================================

export interface Step {
    label: string
    description?: string
    icon?: React.ReactNode
}

export interface StepsProgressProps extends React.HTMLAttributes<HTMLDivElement> {
    steps: Step[]
    currentStep: number
    variant?: 'default' | 'dots' | 'compact'
    orientation?: 'horizontal' | 'vertical'
}

export function StepsProgress({
    steps,
    currentStep,
    variant = 'default',
    orientation = 'horizontal',
    className,
    ...props
}: StepsProgressProps) {
    return (
        <div
            className={cn(
                'w-full',
                orientation === 'vertical' && 'flex flex-col',
                className
            )}
            {...props}
        >
            <div
                className={cn(
                    'flex',
                    orientation === 'horizontal' ? 'items-center justify-between' : 'flex-col gap-0'
                )}
            >
                {steps.map((step, index) => {
                    const isCompleted = index < currentStep
                    const isCurrent = index === currentStep
                    const isLast = index === steps.length - 1

                    return (
                        <React.Fragment key={index}>
                            {/* Step */}
                            <div
                                className={cn(
                                    'flex items-center',
                                    orientation === 'vertical' && 'flex-1',
                                    orientation === 'vertical' && !isLast && 'pb-8'
                                )}
                            >
                                {/* Step indicator */}
                                <div className="relative">
                                    <div
                                        className={cn(
                                            'flex items-center justify-center rounded-full transition-all duration-300',
                                            variant === 'dots' ? 'w-3 h-3' : 'w-8 h-8',
                                            isCompleted && 'bg-primary-500 text-white',
                                            isCurrent && 'bg-primary-500/20 border-2 border-primary-500 text-primary-400',
                                            !isCompleted && !isCurrent && 'bg-dark-400 border border-white/10 text-gray-500'
                                        )}
                                    >
                                        {variant !== 'dots' && (
                                            isCompleted ? (
                                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                                </svg>
                                            ) : step.icon ? (
                                                step.icon
                                            ) : (
                                                <span className="text-sm font-medium">{index + 1}</span>
                                            )
                                        )}
                                    </div>

                                    {/* Vertical connector */}
                                    {orientation === 'vertical' && !isLast && (
                                        <div
                                            className={cn(
                                                'absolute left-1/2 -translate-x-1/2 w-0.5 h-8 top-full mt-0',
                                                isCompleted ? 'bg-primary-500' : 'bg-dark-300'
                                            )}
                                        />
                                    )}
                                </div>

                                {/* Step content (vertical only) */}
                                {orientation === 'vertical' && variant !== 'dots' && (
                                    <div className="ml-4">
                                        <div
                                            className={cn(
                                                'text-sm font-medium',
                                                isCompleted || isCurrent ? 'text-gray-200' : 'text-gray-500'
                                            )}
                                        >
                                            {step.label}
                                        </div>
                                        {step.description && (
                                            <div className="text-xs text-gray-500 mt-0.5">{step.description}</div>
                                        )}
                                    </div>
                                )}
                            </div>

                            {/* Horizontal connector */}
                            {orientation === 'horizontal' && !isLast && (
                                <div
                                    className={cn(
                                        'flex-1 h-0.5 mx-2',
                                        isCompleted ? 'bg-primary-500' : 'bg-dark-300'
                                    )}
                                />
                            )}
                        </React.Fragment>
                    )
                })}
            </div>

            {/* Horizontal labels */}
            {orientation === 'horizontal' && variant !== 'compact' && (
                <div className="flex justify-between mt-2">
                    {steps.map((step, index) => {
                        const isCompleted = index < currentStep
                        const isCurrent = index === currentStep

                        return (
                            <div key={index} className="text-center" style={{ width: `${100 / steps.length}%` }}>
                                <div
                                    className={cn(
                                        'text-xs font-medium',
                                        isCompleted || isCurrent ? 'text-gray-200' : 'text-gray-500'
                                    )}
                                >
                                    {step.label}
                                </div>
                                {step.description && (
                                    <div className="text-xs text-gray-500 mt-0.5">{step.description}</div>
                                )}
                            </div>
                        )
                    })}
                </div>
            )}
        </div>
    )
}

// ============================================================================
// Loading Spinner
// ============================================================================

export interface SpinnerProps {
    size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl'
    variant?: 'default' | 'dots' | 'pulse'
    className?: string
}

export function Spinner({ size = 'md', variant = 'default', className }: SpinnerProps) {
    const sizeMap = {
        xs: 'w-3 h-3',
        sm: 'w-4 h-4',
        md: 'w-6 h-6',
        lg: 'w-8 h-8',
        xl: 'w-12 h-12',
    }

    if (variant === 'dots') {
        return (
            <div className={cn('flex space-x-1', className)}>
                {[0, 1, 2].map((i) => (
                    <div
                        key={i}
                        className={cn(
                            'rounded-full bg-primary-500',
                            sizeMap[size].split(' ')[0].replace('w-', 'w-').replace(/\d+/, String(parseInt(sizeMap[size].split(' ')[0].match(/\d+/)?.[0] || '4') / 3)),
                            'animate-bounce'
                        )}
                        style={{
                            animationDelay: `${i * 0.1}s`,
                            width: size === 'xs' ? 4 : size === 'sm' ? 5 : size === 'md' ? 6 : size === 'lg' ? 8 : 10,
                            height: size === 'xs' ? 4 : size === 'sm' ? 5 : size === 'md' ? 6 : size === 'lg' ? 8 : 10,
                        }}
                    />
                ))}
            </div>
        )
    }

    if (variant === 'pulse') {
        return (
            <div className={cn(sizeMap[size], 'relative', className)}>
                <div className="absolute inset-0 rounded-full bg-primary-500/50 animate-ping" />
                <div className="relative rounded-full bg-primary-500" style={{ width: '100%', height: '100%' }} />
            </div>
        )
    }

    return (
        <svg
            className={cn(sizeMap[size], 'animate-spin text-primary-500', className)}
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
    )
}

// ============================================================================
// Skeleton Loader
// ============================================================================

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
    variant?: 'text' | 'circular' | 'rectangular'
    width?: string | number
    height?: string | number
    lines?: number
}

export function Skeleton({
    variant = 'text',
    width,
    height,
    lines = 1,
    className,
    ...props
}: SkeletonProps) {
    const baseClasses = 'animate-pulse bg-dark-400/50 rounded'

    if (variant === 'circular') {
        return (
            <div
                className={cn(baseClasses, 'rounded-full', className)}
                style={{
                    width: width ?? 40,
                    height: height ?? width ?? 40,
                }}
                {...props}
            />
        )
    }

    if (variant === 'rectangular') {
        return (
            <div
                className={cn(baseClasses, className)}
                style={{ width, height }}
                {...props}
            />
        )
    }

    // Text variant
    return (
        <div className={cn('space-y-2', className)} {...props}>
            {Array.from({ length: lines }).map((_, i) => (
                <div
                    key={i}
                    className={cn(baseClasses, 'h-4')}
                    style={{
                        width: i === lines - 1 && lines > 1 ? '75%' : width ?? '100%',
                    }}
                />
            ))}
        </div>
    )
}

export { progressVariants, progressBarVariants }
