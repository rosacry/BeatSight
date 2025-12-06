/**
 * Switch/Toggle Components
 * Modern toggle switches with animations and accessibility.
 */

import React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'

// ============================================================================
// Switch Variants
// ============================================================================

const switchVariants = cva(
    [
        'relative inline-flex shrink-0 cursor-pointer items-center rounded-full',
        'border-2 border-transparent transition-colors duration-200',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/50 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900',
        'disabled:cursor-not-allowed disabled:opacity-50',
    ],
    {
        variants: {
            size: {
                sm: 'h-5 w-9',
                md: 'h-6 w-11',
                lg: 'h-7 w-14',
            },
            variant: {
                default: [
                    'bg-slate-700',
                    'data-[state=checked]:bg-cyan-500',
                ],
                gradient: [
                    'bg-slate-700',
                    'data-[state=checked]:bg-gradient-to-r data-[state=checked]:from-cyan-500 data-[state=checked]:to-fuchsia-500',
                ],
                success: [
                    'bg-slate-700',
                    'data-[state=checked]:bg-green-500',
                ],
                danger: [
                    'bg-slate-700',
                    'data-[state=checked]:bg-red-500',
                ],
            },
        },
        defaultVariants: {
            size: 'md',
            variant: 'default',
        },
    }
)

const thumbVariants = cva(
    [
        'pointer-events-none block rounded-full bg-white shadow-lg',
        'ring-0 transition-transform duration-200 ease-out',
    ],
    {
        variants: {
            size: {
                sm: 'h-4 w-4 data-[state=checked]:translate-x-4',
                md: 'h-5 w-5 data-[state=checked]:translate-x-5',
                lg: 'h-6 w-6 data-[state=checked]:translate-x-7',
            },
        },
        defaultVariants: {
            size: 'md',
        },
    }
)

// ============================================================================
// Switch Component
// ============================================================================

export interface SwitchProps
    extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'onChange'>,
    VariantProps<typeof switchVariants> {
    checked?: boolean
    defaultChecked?: boolean
    onCheckedChange?: (checked: boolean) => void
    label?: string
    description?: string
    labelPosition?: 'left' | 'right'
}

export const Switch = React.forwardRef<HTMLButtonElement, SwitchProps>(
    (
        {
            className,
            size,
            variant,
            checked,
            defaultChecked = false,
            onCheckedChange,
            label,
            description,
            labelPosition = 'right',
            disabled,
            ...props
        },
        ref
    ) => {
        const [isChecked, setIsChecked] = React.useState(defaultChecked)

        const controlledChecked = checked !== undefined ? checked : isChecked

        const handleClick = () => {
            if (disabled) return

            const newChecked = !controlledChecked
            if (checked === undefined) {
                setIsChecked(newChecked)
            }
            onCheckedChange?.(newChecked)
        }

        const switchElement = (
            <button
                type="button"
                role="switch"
                ref={ref}
                aria-checked={controlledChecked}
                aria-label={label}
                data-state={controlledChecked ? 'checked' : 'unchecked'}
                disabled={disabled}
                onClick={handleClick}
                className={cn(switchVariants({ size, variant }), className)}
                {...props}
            >
                <span
                    data-state={controlledChecked ? 'checked' : 'unchecked'}
                    className={cn(thumbVariants({ size }))}
                />
            </button>
        )

        if (!label && !description) {
            return switchElement
        }

        return (
            <div className={cn('flex items-center gap-3', labelPosition === 'left' && 'flex-row-reverse')}>
                {switchElement}
                <div className="flex flex-col">
                    {label && (
                        <span
                            className={cn(
                                'text-sm font-medium text-slate-200',
                                disabled && 'opacity-50'
                            )}
                        >
                            {label}
                        </span>
                    )}
                    {description && (
                        <span
                            className={cn(
                                'text-xs text-slate-500',
                                disabled && 'opacity-50'
                            )}
                        >
                            {description}
                        </span>
                    )}
                </div>
            </div>
        )
    }
)
Switch.displayName = 'Switch'

// ============================================================================
// Toggle Button Group
// ============================================================================

