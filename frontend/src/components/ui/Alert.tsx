/**
 * Alert/Notification Components
 * Modern alerts and notifications with animations.
 */

import React, { useState, useEffect } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'

// ============================================================================
// Alert Variants
// ============================================================================

const alertVariants = cva(
    [
        'relative w-full rounded-lg border p-4',
        'flex items-start gap-3',
        '[&>svg]:shrink-0 [&>svg]:mt-0.5',
    ],
    {
        variants: {
            variant: {
                default: [
                    'bg-slate-800/50 border-slate-700 text-slate-200',
                    '[&>svg]:text-slate-400',
                ],
                info: [
                    'bg-blue-500/10 border-blue-500/30 text-blue-200',
                    '[&>svg]:text-blue-400',
                ],
                success: [
                    'bg-green-500/10 border-green-500/30 text-green-200',
                    '[&>svg]:text-green-400',
                ],
                warning: [
                    'bg-amber-500/10 border-amber-500/30 text-amber-200',
                    '[&>svg]:text-amber-400',
                ],
                error: [
                    'bg-red-500/10 border-red-500/30 text-red-200',
                    '[&>svg]:text-red-400',
                ],
            },
        },
        defaultVariants: {
            variant: 'default',
        },
    }
)

// ============================================================================
// Icons
// ============================================================================

const AlertIcons = {
    info: (
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
        </svg>
    ),
    success: (
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
            />
        </svg>
    ),
    warning: (
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
        </svg>
    ),
    error: (
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"
            />
        </svg>
    ),
    default: (
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
        </svg>
    ),
}

// ============================================================================
// Alert Component
// ============================================================================

export interface AlertProps
    extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof alertVariants> {
    title?: string
    icon?: React.ReactNode
    onClose?: () => void
    closable?: boolean
}

export function Alert({
    className,
    variant = 'default',
    title,
    icon,
    onClose,
    closable = false,
    children,
    ...props
}: AlertProps) {
    const defaultIcon = icon ?? AlertIcons[variant ?? 'default']

    return (
        <div
            role="alert"
            className={cn(alertVariants({ variant }), className)}
            {...props}
        >
            {defaultIcon}
            <div className="flex-1 min-w-0">
                {title && (
                    <h5 className="mb-1 font-medium leading-none tracking-tight">{title}</h5>
                )}
                <div className="text-sm opacity-90">{children}</div>
            </div>
            {closable && onClose && (
                <button
                    onClick={onClose}
                    className={cn(
                        'absolute right-2 top-2 rounded-md p-1',
                        'opacity-70 hover:opacity-100 transition-opacity',
                        'focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-slate-900'
                    )}
                    aria-label="Close alert"
                >
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M6 18L18 6M6 6l12 12"
                        />
                    </svg>
                </button>
            )}
        </div>
    )
}

// ============================================================================
// Toast Notification
// ============================================================================

export interface ToastProps {
    id: string
    title?: string
    description?: string
    variant?: 'default' | 'info' | 'success' | 'warning' | 'error'
    duration?: number
    onClose?: () => void
}

export function Toast({
    title,
    description,
    variant = 'default',
    duration = 5000,
    onClose,
}: ToastProps) {
    const [isVisible, setIsVisible] = useState(true)
    const [isExiting, setIsExiting] = useState(false)

    const handleClose = useCallback(() => {
        setIsExiting(true)
        setTimeout(() => {
            setIsVisible(false)
            onClose?.()
        }, 200)
    }, [onClose])

    useEffect(() => {
        if (duration > 0) {
            const timer = setTimeout(() => {
                handleClose()
            }, duration)
            return () => clearTimeout(timer)
        }
    }, [duration, handleClose])

    if (!isVisible) return null

    const variantColors = {
        default: 'border-slate-700 bg-slate-800',
        info: 'border-blue-500/30 bg-blue-500/10',
        success: 'border-green-500/30 bg-green-500/10',
        warning: 'border-amber-500/30 bg-amber-500/10',
        error: 'border-red-500/30 bg-red-500/10',
    }

    const iconColors = {
        default: 'text-slate-400',
        info: 'text-blue-400',
        success: 'text-green-400',
        warning: 'text-amber-400',
        error: 'text-red-400',
    }

    return (
        <div
            className={cn(
                'pointer-events-auto w-full max-w-sm overflow-hidden rounded-lg border shadow-lg',
                variantColors[variant],
                isExiting ? 'animate-slide-out-right' : 'animate-slide-in-right'
            )}
            role="alert"
        >
            <div className="p-4">
                <div className="flex items-start gap-3">
                    <span className={cn('shrink-0', iconColors[variant])}>
                        {AlertIcons[variant]}
                    </span>
                    <div className="flex-1 min-w-0">
                        {title && (
                            <p className="text-sm font-medium text-slate-100">{title}</p>
                        )}
                        {description && (
                            <p className="mt-1 text-sm text-slate-400">{description}</p>
                        )}
                    </div>
                    <button
                        onClick={handleClose}
                        className={cn(
                            'shrink-0 rounded-md p-1',
                            'text-slate-500 hover:text-slate-300 transition-colors',
                            'focus:outline-none focus:ring-2 focus:ring-cyan-500/50'
                        )}
                    >
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M6 18L18 6M6 6l12 12"
                            />
                        </svg>
                    </button>
                </div>
            </div>
            {duration > 0 && (
                <div className="h-1 bg-slate-700/50">
                    <div
                        className={cn(
                            'h-full bg-gradient-to-r from-cyan-500 to-fuchsia-500',
                            'animate-shrink-width'
                        )}
                        style={{
                            animationDuration: `${duration}ms`,
                        }}
                    />
                </div>
            )}
        </div>
    )
}

