/**
 * Modern Button component with variants, animations, and glow effects.
 * Inspired by premium UI design patterns.
 */

import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { clsx } from 'clsx'

const buttonVariants = cva(
    // Base styles
    [
        'relative inline-flex items-center justify-center gap-2',
        'font-semibold transition-all duration-200',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-dark-500',
        'disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none',
        'active:scale-[0.98]',
    ],
    {
        variants: {
            variant: {
                primary: [
                    'bg-primary-500 hover:bg-primary-600',
                    'text-white',
                    'focus-visible:ring-primary-500',
                ],
                secondary: [
                    'bg-dark-400 hover:bg-dark-300',
                    'text-gray-100 border border-dark-300',
                    'hover:border-dark-200',
                    'focus-visible:ring-gray-500',
                ],
                accent: [
                    'bg-accent-500 hover:bg-accent-600',
                    'text-white',
                    'focus-visible:ring-accent-500',
                ],
                ghost: [
                    'bg-transparent hover:bg-dark-400',
                    'text-gray-300 hover:text-white',
                    'focus-visible:ring-gray-500',
                ],
                outline: [
                    'bg-transparent border-2 border-primary-500/50',
                    'hover:bg-primary-500/10 hover:border-primary-500',
                    'text-primary-400 hover:text-primary-300',
                    'focus-visible:ring-primary-500',
                ],
                danger: [
                    'bg-red-600 hover:bg-red-500',
                    'text-white',
                    'focus-visible:ring-red-500',
                ],
                success: [
                    'bg-green-600 hover:bg-green-500',
                    'text-white',
                    'focus-visible:ring-green-500',
                ],
                glow: [
                    'bg-primary-500 hover:bg-primary-400',
                    'text-white',
                    'shadow-[0_0_15px_rgba(255,102,171,0.3)]',
                    'hover:shadow-[0_0_20px_rgba(255,102,171,0.4)]',
                    'focus-visible:ring-primary-500',
                ],
            },
            size: {
                xs: 'text-xs px-2.5 py-1.5 rounded',
                sm: 'text-sm px-3 py-2 rounded-md',
                md: 'text-sm px-4 py-2.5 rounded-lg',
                lg: 'text-base px-6 py-3 rounded-lg',
                xl: 'text-lg px-8 py-4 rounded-xl',
            },
            fullWidth: {
                true: 'w-full',
                false: '',
            },
        },
        defaultVariants: {
            variant: 'primary',
            size: 'md',
            fullWidth: false,
        },
    }
)

export interface ButtonProps
    extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
    /** Optional icon to show before text */
    leftIcon?: ReactNode
    /** Optional icon to show after text */
    rightIcon?: ReactNode
    /** Show loading spinner */
    loading?: boolean
    /** Animate on hover with pulse effect */
    pulse?: boolean
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
    (
        {
            className,
            variant,
            size,
            fullWidth,
            leftIcon,
            rightIcon,
            loading,
            pulse,
            disabled,
            children,
            ...props
        },
        ref
    ) => {
        return (
            <button
                ref={ref}
                disabled={disabled || loading}
                className={clsx(
                    buttonVariants({ variant, size, fullWidth }),
                    pulse && 'animate-pulse-slow',
                    className
                )}
                {...props}
            >
                {/* Loading spinner */}
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

                {/* Left icon */}
                {!loading && leftIcon && <span className="shrink-0">{leftIcon}</span>}

                {/* Button text */}
                {children}

                {/* Right icon */}
                {rightIcon && <span className="shrink-0">{rightIcon}</span>}
            </button>
        )
    }
)

Button.displayName = 'Button'

/**
 * Icon-only button variant
 */
export interface IconButtonProps
    extends ButtonHTMLAttributes<HTMLButtonElement>,
    Omit<VariantProps<typeof buttonVariants>, 'fullWidth'> {
    /** Icon to display */
    icon: ReactNode
    /** Accessible label */
    'aria-label': string
    /** Show loading spinner */
    loading?: boolean
}

const iconButtonSizes = {
    xs: 'h-6 w-6',
    sm: 'h-8 w-8',
    md: 'h-10 w-10',
    lg: 'h-12 w-12',
    xl: 'h-14 w-14',
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
    ({ className, variant, size = 'md', icon, loading, disabled, ...props }, ref) => {
        return (
            <button
                ref={ref}
                disabled={disabled || loading}
                className={clsx(
                    buttonVariants({ variant, size: null }),
                    iconButtonSizes[size ?? 'md'],
                    'p-0 rounded-lg',
                    className
                )}
                {...props}
            >
                {loading ? (
                    <svg
                        className="animate-spin h-5 w-5"
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
                ) : (
                    icon
                )}
            </button>
        )
    }
)

IconButton.displayName = 'IconButton'

export { buttonVariants }
