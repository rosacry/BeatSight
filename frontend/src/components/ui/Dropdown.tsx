/**
 * Dropdown/Select Components
 * Modern dropdown and select components with animations and accessibility.
 */

import React, { useState, useRef, useEffect, useCallback, createContext, useContext } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'

// Animation variants for dropdown menu
const dropdownAnimationVariants = {
    hidden: {
        opacity: 0,
        scale: 0.95,
        y: -8,
    },
    visible: {
        opacity: 1,
        scale: 1,
        y: 0,
        transition: {
            duration: 0.15,
            ease: [0.4, 0, 0.2, 1],
        },
    },
    exit: {
        opacity: 0,
        scale: 0.95,
        y: -8,
        transition: {
            duration: 0.1,
            ease: [0.4, 0, 1, 1],
        },
    },
}

// Animation props that conflict with Framer Motion
type ConflictingAnimationProps = 'onAnimationStart' | 'onAnimationEnd' | 'onDragStart' | 'onDragEnd' | 'onDrag'

// ============================================================================
// Dropdown Context
// ============================================================================

interface DropdownContextType {
    isOpen: boolean
    setIsOpen: (open: boolean) => void
    selectedValue: string | null
    setSelectedValue: (value: string) => void
    highlightedIndex: number
    setHighlightedIndex: (index: number) => void
}

const DropdownContext = createContext<DropdownContextType | null>(null)

const useDropdown = () => {
    const context = useContext(DropdownContext)
    if (!context) {
        throw new Error('Dropdown components must be used within a Dropdown provider')
    }
    return context
}

// ============================================================================
// Dropdown Variants
// ============================================================================

const dropdownTriggerVariants = cva(
    [
        'inline-flex items-center justify-between gap-2',
        'rounded-lg border bg-slate-900/50 text-slate-200',
        'transition-all duration-200',
        'focus:outline-none focus:ring-2 focus:ring-cyan-500/50',
        'disabled:opacity-50 disabled:cursor-not-allowed',
    ],
    {
        variants: {
            variant: {
                default: 'border-slate-700 hover:border-slate-600 hover:bg-slate-800/50',
                outline: 'border-slate-600 hover:border-cyan-500/50 hover:bg-slate-800/30',
                ghost: 'border-transparent bg-transparent hover:bg-slate-800/50',
            },
            size: {
                sm: 'px-3 py-1.5 text-sm min-w-[120px]',
                md: 'px-4 py-2 text-sm min-w-[160px]',
                lg: 'px-5 py-2.5 text-base min-w-[200px]',
            },
        },
        defaultVariants: {
            variant: 'default',
            size: 'md',
        },
    }
)

const dropdownMenuVariants = cva(
    [
        'absolute z-50 min-w-[160px] overflow-hidden',
        'rounded-lg border border-slate-700 bg-slate-900/95 backdrop-blur-xl',
        'shadow-xl shadow-black/30',
        'origin-top transition-all duration-200',
    ],
    {
        variants: {
            position: {
                bottom: 'top-full mt-2',
                top: 'bottom-full mb-2',
            },
            align: {
                start: 'left-0',
                center: 'left-1/2 -translate-x-1/2',
                end: 'right-0',
            },
        },
        defaultVariants: {
            position: 'bottom',
            align: 'start',
        },
    }
)

// ============================================================================
// Dropdown Components
// ============================================================================

export interface DropdownProps {
    children: React.ReactNode
    value?: string
    onValueChange?: (value: string) => void
    defaultOpen?: boolean
}

export function Dropdown({ children, value, onValueChange, defaultOpen = false }: DropdownProps) {
    const [isOpen, setIsOpen] = useState(defaultOpen)
    const [selectedValue, setSelectedValueState] = useState<string | null>(value ?? null)
    const [highlightedIndex, setHighlightedIndex] = useState(-1)

    const setSelectedValue = useCallback(
        (newValue: string) => {
            setSelectedValueState(newValue)
            onValueChange?.(newValue)
            setIsOpen(false)
        },
        [onValueChange]
    )

    useEffect(() => {
        if (value !== undefined) {
            setSelectedValueState(value)
        }
    }, [value])

    return (
        <DropdownContext.Provider
            value={{
                isOpen,
                setIsOpen,
                selectedValue,
                setSelectedValue,
                highlightedIndex,
                setHighlightedIndex,
            }}
        >
            <div className="relative inline-block">{children}</div>
        </DropdownContext.Provider>
    )
}

// ============================================================================
// Dropdown Trigger
// ============================================================================

export interface DropdownTriggerProps
    extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof dropdownTriggerVariants> {
    placeholder?: string
}

