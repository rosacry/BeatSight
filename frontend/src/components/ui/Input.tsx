/**
 * Modern Input components with variants, states, and accessibility.
 */

import { forwardRef, type InputHTMLAttributes, type TextareaHTMLAttributes, type ReactNode, useState } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { clsx } from 'clsx'

const inputVariants = cva(
    // Base styles
    [
        'w-full bg-gray-800 text-white placeholder-gray-500',
        'border rounded-lg transition-all duration-200',
        'focus:outline-none focus:ring-2 focus:ring-offset-0',
        'disabled:opacity-50 disabled:cursor-not-allowed',
    ],
    {
        variants: {
            variant: {
                default: [
                    'border-gray-700',
                    'hover:border-gray-600',
                    'focus:border-primary-500 focus:ring-primary-500/20',
                ],
                filled: [
                    'bg-gray-700 border-transparent',
                    'hover:bg-gray-600',
                    'focus:bg-gray-700 focus:border-primary-500 focus:ring-primary-500/20',
                ],
                outline: [
                    'bg-transparent border-gray-600',
                    'hover:border-gray-500',
                    'focus:border-primary-500 focus:ring-primary-500/20',
                ],
                ghost: [
                    'bg-transparent border-transparent',
                    'hover:bg-gray-800',
                    'focus:bg-gray-800 focus:border-gray-700',
                ],
            },
            inputSize: {
                sm: 'text-sm px-3 py-2',
                md: 'text-sm px-4 py-2.5',
                lg: 'text-base px-4 py-3',
            },
            state: {
                default: '',
                error: 'border-red-500 focus:border-red-500 focus:ring-red-500/20',
                success: 'border-green-500 focus:border-green-500 focus:ring-green-500/20',
            },
        },
        defaultVariants: {
            variant: 'default',
            inputSize: 'md',
            state: 'default',
        },
    }
)

export interface InputProps
    extends Omit<InputHTMLAttributes<HTMLInputElement>, 'size'>,
    VariantProps<typeof inputVariants> {
    /** Label text */
    label?: string
    /** Helper/error text below input */
    helperText?: string
    /** Left icon or element */
    leftElement?: ReactNode
    /** Right icon or element */
    rightElement?: ReactNode
    /** Full width */
    fullWidth?: boolean
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
    (
        {
            className,
            variant,
            inputSize,
            state,
            label,
            helperText,
            leftElement,
            rightElement,
            fullWidth = true,
            id,
            ...props
        },
        ref
    ) => {
        const inputId = id || `input-${Math.random().toString(36).slice(2, 9)}`

        return (
            <div className={clsx('space-y-1.5', fullWidth && 'w-full')}>
                {label && (
                    <label
                        htmlFor={inputId}
                        className="block text-sm font-medium text-gray-300"
                    >
                        {label}
                    </label>
                )}

                <div className="relative">
                    {leftElement && (
                        <div className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
                            {leftElement}
                        </div>
                    )}

                    <input
                        ref={ref}
                        id={inputId}
                        className={clsx(
                            inputVariants({ variant, inputSize, state }),
                            leftElement && 'pl-10',
                            rightElement && 'pr-10',
                            className
                        )}
                        {...props}
                    />

                    {rightElement && (
                        <div className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400">
                            {rightElement}
                        </div>
                    )}
                </div>

                {helperText && (
                    <p
                        className={clsx(
                            'text-xs',
                            state === 'error' && 'text-red-400',
                            state === 'success' && 'text-green-400',
                            state === 'default' && 'text-gray-500'
                        )}
                    >
                        {helperText}
                    </p>
                )}
            </div>
        )
    }
)

Input.displayName = 'Input'

/**
 * Textarea component with same styling as Input
 */
export interface TextareaProps
    extends Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, 'size'>,
    VariantProps<typeof inputVariants> {
    label?: string
    helperText?: string
    fullWidth?: boolean
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
    (
        {
            className,
            variant,
            inputSize,
            state,
            label,
            helperText,
            fullWidth = true,
            id,
            rows = 4,
            ...props
        },
        ref
    ) => {
        const textareaId = id || `textarea-${Math.random().toString(36).slice(2, 9)}`

        return (
            <div className={clsx('space-y-1.5', fullWidth && 'w-full')}>
                {label && (
                    <label
                        htmlFor={textareaId}
                        className="block text-sm font-medium text-gray-300"
                    >
                        {label}
                    </label>
                )}

                <textarea
                    ref={ref}
                    id={textareaId}
                    rows={rows}
                    className={clsx(
                        inputVariants({ variant, inputSize, state }),
                        'resize-y min-h-[80px]',
                        className
                    )}
                    {...props}
                />

                {helperText && (
                    <p
                        className={clsx(
                            'text-xs',
                            state === 'error' && 'text-red-400',
                            state === 'success' && 'text-green-400',
                            state === 'default' && 'text-gray-500'
                        )}
                    >
                        {helperText}
                    </p>
                )}
            </div>
        )
    }
)

Textarea.displayName = 'Textarea'

/**
 * Search Input with icon and clear button
 */
interface SearchInputProps extends Omit<InputProps, 'leftElement' | 'rightElement'> {
    onClear?: () => void
}

export const SearchInput = forwardRef<HTMLInputElement, SearchInputProps>(
    ({ value, onClear, onChange, ...props }, ref) => {
        const hasValue = typeof value === 'string' && value.length > 0

        return (
            <Input
                ref={ref}
                type="search"
                value={value}
                onChange={onChange}
                leftElement={
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                        />
                    </svg>
                }
                rightElement={
                    hasValue && onClear ? (
                        <button
                            type="button"
                            onClick={onClear}
                            className="p-1 hover:bg-gray-700 rounded transition-colors"
                        >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M6 18L18 6M6 6l12 12"
                                />
                            </svg>
                        </button>
                    ) : undefined
                }
                {...props}
            />
        )
    }
)

SearchInput.displayName = 'SearchInput'

/**
 * Password Input with visibility toggle
 */
export const PasswordInput = forwardRef<HTMLInputElement, Omit<InputProps, 'type' | 'rightElement'>>(
    (props, ref) => {
        const [showPassword, setShowPassword] = useState(false)

        return (
            <Input
                ref={ref}
                type={showPassword ? 'text' : 'password'}
                rightElement={
                    <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="p-1 hover:bg-gray-700 rounded transition-colors"
                        aria-label={showPassword ? 'Hide password' : 'Show password'}
                    >
                        {showPassword ? (
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"
                                />
                            </svg>
                        ) : (
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                                />
                                <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                                />
                            </svg>
                        )}
                    </button>
                }
                {...props}
            />
        )
    }
)

PasswordInput.displayName = 'PasswordInput'

export { inputVariants }