export interface ToggleOption<T extends string = string> {
    value: T
    label: string
    icon?: React.ReactNode
    disabled?: boolean
}

export interface ToggleGroupProps<T extends string = string> {
    options: ToggleOption<T>[]
    value?: T
    defaultValue?: T
    onValueChange?: (value: T) => void
    size?: 'sm' | 'md' | 'lg'
    variant?: 'default' | 'outline' | 'pills'
    className?: string
    disabled?: boolean
}

export function ToggleGroup<T extends string = string>({
    options,
    value,
    defaultValue,
    onValueChange,
    size = 'md',
    variant = 'default',
    className,
    disabled,
}: ToggleGroupProps<T>) {
    const [selected, setSelected] = React.useState<T | undefined>(defaultValue)
    const controlledValue = value !== undefined ? value : selected

    const handleSelect = (optionValue: T) => {
        if (disabled) return

        if (value === undefined) {
            setSelected(optionValue)
        }
        onValueChange?.(optionValue)
    }

    const sizeClasses = {
        sm: 'px-2.5 py-1 text-xs',
        md: 'px-3 py-1.5 text-sm',
        lg: 'px-4 py-2 text-base',
    }

    const variantClasses = {
        default: 'bg-slate-800/50 rounded-lg p-1',
        outline: 'border border-slate-700 rounded-lg p-1',
        pills: 'gap-2',
    }

    const itemVariantClasses = {
        default: cn(
            'rounded-md transition-all duration-200',
            'text-slate-400 hover:text-slate-200',
            'data-[state=on]:bg-slate-700 data-[state=on]:text-cyan-400'
        ),
        outline: cn(
            'rounded-md transition-all duration-200',
            'text-slate-400 hover:text-slate-200',
            'data-[state=on]:bg-cyan-500/10 data-[state=on]:text-cyan-400'
        ),
        pills: cn(
            'rounded-full transition-all duration-200 border',
            'border-slate-700 text-slate-400 hover:text-slate-200 hover:border-slate-600',
            'data-[state=on]:border-cyan-500/50 data-[state=on]:bg-cyan-500/10 data-[state=on]:text-cyan-400'
        ),
    }

    return (
        <div
            role="group"
            className={cn('inline-flex items-center', variantClasses[variant], className)}
        >
            {options.map((option) => {
                const isSelected = controlledValue === option.value
                const isDisabled = disabled || option.disabled

                return (
                    <button
                        key={option.value}
                        type="button"
                        role="radio"
                        aria-checked={isSelected}
                        data-state={isSelected ? 'on' : 'off'}
                        disabled={isDisabled}
                        onClick={() => handleSelect(option.value)}
                        className={cn(
                            'inline-flex items-center justify-center gap-2 font-medium',
                            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/50',
                            'disabled:pointer-events-none disabled:opacity-50',
                            sizeClasses[size],
                            itemVariantClasses[variant]
                        )}
                    >
                        {option.icon && <span className="flex-shrink-0">{option.icon}</span>}
                        {option.label}
                    </button>
                )
            })}
        </div>
    )
}

// ============================================================================
// Checkbox Component
// ============================================================================

export interface CheckboxProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'onChange' | 'size'> {
    label?: string
    description?: string
    size?: 'sm' | 'md' | 'lg'
    onCheckedChange?: (checked: boolean) => void
}

