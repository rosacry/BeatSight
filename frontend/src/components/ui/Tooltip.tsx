/**
 * Tooltip Components
 * Accessible, animated tooltips with multiple placement options.
 */

import React, { useState, useRef, useEffect, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'

// ============================================================================
// Tooltip Variants
// ============================================================================

const tooltipVariants = cva(
    [
        'z-50 px-3 py-1.5 text-sm rounded-lg',
        'bg-slate-800 border border-slate-700/50 text-slate-200',
        'shadow-lg shadow-black/30',
        'animate-in fade-in-0 zoom-in-95 duration-150',
    ],
    {
        variants: {
            variant: {
                default: 'bg-slate-800 border-slate-700/50',
                dark: 'bg-slate-900 border-slate-700',
                light: 'bg-slate-100 border-slate-200 text-slate-900',
                cyan: 'bg-cyan-900/90 border-cyan-500/30 text-cyan-100',
                magenta: 'bg-fuchsia-900/90 border-fuchsia-500/30 text-fuchsia-100',
            },
        },
        defaultVariants: {
            variant: 'default',
        },
    }
)

const arrowVariants = cva('absolute w-2 h-2 rotate-45', {
    variants: {
        variant: {
            default: 'bg-slate-800 border-slate-700/50',
            dark: 'bg-slate-900 border-slate-700',
            light: 'bg-slate-100 border-slate-200',
            cyan: 'bg-cyan-900/90 border-cyan-500/30',
            magenta: 'bg-fuchsia-900/90 border-fuchsia-500/30',
        },
        placement: {
            top: 'bottom-[-5px] border-r border-b',
            bottom: 'top-[-5px] border-l border-t',
            left: 'right-[-5px] border-r border-t',
            right: 'left-[-5px] border-l border-b',
        },
    },
    defaultVariants: {
        variant: 'default',
        placement: 'top',
    },
})

// ============================================================================
// Types
// ============================================================================

type Placement = 'top' | 'bottom' | 'left' | 'right'

export interface TooltipProps extends VariantProps<typeof tooltipVariants> {
    content: React.ReactNode
    children: React.ReactElement
    placement?: Placement
    delay?: number
    offset?: number
    disabled?: boolean
    arrow?: boolean
    className?: string
    contentClassName?: string
}

// ============================================================================
// Position Calculation
// ============================================================================

interface Position {
    top: number
    left: number
    actualPlacement: Placement
}

function calculatePosition(
    triggerRect: DOMRect,
    tooltipRect: DOMRect,
    placement: Placement,
    offset: number
): Position {
    const viewportWidth = window.innerWidth
    const viewportHeight = window.innerHeight

    let top = 0
    let left = 0
    let actualPlacement = placement

    // Calculate initial position based on placement
    switch (placement) {
        case 'top':
            top = triggerRect.top - tooltipRect.height - offset
            left = triggerRect.left + triggerRect.width / 2 - tooltipRect.width / 2
            break
        case 'bottom':
            top = triggerRect.bottom + offset
            left = triggerRect.left + triggerRect.width / 2 - tooltipRect.width / 2
            break
        case 'left':
            top = triggerRect.top + triggerRect.height / 2 - tooltipRect.height / 2
            left = triggerRect.left - tooltipRect.width - offset
            break
        case 'right':
            top = triggerRect.top + triggerRect.height / 2 - tooltipRect.height / 2
            left = triggerRect.right + offset
            break
    }

    // Flip placement if out of viewport
    if (placement === 'top' && top < 0) {
        top = triggerRect.bottom + offset
        actualPlacement = 'bottom'
    } else if (placement === 'bottom' && top + tooltipRect.height > viewportHeight) {
        top = triggerRect.top - tooltipRect.height - offset
        actualPlacement = 'top'
    } else if (placement === 'left' && left < 0) {
        left = triggerRect.right + offset
        actualPlacement = 'right'
    } else if (placement === 'right' && left + tooltipRect.width > viewportWidth) {
        left = triggerRect.left - tooltipRect.width - offset
        actualPlacement = 'left'
    }

    // Ensure tooltip stays within horizontal bounds
    if (left < 8) left = 8
    if (left + tooltipRect.width > viewportWidth - 8) {
        left = viewportWidth - tooltipRect.width - 8
    }

    // Add scroll offset
    top += window.scrollY
    left += window.scrollX

    return { top, left, actualPlacement }
}

// ============================================================================
// Tooltip Component
// ============================================================================

export function Tooltip({
    content,
    children,
    placement = 'top',
    delay = 200,
    offset = 8,
    disabled = false,
    arrow = true,
    variant,
    className,
    contentClassName,
}: TooltipProps) {
    const [isVisible, setIsVisible] = useState(false)
    const [position, setPosition] = useState<Position>({ top: 0, left: 0, actualPlacement: placement })
    const triggerRef = useRef<HTMLElement | null>(null)
    const tooltipRef = useRef<HTMLDivElement>(null)
    const timeoutRef = useRef<ReturnType<typeof setTimeout>>()

    const show = useCallback(() => {
        if (disabled) return
        timeoutRef.current = setTimeout(() => setIsVisible(true), delay)
    }, [disabled, delay])

    const hide = useCallback(() => {
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current)
        }
        setIsVisible(false)
    }, [])

    // Update position when visible
    useEffect(() => {
        if (!isVisible || !triggerRef.current || !tooltipRef.current) return

        const triggerRect = triggerRef.current.getBoundingClientRect()
        const tooltipRect = tooltipRef.current.getBoundingClientRect()
        const newPosition = calculatePosition(triggerRect, tooltipRect, placement, offset)
        setPosition(newPosition)

        // Update position on scroll/resize
        const handleUpdate = () => {
            if (!triggerRef.current || !tooltipRef.current) return
            const rect = triggerRef.current.getBoundingClientRect()
            const tipRect = tooltipRef.current.getBoundingClientRect()
            setPosition(calculatePosition(rect, tipRect, placement, offset))
        }

        window.addEventListener('scroll', handleUpdate, true)
        window.addEventListener('resize', handleUpdate)

        return () => {
            window.removeEventListener('scroll', handleUpdate, true)
            window.removeEventListener('resize', handleUpdate)
        }
    }, [isVisible, placement, offset])

    // Cleanup timeout on unmount
    useEffect(() => {
        return () => {
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current)
            }
        }
    }, [])

    // Clone child with event handlers
    const trigger = React.cloneElement(children, {
        ref: (node: HTMLElement) => {
            triggerRef.current = node
            // Forward ref if child has one
            const childRef = (children as any).ref
            if (typeof childRef === 'function') childRef(node)
            else if (childRef) childRef.current = node
        },
        onMouseEnter: (e: React.MouseEvent) => {
            show()
            children.props.onMouseEnter?.(e)
        },
        onMouseLeave: (e: React.MouseEvent) => {
            hide()
            children.props.onMouseLeave?.(e)
        },
        onFocus: (e: React.FocusEvent) => {
            show()
            children.props.onFocus?.(e)
        },
        onBlur: (e: React.FocusEvent) => {
            hide()
            children.props.onBlur?.(e)
        },
        'aria-describedby': isVisible ? 'tooltip' : undefined,
    })

    return (
        <>
            {trigger}
            {isVisible &&
                createPortal(
                    <div
                        ref={tooltipRef}
                        id="tooltip"
                        role="tooltip"
                        className={cn(tooltipVariants({ variant }), 'fixed', className)}
                        style={{
                            top: position.top,
                            left: position.left,
                        }}
                    >
                        {arrow && (
                            <div
                                className={cn(arrowVariants({ variant, placement: position.actualPlacement }))}
                                style={{
                                    left:
                                        position.actualPlacement === 'top' || position.actualPlacement === 'bottom'
                                            ? '50%'
                                            : undefined,
                                    transform:
                                        position.actualPlacement === 'top' || position.actualPlacement === 'bottom'
                                            ? 'translateX(-50%) rotate(45deg)'
                                            : 'rotate(45deg)',
                                    top:
                                        position.actualPlacement === 'left' || position.actualPlacement === 'right'
                                            ? '50%'
                                            : undefined,
                                    marginTop:
                                        position.actualPlacement === 'left' || position.actualPlacement === 'right'
                                            ? '-4px'
                                            : undefined,
                                }}
                            />
                        )}
                        <div className={cn('relative z-10', contentClassName)}>{content}</div>
                    </div>,
                    document.body
                )}
        </>
    )
}