export const DropdownTrigger = React.forwardRef<HTMLButtonElement, DropdownTriggerProps>(
    ({ className, variant, size, placeholder = 'Select...', children, ...props }, ref) => {
        const { isOpen, setIsOpen, selectedValue } = useDropdown()

        const handleClick = () => {
            setIsOpen(!isOpen)
        }

        const handleKeyDown = (e: React.KeyboardEvent) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                setIsOpen(!isOpen)
            } else if (e.key === 'Escape') {
                setIsOpen(false)
            }
        }

        return (
            <button
                ref={ref}
                type="button"
                role="combobox"
                aria-expanded={isOpen}
                aria-haspopup="listbox"
                onClick={handleClick}
                onKeyDown={handleKeyDown}
                className={cn(dropdownTriggerVariants({ variant, size }), className)}
                {...props}
            >
                <span className={cn(!selectedValue && 'text-slate-500')}>
                    {children ?? selectedValue ?? placeholder}
                </span>
                <svg
                    className={cn(
                        'h-4 w-4 text-slate-400 transition-transform duration-200',
                        isOpen && 'rotate-180'
                    )}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
            </button>
        )
    }
)
DropdownTrigger.displayName = 'DropdownTrigger'

// ============================================================================
// Dropdown Menu
// ============================================================================

export interface DropdownMenuProps
    extends Omit<React.HTMLAttributes<HTMLDivElement>, ConflictingAnimationProps>,
    VariantProps<typeof dropdownMenuVariants> { }

export function DropdownMenu({ className, position, align, children, ...props }: DropdownMenuProps) {
    const { isOpen, setIsOpen } = useDropdown()
    const menuRef = useRef<HTMLDivElement>(null)

    // Close on click outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (menuRef.current && !menuRef.current.parentElement?.contains(event.target as Node)) {
                setIsOpen(false)
            }
        }

        if (isOpen) {
            document.addEventListener('mousedown', handleClickOutside)
            return () => document.removeEventListener('mousedown', handleClickOutside)
        }
    }, [isOpen, setIsOpen])

    return (
        <AnimatePresence>
            {isOpen && (
                <motion.div
                    ref={menuRef}
                    role="listbox"
                    variants={dropdownAnimationVariants}
                    initial="hidden"
                    animate="visible"
                    exit="exit"
                    className={cn(
                        dropdownMenuVariants({ position, align }),
                        className
                    )}
                    {...props}
                >
                    <div className="py-1">{children}</div>
                </motion.div>
            )}
        </AnimatePresence>
    )
}

// ============================================================================
// Dropdown Item
// ============================================================================

export interface DropdownItemProps extends React.HTMLAttributes<HTMLDivElement> {
    value: string
    disabled?: boolean
}

export function DropdownItem({ className, value, disabled, children, ...props }: DropdownItemProps) {
    const { selectedValue, setSelectedValue } = useDropdown()
    const isSelected = selectedValue === value

    const handleClick = () => {
        if (!disabled) {
            setSelectedValue(value)
        }
    }

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            if (!disabled) {
                setSelectedValue(value)
            }
        }
    }

    return (
        <div
            role="option"
            aria-selected={isSelected}
            aria-disabled={disabled}
            tabIndex={disabled ? -1 : 0}
            onClick={handleClick}
            onKeyDown={handleKeyDown}
            className={cn(
                'relative flex items-center px-3 py-2 text-sm cursor-pointer',
                'transition-colors duration-150',
                'outline-none focus:bg-slate-800/80',
                isSelected
                    ? 'bg-cyan-500/10 text-cyan-400'
                    : 'text-slate-300 hover:bg-slate-800/50 hover:text-slate-100',
                disabled && 'opacity-50 cursor-not-allowed hover:bg-transparent',
                className
            )}
            {...props}
        >
            {isSelected && (
                <svg
                    className="absolute left-2 h-4 w-4 text-cyan-400"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
            )}
            <span className={cn(isSelected && 'pl-5')}>{children}</span>
        </div>
    )
}

// ============================================================================
// Dropdown Separator
// ============================================================================

