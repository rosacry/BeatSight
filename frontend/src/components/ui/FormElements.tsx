/**
 * Advanced form components with validation, error states, and accessibility.
 * Includes FormField, FormGroup, FormSection, and validation utilities.
 */

import {
    forwardRef,
    createContext,
    useContext,
    useState,
    useCallback,
    useId,
    useRef,
    useEffect,
    type HTMLAttributes,
    type ReactNode,
    type FormEvent,
} from 'react'
import { motion, AnimatePresence } from 'framer-motion'
// CVA used for future variants
import { cn } from '../../lib/utils'

// ============================================================================
// FORM CONTEXT
// ============================================================================

interface FormContextValue {
    isSubmitting: boolean
    errors: Record<string, string>
    touched: Record<string, boolean>
    setFieldError: (field: string, error: string | null) => void
    setFieldTouched: (field: string, touched: boolean) => void
    getFieldError: (field: string) => string | undefined
    isFieldTouched: (field: string) => boolean
}

const FormContext = createContext<FormContextValue | null>(null)

export function useFormContext() {
    const context = useContext(FormContext)
    if (!context) {
        throw new Error('useFormContext must be used within a Form component')
    }
    return context
}

// ============================================================================
// FORM
// ============================================================================

export interface FormProps extends Omit<HTMLAttributes<HTMLFormElement>, 'onSubmit'> {
    /** Form submit handler */
    onSubmit?: (values: FormData) => void | Promise<void>
    /** Initial errors */
    initialErrors?: Record<string, string>
    /** Disable form */
    disabled?: boolean
    children: ReactNode
}

export const Form = forwardRef<HTMLFormElement, FormProps>(
    ({ className, onSubmit, initialErrors = {}, disabled, children, ...props }, ref) => {
        const [isSubmitting, setIsSubmitting] = useState(false)
        const [errors, setErrors] = useState<Record<string, string>>(initialErrors)
        const [touched, setTouched] = useState<Record<string, boolean>>({})

        const setFieldError = useCallback((field: string, error: string | null) => {
            setErrors(prev => {
                if (error === null) {
                    const { [field]: _, ...rest } = prev
                    return rest
                }
                return { ...prev, [field]: error }
            })
        }, [])

        const setFieldTouched = useCallback((field: string, value: boolean) => {
            setTouched(prev => ({ ...prev, [field]: value }))
        }, [])

        const getFieldError = useCallback((field: string) => errors[field], [errors])
        const isFieldTouched = useCallback((field: string) => touched[field] || false, [touched])

        const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
            e.preventDefault()
            if (disabled || isSubmitting) return

            setIsSubmitting(true)
            try {
                const formData = new FormData(e.currentTarget)
                await onSubmit?.(formData)
            } finally {
                setIsSubmitting(false)
            }
        }

        return (
            <FormContext.Provider
                value={{
                    isSubmitting,
                    errors,
                    touched,
                    setFieldError,
                    setFieldTouched,
                    getFieldError,
                    isFieldTouched,
                }}
            >
                <form
                    ref={ref}
                    className={cn('space-y-6', className)}
                    onSubmit={handleSubmit}
                    {...props}
                >
                    <fieldset disabled={disabled || isSubmitting} className="space-y-6">
                        {children}
                    </fieldset>
                </form>
            </FormContext.Provider>
        )
    }
)
Form.displayName = 'Form'

// ============================================================================
// FORM FIELD
// ============================================================================

export interface FormFieldProps extends HTMLAttributes<HTMLDivElement> {
    /** Field name (for form submission) */
    name: string
    /** Field label */
    label?: string
    /** Helper text */
    helperText?: string
    /** Required field */
    required?: boolean
    /** Error message (overrides form context) */
    error?: string
    /** Show character count */
    showCharCount?: boolean
    /** Max characters */
    maxLength?: number
    /** Current character count */
    charCount?: number
    /** Horizontal layout */
    horizontal?: boolean
    children: ReactNode
}