// ============================================================================
// Rich Tooltip (with title, description, etc.)
// ============================================================================

export interface RichTooltipProps extends Omit<TooltipProps, 'content'> {
    title?: string
    description?: string
    icon?: React.ReactNode
    action?: {
        label: string
        onClick: () => void
    }
}

export function RichTooltip({
    title,
    description,
    icon,
    action,
    children,
    ...props
}: RichTooltipProps) {
    const content = (
        <div className="max-w-xs">
            <div className="flex items-start gap-2">
                {icon && <div className="flex-shrink-0 text-cyan-400">{icon}</div>}
                <div className="flex-1 min-w-0">
                    {title && <div className="font-medium text-slate-100">{title}</div>}
                    {description && <div className="text-sm text-slate-400 mt-0.5">{description}</div>}
                    {action && (
                        <button
                            onClick={(e) => {
                                e.stopPropagation()
                                action.onClick()
                            }}
                            className="mt-2 text-xs text-cyan-400 hover:text-cyan-300 font-medium"
                        >
                            {action.label} →
                        </button>
                    )}
                </div>
            </div>
        </div>
    )

    return (
        <Tooltip content={content} {...props}>
            {children}
        </Tooltip>
    )
}

// ============================================================================
// Keyboard Shortcut Tooltip
// ============================================================================