export function DropdownSeparator({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
    return <div className={cn('my-1 h-px bg-slate-700', className)} {...props} />
}

// ============================================================================
// Dropdown Label
// ============================================================================

export function DropdownLabel({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
    return (
        <div
            className={cn('px-3 py-1.5 text-xs font-semibold text-slate-500 uppercase tracking-wider', className)}
            {...props}
        >
            {children}
        </div>
    )
}

// ============================================================================
// Select Component (Simplified Dropdown)
// ============================================================================

export interface SelectOption {
    value: string
    label: string
    disabled?: boolean
}

export interface SelectProps extends VariantProps<typeof dropdownTriggerVariants> {
    options: SelectOption[]
    value?: string
    onValueChange?: (value: string) => void
    placeholder?: string
    disabled?: boolean
    className?: string
    label?: string
    error?: string
}

export function Select({
    options,
    value,
    onValueChange,
    placeholder = 'Select an option...',
    disabled,
    variant,
    size,
    className,
    label,
    error,
}: SelectProps) {
    const selectedOption = options.find((opt) => opt.value === value)

    return (
        <div className={cn('w-full', className)}>
            {label && <label className="block text-sm font-medium text-slate-300 mb-1.5">{label}</label>}
            <Dropdown value={value} onValueChange={onValueChange}>
                <DropdownTrigger variant={variant} size={size} disabled={disabled} placeholder={placeholder}>
                    {selectedOption?.label}
                </DropdownTrigger>
                <DropdownMenu className="w-full">
                    {options.map((option) => (
                        <DropdownItem key={option.value} value={option.value} disabled={option.disabled}>
                            {option.label}
                        </DropdownItem>
                    ))}
                </DropdownMenu>
            </Dropdown>
            {error && <p className="mt-1.5 text-xs text-red-400">{error}</p>}
        </div>
    )
}

// ============================================================================
// Multi-Select Component
// ============================================================================

export interface MultiSelectProps extends VariantProps<typeof dropdownTriggerVariants> {
    options: SelectOption[]
    value?: string[]
    onValueChange?: (value: string[]) => void
    placeholder?: string
    disabled?: boolean
    className?: string
    label?: string
    error?: string
    maxDisplay?: number
}

export function MultiSelect({
    options,
    value = [],
    onValueChange,
    placeholder = 'Select options...',
    disabled,
    variant,
    size,
    className,
    label,
    error,
    maxDisplay = 2,
}: MultiSelectProps) {
    const [isOpen, setIsOpen] = useState(false)
    const containerRef = useRef<HTMLDivElement>(null)

    const selectedOptions = options.filter((opt) => value.includes(opt.value))

    const displayText =
        selectedOptions.length === 0
            ? placeholder
            : selectedOptions.length <= maxDisplay
                ? selectedOptions.map((opt) => opt.label).join(', ')
                : `${selectedOptions.length} selected`

    const toggleOption = (optionValue: string) => {
        const newValue = value.includes(optionValue)
            ? value.filter((v) => v !== optionValue)
            : [...value, optionValue]
        onValueChange?.(newValue)
    }

    // Close on click outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
                setIsOpen(false)
            }
        }

        if (isOpen) {
            document.addEventListener('mousedown', handleClickOutside)
            return () => document.removeEventListener('mousedown', handleClickOutside)
        }
    }, [isOpen])

    return (
        <div ref={containerRef} className={cn('relative w-full', className)}>
            {label && <label className="block text-sm font-medium text-slate-300 mb-1.5">{label}</label>}
            <button
                type="button"
                onClick={() => setIsOpen(!isOpen)}
                disabled={disabled}
                className={cn(
                    dropdownTriggerVariants({ variant, size }),
                    'w-full',
                    selectedOptions.length === 0 && 'text-slate-500'
                )}
            >
                <span className="truncate">{displayText}</span>
                <svg
                    className={cn('h-4 w-4 text-slate-400 transition-transform duration-200', isOpen && 'rotate-180')}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
            </button>

            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        variants={dropdownAnimationVariants}
                        initial="hidden"
                        animate="visible"
                        exit="exit"
                        className={cn(
                            dropdownMenuVariants({ position: 'bottom', align: 'start' }),
                            'w-full'
                        )}
                    >
                        <div className="py-1 max-h-60 overflow-auto">
                            {options.map((option) => {
                                const isSelected = value.includes(option.value)
                                return (
                                    <div
                                        key={option.value}
                                        onClick={() => !option.disabled && toggleOption(option.value)}
                                        className={cn(
                                            'relative flex items-center gap-2 px-3 py-2 text-sm cursor-pointer',
                                            'transition-colors duration-150',
                                            isSelected
                                                ? 'bg-cyan-500/10 text-cyan-400'
                                                : 'text-slate-300 hover:bg-slate-800/50',
                                            option.disabled && 'opacity-50 cursor-not-allowed'
                                        )}
                                    >
                                        <div
                                            className={cn(
                                                'h-4 w-4 rounded border flex items-center justify-center',
                                                'transition-colors duration-150',
                                                isSelected
                                                    ? 'bg-cyan-500 border-cyan-500'
                                                    : 'border-slate-600 bg-slate-800/50'
                                            )}
                                        >
                                            {isSelected && (
                                                <svg
                                                    className="h-3 w-3 text-white"
                                                    fill="none"
                                                    viewBox="0 0 24 24"
                                                    stroke="currentColor"
                                                >
                                                    <path
                                                        strokeLinecap="round"
                                                        strokeLinejoin="round"
                                                        strokeWidth={3}
                                                        d="M5 13l4 4L19 7"
                                                    />
                                                </svg>
                                            )}
                                        </div>
                                        {option.label}
                                    </div>
                                )
                            })}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {error && <p className="mt-1.5 text-xs text-red-400">{error}</p>}
        </div>
    )
}

export { dropdownTriggerVariants, dropdownMenuVariants }