export const FormField = forwardRef<HTMLDivElement, FormFieldProps>(
    (
        {
            className,
            name,
            label,
            helperText,
            required,
            error: externalError,
            showCharCount,
            maxLength,
            charCount = 0,
            horizontal,
            children,
            ...props
        },
        ref
    ) => {
        const id = useId()
        const fieldId = `${id}-${name}`
        const errorId = `${fieldId}-error`
        const helperId = `${fieldId}-helper`

        // Try to get error from context, fallback to prop
        let contextError: string | undefined
        try {
            const formContext = useFormContext()
            contextError = formContext.getFieldError(name)
        } catch {
            // Not inside a Form, use external error
        }

        const error = externalError || contextError
        const hasError = Boolean(error)

        return (
            <div
                ref={ref}
                className={cn(
                    'space-y-2',
                    horizontal && 'sm:flex sm:items-start sm:gap-4 sm:space-y-0',
                    className
                )}
                {...props}
            >
                {label && (
                    <label
                        htmlFor={fieldId}
                        className={cn(
                            'block text-sm font-medium text-gray-300',
                            horizontal && 'sm:w-1/3 sm:pt-2'
                        )}
                    >
                        {label}
                        {required && <span className="text-red-500 ml-1">*</span>}
                    </label>
                )}

                <div className={cn('flex-1', horizontal && 'sm:w-2/3')}>
                    {/* Clone child to inject props */}
                    {children}

                    {/* Helper text and error */}
                    <div className="mt-1.5 flex justify-between gap-2">
                        <div>
                            {hasError ? (
                                <p id={errorId} className="text-sm text-red-500" role="alert">
                                    {error}
                                </p>
                            ) : helperText ? (
                                <p id={helperId} className="text-sm text-gray-500">
                                    {helperText}
                                </p>
                            ) : null}
                        </div>

                        {showCharCount && maxLength && (
                            <span
                                className={cn(
                                    'text-xs',
                                    charCount > maxLength ? 'text-red-500' : 'text-gray-500'
                                )}
                            >
                                {charCount}/{maxLength}
                            </span>
                        )}
                    </div>
                </div>
            </div>
        )
    }
)
FormField.displayName = 'FormField'

// ============================================================================
// FORM GROUP
// ============================================================================

export interface FormGroupProps extends HTMLAttributes<HTMLDivElement> {
    /** Group title */
    title?: string
    /** Group description */
    description?: string
    /** Collapsible */
    collapsible?: boolean
    /** Default collapsed state */
    defaultCollapsed?: boolean
    children: ReactNode
}