export interface ShortcutTooltipProps extends Omit<TooltipProps, 'content'> {
    label: string
    shortcut: string | string[]
}

export function ShortcutTooltip({ label, shortcut, children, ...props }: ShortcutTooltipProps) {
    const shortcuts = Array.isArray(shortcut) ? shortcut : [shortcut]

    const content = (
        <div className="flex items-center gap-3">
            <span>{label}</span>
            <div className="flex items-center gap-1">
                {shortcuts.map((key, index) => (
                    <React.Fragment key={key}>
                        {index > 0 && <span className="text-slate-500">+</span>}
                        <kbd
                            className={cn(
                                'px-1.5 py-0.5 text-xs font-mono rounded',
                                'bg-slate-700 border border-slate-600 text-slate-300',
                                'shadow-sm'
                            )}
                        >
                            {key}
                        </kbd>
                    </React.Fragment>
                ))}
            </div>
        </div>
    )

    return (
        <Tooltip content={content} {...props}>
            {children}
        </Tooltip>
    )
}

// ============================================================================
// Info Tooltip (with info icon)
// ============================================================================

export interface InfoTooltipProps extends Omit<TooltipProps, 'children'> {
    size?: 'sm' | 'md' | 'lg'
    iconClassName?: string
}

export function InfoTooltip({ content, size = 'md', iconClassName, ...props }: InfoTooltipProps) {
    const sizeClasses = {
        sm: 'w-3.5 h-3.5',
        md: 'w-4 h-4',
        lg: 'w-5 h-5',
    }

    return (
        <Tooltip content={content} {...props}>
            <button
                type="button"
                className={cn(
                    'inline-flex items-center justify-center rounded-full',
                    'text-slate-500 hover:text-slate-400 transition-colors',
                    'focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/50'
                )}
                aria-label="More information"
            >
                <svg
                    className={cn(sizeClasses[size], iconClassName)}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                >
                    <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                </svg>
            </button>
        </Tooltip>
    )
}

export { tooltipVariants, arrowVariants }