// ============================================================================
// Toast Container
// ============================================================================

export interface ToastContainerProps {
    position?: 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left' | 'top-center' | 'bottom-center'
    children: React.ReactNode
}

export function ToastContainer({ position = 'top-right', children }: ToastContainerProps) {
    const positionClasses = {
        'top-right': 'top-0 right-0',
        'top-left': 'top-0 left-0',
        'bottom-right': 'bottom-0 right-0',
        'bottom-left': 'bottom-0 left-0',
        'top-center': 'top-0 left-1/2 -translate-x-1/2',
        'bottom-center': 'bottom-0 left-1/2 -translate-x-1/2',
    }

    return (
        <div
            className={cn(
                'fixed z-50 flex flex-col gap-2 p-4 pointer-events-none',
                'max-h-screen overflow-hidden',
                positionClasses[position]
            )}
        >
            {children}
        </div>
    )
}

// ============================================================================
// Banner Alert
// ============================================================================

export interface BannerProps extends React.HTMLAttributes<HTMLDivElement> {
    variant?: 'info' | 'success' | 'warning' | 'error'
    icon?: React.ReactNode
    action?: {
        label: string
        onClick: () => void
    }
    onClose?: () => void
}

export function Banner({
    variant = 'info',
    icon,
    action,
    onClose,
    children,
    className,
    ...props
}: BannerProps) {
    const variantColors = {
        info: 'bg-blue-500/20 border-blue-500/30 text-blue-100',
        success: 'bg-green-500/20 border-green-500/30 text-green-100',
        warning: 'bg-amber-500/20 border-amber-500/30 text-amber-100',
        error: 'bg-red-500/20 border-red-500/30 text-red-100',
    }

    const buttonColors = {
        info: 'bg-blue-500 hover:bg-blue-600 text-white',
        success: 'bg-green-500 hover:bg-green-600 text-white',
        warning: 'bg-amber-500 hover:bg-amber-600 text-white',
        error: 'bg-red-500 hover:bg-red-600 text-white',
    }

    return (
        <div
            className={cn(
                'relative w-full border-b py-3 px-4',
                variantColors[variant],
                className
            )}
            role="alert"
            {...props}
        >
            <div className="container mx-auto flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                    {icon ?? (
                        <span className="opacity-80">
                            {AlertIcons[variant]}
                        </span>
                    )}
                    <span className="text-sm">{children}</span>
                </div>
                <div className="flex items-center gap-2">
                    {action && (
                        <button
                            onClick={action.onClick}
                            className={cn(
                                'rounded-md px-3 py-1 text-sm font-medium transition-colors',
                                buttonColors[variant]
                            )}
                        >
                            {action.label}
                        </button>
                    )}
                    {onClose && (
                        <button
                            onClick={onClose}
                            className="rounded-md p-1 opacity-70 hover:opacity-100 transition-opacity"
                            aria-label="Close banner"
                        >
                            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M6 18L18 6M6 6l12 12"
                                />
                            </svg>
                        </button>
                    )}
                </div>
            </div>
        </div>
    )
}

// ============================================================================
// Callout Component
// ============================================================================

export interface CalloutProps extends React.HTMLAttributes<HTMLDivElement> {
    variant?: 'default' | 'info' | 'success' | 'warning' | 'error'
    icon?: React.ReactNode
    title?: string
}

export function Callout({
    variant = 'default',
    icon,
    title,
    children,
    className,
    ...props
}: CalloutProps) {
    const variantStyles = {
        default: 'border-l-slate-500 bg-slate-800/30',
        info: 'border-l-blue-500 bg-blue-500/5',
        success: 'border-l-green-500 bg-green-500/5',
        warning: 'border-l-amber-500 bg-amber-500/5',
        error: 'border-l-red-500 bg-red-500/5',
    }

    const iconColors = {
        default: 'text-slate-400',
        info: 'text-blue-400',
        success: 'text-green-400',
        warning: 'text-amber-400',
        error: 'text-red-400',
    }

    return (
        <div
            className={cn(
                'rounded-r-lg border-l-4 p-4',
                variantStyles[variant],
                className
            )}
            {...props}
        >
            <div className="flex gap-3">
                {(icon || variant !== 'default') && (
                    <span className={cn('shrink-0 mt-0.5', iconColors[variant])}>
                        {icon ?? AlertIcons[variant]}
                    </span>
                )}
                <div className="flex-1">
                    {title && (
                        <h4 className="mb-1 font-medium text-slate-100">{title}</h4>
                    )}
                    <div className="text-sm text-slate-300">{children}</div>
                </div>
            </div>
        </div>
    )
}

export { alertVariants }