export const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
    ({ className, label, description, size = 'md', onCheckedChange, checked, disabled, ...props }, ref) => {
        const sizeClasses = {
            sm: 'h-4 w-4',
            md: 'h-5 w-5',
            lg: 'h-6 w-6',
        }

        const iconSizes = {
            sm: 'h-3 w-3',
            md: 'h-3.5 w-3.5',
            lg: 'h-4 w-4',
        }

        return (
            <label
                className={cn(
                    'inline-flex items-start gap-3 cursor-pointer',
                    disabled && 'cursor-not-allowed opacity-50',
                    className
                )}
            >
                <div className="relative flex items-center justify-center">
                    <input
                        type="checkbox"
                        ref={ref}
                        checked={checked}
                        disabled={disabled}
                        onChange={(e) => onCheckedChange?.(e.target.checked)}
                        className="peer sr-only"
                        {...props}
                    />
                    <div
                        className={cn(
                            sizeClasses[size],
                            'rounded border-2 border-slate-600 bg-slate-800/50',
                            'transition-all duration-200',
                            'peer-focus-visible:ring-2 peer-focus-visible:ring-cyan-500/50 peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-slate-900',
                            'peer-checked:border-cyan-500 peer-checked:bg-cyan-500'
                        )}
                    />
                    <svg
                        className={cn(
                            iconSizes[size],
                            'absolute text-white opacity-0 transition-opacity duration-200',
                            'peer-checked:opacity-100'
                        )}
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={3}
                    >
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                </div>
                {(label || description) && (
                    <div className="flex flex-col">
                        {label && <span className="text-sm font-medium text-slate-200">{label}</span>}
                        {description && <span className="text-xs text-slate-500">{description}</span>}
                    </div>
                )}
            </label>
        )
    }
)
Checkbox.displayName = 'Checkbox'

// ============================================================================
// Radio Group
// ============================================================================

export interface RadioOption<T extends string = string> {
    value: T
    label: string
    description?: string
    disabled?: boolean
}

export interface RadioGroupProps<T extends string = string> {
    options: RadioOption<T>[]
    value?: T
    defaultValue?: T
    onValueChange?: (value: T) => void
    name: string
    size?: 'sm' | 'md' | 'lg'
    orientation?: 'horizontal' | 'vertical'
    className?: string
    disabled?: boolean
}

export function RadioGroup<T extends string = string>({
    options,
    value,
    defaultValue,
    onValueChange,
    name,
    size = 'md',
    orientation = 'vertical',
    className,
    disabled,
}: RadioGroupProps<T>) {
    const [selected, setSelected] = React.useState<T | undefined>(defaultValue)
    const controlledValue = value !== undefined ? value : selected

    const handleSelect = (optionValue: T) => {
        if (disabled) return

        if (value === undefined) {
            setSelected(optionValue)
        }
        onValueChange?.(optionValue)
    }

    const sizeClasses = {
        sm: 'h-4 w-4',
        md: 'h-5 w-5',
        lg: 'h-6 w-6',
    }

    const dotSizes = {
        sm: 'h-2 w-2',
        md: 'h-2.5 w-2.5',
        lg: 'h-3 w-3',
    }

    return (
        <div
            role="radiogroup"
            className={cn(
                'flex',
                orientation === 'vertical' ? 'flex-col gap-3' : 'flex-row flex-wrap gap-4',
                className
            )}
        >
            {options.map((option) => {
                const isSelected = controlledValue === option.value
                const isDisabled = disabled || option.disabled

                return (
                    <label
                        key={option.value}
                        className={cn(
                            'inline-flex items-start gap-3 cursor-pointer',
                            isDisabled && 'cursor-not-allowed opacity-50'
                        )}
                    >
                        <div className="relative flex items-center justify-center">
                            <input
                                type="radio"
                                name={name}
                                value={option.value}
                                checked={isSelected}
                                disabled={isDisabled}
                                onChange={() => handleSelect(option.value)}
                                className="peer sr-only"
                            />
                            <div
                                className={cn(
                                    sizeClasses[size],
                                    'rounded-full border-2 border-slate-600 bg-slate-800/50',
                                    'transition-all duration-200',
                                    'peer-focus-visible:ring-2 peer-focus-visible:ring-cyan-500/50 peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-slate-900',
                                    'peer-checked:border-cyan-500'
                                )}
                            />
                            <div
                                className={cn(
                                    dotSizes[size],
                                    'absolute rounded-full bg-cyan-500',
                                    'scale-0 transition-transform duration-200',
                                    'peer-checked:scale-100'
                                )}
                            />
                        </div>
                        {(option.label || option.description) && (
                            <div className="flex flex-col">
                                {option.label && (
                                    <span className="text-sm font-medium text-slate-200">{option.label}</span>
                                )}
                                {option.description && (
                                    <span className="text-xs text-slate-500">{option.description}</span>
                                )}
                            </div>
                        )}
                    </label>
                )
            })}
        </div>
    )
}

export { switchVariants, thumbVariants }
