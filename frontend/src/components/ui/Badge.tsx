/**
 * Badge component with variants for status indicators, labels, and tags.
 */

import { forwardRef, type HTMLAttributes, type ReactNode } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { clsx } from 'clsx'

const badgeVariants = cva(
    // Base styles
    [
        'inline-flex items-center gap-1.5 font-medium',
        'transition-all duration-200',
    ],
    {
        variants: {
            variant: {
                default: 'bg-dark-300 text-gray-200',
                primary: 'bg-primary-500/20 text-primary-400 border border-primary-500/30',
                secondary: 'bg-gray-600/50 text-gray-300 border border-gray-500/30',
                accent: 'bg-accent-500/20 text-accent-400 border border-accent-500/30',
                success: 'bg-green-500/20 text-green-400 border border-green-500/30',
                warning: 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30',
                error: 'bg-red-500/20 text-red-400 border border-red-500/30',
                info: 'bg-blue-500/20 text-blue-400 border border-blue-500/30',
                outline: 'bg-transparent border border-gray-600 text-gray-300',
                glow: [
                    'bg-primary-500/10 text-primary-300 border border-primary-500/50',
                    'shadow-[0_0_10px_rgba(14,165,233,0.3)]',
                ],
            },
            size: {
                xs: 'text-[10px] px-1.5 py-0.5 rounded',
                sm: 'text-xs px-2 py-0.5 rounded-md',
                md: 'text-sm px-2.5 py-1 rounded-md',
                lg: 'text-base px-3 py-1.5 rounded-lg',
            },
            dot: {
                true: '',
                false: '',
            },
            pulse: {
                true: '',
                false: '',
            },
        },
        defaultVariants: {
            variant: 'default',
            size: 'sm',
            dot: false,
            pulse: false,
        },
    }
)

export interface BadgeProps
    extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {
    /** Optional icon to show before text */
    icon?: ReactNode
    /** Show remove button */
    onRemove?: () => void
}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
    ({ className, variant, size, dot, pulse, icon, onRemove, children, ...props }, ref) => {
        // Get dot color based on variant
        const getDotColor = () => {
            switch (variant) {
                case 'primary':
                    return 'bg-primary-400'
                case 'accent':
                    return 'bg-accent-400'
                case 'success':
                    return 'bg-green-400'
                case 'warning':
                    return 'bg-yellow-400'
                case 'error':
                    return 'bg-red-400'
                case 'info':
                    return 'bg-blue-400'
                default:
                    return 'bg-gray-400'
            }
        }

        return (
            <span
                ref={ref}
                className={clsx(badgeVariants({ variant, size, dot, pulse }), className)}
                {...props}
            >
                {/* Animated dot */}
                {dot && (
                    <span className="relative flex h-2 w-2">
                        {pulse && (
                            <span
                                className={clsx(
                                    'animate-ping absolute inline-flex h-full w-full rounded-full opacity-75',
                                    getDotColor()
                                )}
                            />
                        )}
                        <span
                            className={clsx(
                                'relative inline-flex rounded-full h-2 w-2',
                                getDotColor()
                            )}
                        />
                    </span>
                )}

                {/* Icon */}
                {icon && <span className="shrink-0 [&>svg]:w-3.5 [&>svg]:h-3.5">{icon}</span>}

                {/* Content */}
                {children}

                {/* Remove button */}
                {onRemove && (
                    <button
                        type="button"
                        onClick={(e) => {
                            e.stopPropagation()
                            onRemove()
                        }}
                        className="ml-0.5 -mr-0.5 hover:bg-white/10 rounded p-0.5 transition-colors"
                        aria-label="Remove"
                    >
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M6 18L18 6M6 6l12 12"
                            />
                        </svg>
                    </button>
                )}
            </span>
        )
    }
)

Badge.displayName = 'Badge'

/**
 * Status Badge - Specialized for showing status indicators
 */
export type StatusType = 'online' | 'offline' | 'away' | 'busy' | 'pending' | 'processing'

interface StatusBadgeProps extends Omit<BadgeProps, 'variant' | 'dot' | 'pulse'> {
    status: StatusType
}

const statusConfig: Record<StatusType, { variant: BadgeProps['variant']; label: string; pulse?: boolean }> = {
    online: { variant: 'success', label: 'Online', pulse: true },
    offline: { variant: 'secondary', label: 'Offline' },
    away: { variant: 'warning', label: 'Away' },
    busy: { variant: 'error', label: 'Busy' },
    pending: { variant: 'info', label: 'Pending' },
    processing: { variant: 'primary', label: 'Processing', pulse: true },
}

export const StatusBadge = forwardRef<HTMLSpanElement, StatusBadgeProps>(
    ({ status, children, ...props }, ref) => {
        const config = statusConfig[status]

        return (
            <Badge
                ref={ref}
                variant={config.variant}
                dot
                pulse={config.pulse}
                {...props}
            >
                {children || config.label}
            </Badge>
        )
    }
)

StatusBadge.displayName = 'StatusBadge'

/**
 * Count Badge - For notifications and counts
 */
interface CountBadgeProps extends Omit<BadgeProps, 'children'> {
    count: number
    max?: number
}

export const CountBadge = forwardRef<HTMLSpanElement, CountBadgeProps>(
    ({ count, max = 99, ...props }, ref) => {
        const displayCount = count > max ? `${max}+` : count.toString()

        return (
            <Badge
                ref={ref}
                size="xs"
                className="min-w-[1.25rem] justify-center"
                {...props}
            >
                {displayCount}
            </Badge>
        )
    }
)

CountBadge.displayName = 'CountBadge'

export { badgeVariants }