export const FormGroup = forwardRef<HTMLDivElement, FormGroupProps>(
    (
        {
            className,
            title,
            description,
            collapsible,
            defaultCollapsed = false,
            children,
            ...props
        },
        ref
    ) => {
        const [isCollapsed, setIsCollapsed] = useState(defaultCollapsed)
        const contentRef = useRef<HTMLDivElement>(null)
        const [contentHeight, setContentHeight] = useState<number | 'auto'>('auto')

        useEffect(() => {
            if (contentRef.current) {
                setContentHeight(contentRef.current.scrollHeight)
            }
        }, [children])

        return (
            <div
                ref={ref}
                className={cn(
                    'rounded-lg border border-gray-700/50 bg-gray-800/30',
                    className
                )}
                {...props}
            >
                {(title || collapsible) && (
                    <div
                        className={cn(
                            'flex items-center justify-between px-4 py-3',
                            collapsible && 'cursor-pointer hover:bg-gray-700/30 transition-colors',
                            !isCollapsed && 'border-b border-gray-700/50'
                        )}
                        onClick={() => collapsible && setIsCollapsed(!isCollapsed)}
                    >
                        <div>
                            {title && (
                                <h3 className="text-sm font-semibold text-white">{title}</h3>
                            )}
                            {description && (
                                <p className="text-xs text-gray-500 mt-0.5">{description}</p>
                            )}
                        </div>

                        {collapsible && (
                            <motion.svg
                                animate={{ rotate: isCollapsed ? -90 : 0 }}
                                transition={{ duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
                                className="w-5 h-5 text-gray-400"
                                fill="none"
                                viewBox="0 0 24 24"
                                stroke="currentColor"
                            >
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </motion.svg>
                        )}
                    </div>
                )}

                <AnimatePresence initial={false}>
                    {!isCollapsed && (
                        <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: contentHeight, opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.2, ease: [0.4, 0, 0.2, 1] }}
                            className="overflow-hidden"
                        >
                            <div ref={contentRef} className="p-4 space-y-4">
                                {children}
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        )
    }
)
FormGroup.displayName = 'FormGroup'

// ============================================================================
// FORM SECTION
// ============================================================================

export interface FormSectionProps extends HTMLAttributes<HTMLDivElement> {
    /** Section title */
    title: string
    /** Section description */
    description?: string
    /** Icon */
    icon?: ReactNode
    children: ReactNode
}

export const FormSection = forwardRef<HTMLDivElement, FormSectionProps>(
    ({ className, title, description, icon, children, ...props }, ref) => {
        return (
            <div ref={ref} className={cn('space-y-4', className)} {...props}>
                <div className="flex items-center gap-3">
                    {icon && (
                        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary-500/20 to-accent-500/20 flex items-center justify-center text-primary-400">
                            {icon}
                        </div>
                    )}
                    <div>
                        <h2 className="text-lg font-semibold text-white">{title}</h2>
                        {description && (
                            <p className="text-sm text-gray-500">{description}</p>
                        )}
                    </div>
                </div>

                <div className="space-y-4 pl-0 sm:pl-13">
                    {children}
                </div>
            </div>
        )
    }
)
FormSection.displayName = 'FormSection'

// ============================================================================
// FORM ACTIONS
// ============================================================================

export interface FormActionsProps extends HTMLAttributes<HTMLDivElement> {
    /** Alignment */
    align?: 'left' | 'center' | 'right' | 'between'
    /** Sticky to bottom */
    sticky?: boolean
    children: ReactNode
}

const alignClasses = {
    left: 'justify-start',
    center: 'justify-center',
    right: 'justify-end',
    between: 'justify-between',
}

export const FormActions = forwardRef<HTMLDivElement, FormActionsProps>(
    ({ className, align = 'right', sticky, children, ...props }, ref) => {
        return (
            <div
                ref={ref}
                className={cn(
                    'flex items-center gap-3 pt-4 border-t border-gray-700/50',
                    alignClasses[align],
                    sticky && 'sticky bottom-0 bg-gray-900/95 backdrop-blur-sm py-4 -mx-4 px-4',
                    className
                )}
                {...props}
            >
                {children}
            </div>
        )
    }
)
FormActions.displayName = 'FormActions'

// ============================================================================
// RADIO GROUP
// ============================================================================

export interface RadioOption {
    value: string
    label: string
    description?: string
    disabled?: boolean
}

export interface RadioGroupProps extends Omit<HTMLAttributes<HTMLDivElement>, 'onChange'> {
    /** Field name */
    name: string
    /** Options */
    options: RadioOption[]
    /** Selected value */
    value?: string
    /** Change handler */
    onChange?: (value: string) => void
    /** Layout direction */
    direction?: 'horizontal' | 'vertical'
    /** Card style */
    cardStyle?: boolean
}

export const RadioGroup = forwardRef<HTMLDivElement, RadioGroupProps>(
    (
        {
            className,
            name,
            options,
            value,
            onChange,
            direction = 'vertical',
            cardStyle = false,
            ...props
        },
        ref
    ) => {
        return (
            <div
                ref={ref}
                role="radiogroup"
                className={cn(
                    direction === 'horizontal' ? 'flex flex-wrap gap-3' : 'space-y-2',
                    className
                )}
                {...props}
            >
                {options.map((option) => (
                    <label
                        key={option.value}
                        className={cn(
                            'flex items-start gap-3 cursor-pointer',
                            option.disabled && 'opacity-50 cursor-not-allowed',
                            cardStyle && [
                                'p-4 rounded-lg border transition-colors',
                                value === option.value
                                    ? 'border-primary-500 bg-primary-500/10'
                                    : 'border-gray-700 hover:border-gray-600 bg-gray-800/50'
                            ]
                        )}
                    >
                        <input
                            type="radio"
                            name={name}
                            value={option.value}
                            checked={value === option.value}
                            disabled={option.disabled}
                            onChange={(e) => onChange?.(e.target.value)}
                            className="sr-only"
                        />

                        <div
                            className={cn(
                                'w-5 h-5 rounded-full border-2 flex items-center justify-center flex-shrink-0 mt-0.5 transition-colors',
                                value === option.value
                                    ? 'border-primary-500 bg-primary-500'
                                    : 'border-gray-600'
                            )}
                        >
                            {value === option.value && (
                                <div className="w-2 h-2 rounded-full bg-white" />
                            )}
                        </div>

                        <div className="flex-1">
                            <span className="text-sm font-medium text-white">{option.label}</span>
                            {option.description && (
                                <p className="text-xs text-gray-500 mt-0.5">{option.description}</p>
                            )}
                        </div>
                    </label>
                ))}
            </div>
        )
    }
)
RadioGroup.displayName = 'RadioGroup'

// ============================================================================
// CHECKBOX GROUP
// ============================================================================

export interface CheckboxOption {
    value: string
    label: string
    description?: string
    disabled?: boolean
}

export interface CheckboxGroupProps extends Omit<HTMLAttributes<HTMLDivElement>, 'onChange'> {
    /** Field name */
    name: string
    /** Options */
    options: CheckboxOption[]
    /** Selected values */
    value?: string[]
    /** Change handler */
    onChange?: (values: string[]) => void
    /** Layout direction */
    direction?: 'horizontal' | 'vertical'
    /** Max selections */
    maxSelections?: number
}

export const CheckboxGroup = forwardRef<HTMLDivElement, CheckboxGroupProps>(
    (
        {
            className,
            name,
            options,
            value = [],
            onChange,
            direction = 'vertical',
            maxSelections,
            ...props
        },
        ref
    ) => {
        const handleChange = (optionValue: string, checked: boolean) => {
            let newValues: string[]

            if (checked) {
                if (maxSelections && value.length >= maxSelections) return
                newValues = [...value, optionValue]
            } else {
                newValues = value.filter(v => v !== optionValue)
            }

            onChange?.(newValues)
        }

        return (
            <div
                ref={ref}
                role="group"
                className={cn(
                    direction === 'horizontal' ? 'flex flex-wrap gap-4' : 'space-y-3',
                    className
                )}
                {...props}
            >
                {options.map((option) => {
                    const isChecked = value.includes(option.value)
                    const isDisabled = option.disabled || (maxSelections !== undefined && !isChecked && value.length >= maxSelections)

                    return (
                        <label
                            key={option.value}
                            className={cn(
                                'flex items-start gap-3 cursor-pointer',
                                isDisabled && 'opacity-50 cursor-not-allowed'
                            )}
                        >
                            <input
                                type="checkbox"
                                name={name}
                                value={option.value}
                                checked={isChecked}
                                disabled={isDisabled || false}
                                onChange={(e) => handleChange(option.value, e.target.checked)}
                                className="sr-only"
                            />

                            <div
                                className={cn(
                                    'w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 mt-0.5 transition-colors',
                                    isChecked
                                        ? 'border-primary-500 bg-primary-500'
                                        : 'border-gray-600'
                                )}
                            >
                                {isChecked && (
                                    <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                                    </svg>
                                )}
                            </div>

                            <div className="flex-1">
                                <span className="text-sm font-medium text-white">{option.label}</span>
                                {option.description && (
                                    <p className="text-xs text-gray-500 mt-0.5">{option.description}</p>
                                )}
                            </div>
                        </label>
                    )
                })}

                {maxSelections && (
                    <p className="text-xs text-gray-500">
                        {value.length}/{maxSelections} selected
                    </p>
                )}
            </div>
        )
    }
)
CheckboxGroup.displayName = 'CheckboxGroup'

// ============================================================================
// COLOR PICKER
// ============================================================================

export interface ColorPickerProps extends Omit<HTMLAttributes<HTMLDivElement>, 'onChange'> {
    /** Selected color */
    value?: string
    /** Change handler */
    onChange?: (color: string) => void
    /** Preset colors */
    presets?: string[]
    /** Show custom input */
    showCustom?: boolean
    /** Label */
    label?: string
}

const defaultPresets = [
    '#ef4444', '#f97316', '#eab308', '#22c55e', '#06b6d4',
    '#3b82f6', '#6366f1', '#8b5cf6', '#ec4899', '#f43f5e',
]

export const ColorPicker = forwardRef<HTMLDivElement, ColorPickerProps>(
    (
        {
            className,
            value = '#0ea5e9',
            onChange,
            presets = defaultPresets,
            showCustom = true,
            label,
            ...props
        },
        ref
    ) => {
        const id = useId()

        return (
            <div ref={ref} className={cn('space-y-3', className)} {...props}>
                {label && (
                    <label className="block text-sm font-medium text-gray-300">
                        {label}
                    </label>
                )}

                {/* Presets */}
                <div className="flex flex-wrap gap-2">
                    {presets.map((color) => (
                        <button
                            key={color}
                            type="button"
                            className={cn(
                                'w-8 h-8 rounded-lg border-2 transition-all',
                                value === color
                                    ? 'border-white scale-110'
                                    : 'border-transparent hover:scale-105'
                            )}
                            style={{ backgroundColor: color }}
                            onClick={() => onChange?.(color)}
                            title={color}
                        />
                    ))}
                </div>

                {/* Custom color input */}
                {showCustom && (
                    <div className="flex items-center gap-3">
                        <input
                            type="color"
                            id={id}
                            value={value}
                            onChange={(e) => onChange?.(e.target.value)}
                            className="w-10 h-10 rounded-lg border-0 cursor-pointer bg-transparent"
                        />
                        <input
                            type="text"
                            value={value}
                            onChange={(e) => onChange?.(e.target.value)}
                            className="flex-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white font-mono focus:outline-none focus:ring-2 focus:ring-primary-500"
                            placeholder="#000000"
                        />
                    </div>
                )}
            </div>
        )
    }
)
ColorPicker.displayName = 'ColorPicker'

// ============================================================================
// RANGE SLIDER
// ============================================================================

export interface RangeSliderProps extends Omit<HTMLAttributes<HTMLDivElement>, 'onChange'> {
    /** Min value */
    min?: number
    /** Max value */
    max?: number
    /** Step */
    step?: number
    /** Current value (single or range) */
    value?: number | [number, number]
    /** Change handler */
    onChange?: (value: number | [number, number]) => void
    /** Show value label */
    showValue?: boolean
    /** Format value for display */
    formatValue?: (value: number) => string
    /** Label */
    label?: string
    /** Marks to show on slider */
    marks?: { value: number; label?: string }[]
}

export const RangeSlider = forwardRef<HTMLDivElement, RangeSliderProps>(
    (
        {
            className,
            min = 0,
            max = 100,
            step = 1,
            value = 50,
            onChange,
            showValue = true,
            formatValue = (v) => v.toString(),
            label,
            marks,
            ...props
        },
        ref
    ) => {
        const isRange = Array.isArray(value)
        const currentValue = isRange ? value : [value, value]

        const handleChange = (index: 0 | 1) => (e: React.ChangeEvent<HTMLInputElement>) => {
            const newValue = parseFloat(e.target.value)
            if (isRange) {
                const newRange: [number, number] = [...currentValue] as [number, number]
                newRange[index] = newValue
                // Ensure min <= max
                if (index === 0 && newRange[0] > newRange[1]) newRange[0] = newRange[1]
                if (index === 1 && newRange[1] < newRange[0]) newRange[1] = newRange[0]
                onChange?.(newRange)
            } else {
                onChange?.(newValue)
            }
        }

        const percentage = (v: number) => ((v - min) / (max - min)) * 100

        return (
            <div ref={ref} className={cn('space-y-2', className)} {...props}>
                {(label || showValue) && (
                    <div className="flex justify-between items-center">
                        {label && (
                            <label className="text-sm font-medium text-gray-300">{label}</label>
                        )}
                        {showValue && (
                            <span className="text-sm text-primary-400 font-medium">
                                {isRange
                                    ? `${formatValue(currentValue[0])} - ${formatValue(currentValue[1])}`
                                    : formatValue(currentValue[0])}
                            </span>
                        )}
                    </div>
                )}

                <div className="relative h-6">
                    {/* Track background */}
                    <div className="absolute top-1/2 -translate-y-1/2 w-full h-2 rounded-full bg-gray-700" />

                    {/* Active track */}
                    <div
                        className="absolute top-1/2 -translate-y-1/2 h-2 rounded-full bg-gradient-to-r from-primary-500 to-accent-500"
                        style={{
                            left: isRange ? `${percentage(currentValue[0])}%` : '0%',
                            right: `${100 - percentage(isRange ? currentValue[1] : currentValue[0])}%`,
                        }}
                    />

                    {/* Marks */}
                    {marks?.map((mark) => (
                        <div
                            key={mark.value}
                            className="absolute top-1/2 -translate-y-1/2"
                            style={{ left: `${percentage(mark.value)}%` }}
                        >
                            <div className="w-1 h-3 bg-gray-600 rounded-full -ml-0.5" />
                            {mark.label && (
                                <span className="absolute top-4 left-1/2 -translate-x-1/2 text-[10px] text-gray-500 whitespace-nowrap">
                                    {mark.label}
                                </span>
                            )}
                        </div>
                    ))}

                    {/* Range inputs */}
                    {isRange && (
                        <input
                            type="range"
                            min={min}
                            max={max}
                            step={step}
                            value={currentValue[0]}
                            onChange={handleChange(0)}
                            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                        />
                    )}
                    <input
                        type="range"
                        min={min}
                        max={max}
                        step={step}
                        value={isRange ? currentValue[1] : currentValue[0]}
                        onChange={handleChange(isRange ? 1 : 0)}
                        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                    />

                    {/* Thumb(s) */}
                    {isRange && (
                        <div
                            className="absolute top-1/2 -translate-y-1/2 w-5 h-5 rounded-full bg-white shadow-lg border-2 border-primary-500 pointer-events-none"
                            style={{ left: `calc(${percentage(currentValue[0])}% - 10px)` }}
                        />
                    )}
                    <div
                        className="absolute top-1/2 -translate-y-1/2 w-5 h-5 rounded-full bg-white shadow-lg border-2 border-primary-500 pointer-events-none"
                        style={{ left: `calc(${percentage(isRange ? currentValue[1] : currentValue[0])}% - 10px)` }}
                    />
                </div>
            </div>
        )
    }
)
RangeSlider.displayName = 'RangeSlider'

// ============================================================================
// EXPORTS
// ============================================================================

export type {
    FormContextValue,
}
