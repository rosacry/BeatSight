/**
 * Accordion/Collapsible components with smooth animations.
 */

import {
    forwardRef,
    createContext,
    useContext,
    useState,
    useRef,
    useEffect,
    type HTMLAttributes,
    type ReactNode,
} from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { clsx } from 'clsx'

// ============================================================================
// ACCORDION CONTEXT
// ============================================================================

interface AccordionContextValue {
    expandedItems: Set<string>
    toggleItem: (id: string) => void
    allowMultiple: boolean
    variant: 'default' | 'bordered' | 'separated'
}

const AccordionContext = createContext<AccordionContextValue | null>(null)

// ============================================================================
// ACCORDION
// ============================================================================

const accordionVariants = cva('', {
    variants: {
        variant: {
            default: 'divide-y divide-gray-700/50',
            bordered: 'border border-white/10/50 rounded-xl divide-y divide-gray-700/50 overflow-hidden',
            separated: 'space-y-2',
        },
    },
    defaultVariants: {
        variant: 'default',
    },
})

export interface AccordionProps
    extends HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof accordionVariants> {
    /** Allow multiple items to be expanded */
    allowMultiple?: boolean
    /** Default expanded items */
    defaultExpanded?: string[]
    /** Controlled expanded items */
    expandedItems?: string[]
    /** Expansion change handler */
    onExpandedChange?: (items: string[]) => void
    children: ReactNode
}

export const Accordion = forwardRef<HTMLDivElement, AccordionProps>(
    (
        {
            className,
            variant = 'default',
            allowMultiple = false,
            defaultExpanded = [],
            expandedItems: controlledExpanded,
            onExpandedChange,
            children,
            ...props
        },
        ref
    ) => {
        const [internalExpanded, setInternalExpanded] = useState<Set<string>>(
            new Set(defaultExpanded)
        )

        const expandedItems = controlledExpanded
            ? new Set(controlledExpanded)
            : internalExpanded

        const toggleItem = (id: string) => {
            const newExpanded = new Set(expandedItems)

            if (newExpanded.has(id)) {
                newExpanded.delete(id)
            } else {
                if (!allowMultiple) {
                    newExpanded.clear()
                }
                newExpanded.add(id)
            }

            setInternalExpanded(newExpanded)
            onExpandedChange?.(Array.from(newExpanded))
        }

        return (
            <AccordionContext.Provider value={{ expandedItems, toggleItem, allowMultiple, variant: variant! }}>
                <div
                    ref={ref}
                    className={clsx(accordionVariants({ variant }), className)}
                    {...props}
                >
                    {children}
                </div>
            </AccordionContext.Provider>
        )
    }
)

Accordion.displayName = 'Accordion'

// ============================================================================
// ACCORDION ITEM
// ============================================================================

const accordionItemVariants = cva('', {
    variants: {
        variant: {
            default: '',
            bordered: '',
            separated: 'border border-white/10/50 rounded-xl overflow-hidden',
        },
    },
    defaultVariants: {
        variant: 'default',
    },
})

export interface AccordionItemProps extends HTMLAttributes<HTMLDivElement> {
    /** Unique ID */
    id: string
    /** Disabled state */
    disabled?: boolean
    children: ReactNode
}

export const AccordionItem = forwardRef<HTMLDivElement, AccordionItemProps>(
    ({ className, id: _id, disabled = false, children, ...props }, ref) => {
        const context = useContext(AccordionContext)
        if (!context) throw new Error('AccordionItem must be used within Accordion')

        const { variant } = context

        return (
            <div
                ref={ref}
                className={clsx(
                    accordionItemVariants({ variant }),
                    disabled && 'opacity-50',
                    className
                )}
                data-disabled={disabled || undefined}
                {...props}
            >
                {children}
            </div>
        )
    }
)

AccordionItem.displayName = 'AccordionItem'

// ============================================================================
// ACCORDION TRIGGER
// ============================================================================

export interface AccordionTriggerProps extends HTMLAttributes<HTMLButtonElement> {
    /** Parent item ID */
    itemId: string
    /** Left icon */
    icon?: ReactNode
    /** Disabled state */
    disabled?: boolean
    children: ReactNode
}

export const AccordionTrigger = forwardRef<HTMLButtonElement, AccordionTriggerProps>(
    ({ className, itemId, icon, disabled = false, children, ...props }, ref) => {
        const context = useContext(AccordionContext)
        if (!context) throw new Error('AccordionTrigger must be used within Accordion')

        const { expandedItems, toggleItem } = context
        const isExpanded = expandedItems.has(itemId)

        return (
            <button
                ref={ref}
                type="button"
                className={clsx(
                    'w-full flex items-center justify-between gap-4 px-4 py-4',
                    'text-left font-medium text-gray-200 hover:text-white',
                    'focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary-500',
                    'transition-colors',
                    disabled && 'cursor-not-allowed',
                    className
                )}
                onClick={() => !disabled && toggleItem(itemId)}
                disabled={disabled}
                aria-expanded={isExpanded}
                {...props}
            >
                <span className="flex items-center gap-3">
                    {icon && <span className="text-gray-400">{icon}</span>}
                    {children}
                </span>
                <svg
                    className={clsx(
                        'w-5 h-5 text-gray-400 transition-transform duration-300',
                        isExpanded && 'rotate-180'
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

AccordionTrigger.displayName = 'AccordionTrigger'

// ============================================================================
// ACCORDION CONTENT
// ============================================================================

export interface AccordionContentProps extends HTMLAttributes<HTMLDivElement> {
    /** Parent item ID */
    itemId: string
    children: ReactNode
}

export const AccordionContent = forwardRef<HTMLDivElement, AccordionContentProps>(
    ({ className, itemId, children, ...props }, ref) => {
        const context = useContext(AccordionContext)
        if (!context) throw new Error('AccordionContent must be used within Accordion')

        const { expandedItems } = context
        const isExpanded = expandedItems.has(itemId)
        const contentRef = useRef<HTMLDivElement>(null)
        const [height, setHeight] = useState(0)

        useEffect(() => {
            if (contentRef.current) {
                setHeight(isExpanded ? contentRef.current.scrollHeight : 0)
            }
        }, [isExpanded, children])

        return (
            <div
                ref={ref}
                className={clsx('overflow-hidden transition-all duration-300 ease-out', className)}
                style={{ height }}
                aria-hidden={!isExpanded}
                {...props}
            >
                <div ref={contentRef} className="px-4 pb-4 text-gray-400">
                    {children}
                </div>
            </div>
        )
    }
)

AccordionContent.displayName = 'AccordionContent'

// ============================================================================
// COLLAPSIBLE (Standalone)
// ============================================================================

export interface CollapsibleProps extends HTMLAttributes<HTMLDivElement> {
    /** Controlled open state */
    open?: boolean
    /** Default open state */
    defaultOpen?: boolean
    /** Open change handler */
    onOpenChange?: (open: boolean) => void
    children: ReactNode
}

interface CollapsibleContextValue {
    isOpen: boolean
    toggle: () => void
}

const CollapsibleContext = createContext<CollapsibleContextValue | null>(null)

export const Collapsible = forwardRef<HTMLDivElement, CollapsibleProps>(
    ({ className, open: controlledOpen, defaultOpen = false, onOpenChange, children, ...props }, ref) => {
        const [internalOpen, setInternalOpen] = useState(defaultOpen)
        const isOpen = controlledOpen ?? internalOpen

        const toggle = () => {
            const newState = !isOpen
            setInternalOpen(newState)
            onOpenChange?.(newState)
        }

        return (
            <CollapsibleContext.Provider value={{ isOpen, toggle }}>
                <div ref={ref} className={className} {...props}>
                    {children}
                </div>
            </CollapsibleContext.Provider>
        )
    }
)

Collapsible.displayName = 'Collapsible'

export interface CollapsibleTriggerProps extends HTMLAttributes<HTMLButtonElement> {
    children: ReactNode
    asChild?: boolean
}

export const CollapsibleTrigger = forwardRef<HTMLButtonElement, CollapsibleTriggerProps>(
    ({ className, children, ...props }, ref) => {
        const context = useContext(CollapsibleContext)
        if (!context) throw new Error('CollapsibleTrigger must be used within Collapsible')

        const { isOpen, toggle } = context

        return (
            <button
                ref={ref}
                type="button"
                className={className}
                onClick={toggle}
                aria-expanded={isOpen}
                {...props}
            >
                {children}
            </button>
        )
    }
)

CollapsibleTrigger.displayName = 'CollapsibleTrigger'

export interface CollapsibleContentProps extends HTMLAttributes<HTMLDivElement> {
    children: ReactNode
}

export const CollapsibleContent = forwardRef<HTMLDivElement, CollapsibleContentProps>(
    ({ className, children, ...props }, ref) => {
        const context = useContext(CollapsibleContext)
        if (!context) throw new Error('CollapsibleContent must be used within Collapsible')

        const { isOpen } = context
        const contentRef = useRef<HTMLDivElement>(null)
        const [height, setHeight] = useState(0)

        useEffect(() => {
            if (contentRef.current) {
                setHeight(isOpen ? contentRef.current.scrollHeight : 0)
            }
        }, [isOpen, children])

        return (
            <div
                ref={ref}
                className={clsx('overflow-hidden transition-all duration-300 ease-out', className)}
                style={{ height }}
                aria-hidden={!isOpen}
                {...props}
            >
                <div ref={contentRef}>{children}</div>
            </div>
        )
    }
)

CollapsibleContent.displayName = 'CollapsibleContent'

// ============================================================================
// EXPANDABLE CARD
// ============================================================================

export interface ExpandableCardProps extends HTMLAttributes<HTMLDivElement> {
    /** Header content */
    header: ReactNode
    /** Preview content shown when collapsed */
    preview?: ReactNode
    /** Default expanded state */
    defaultExpanded?: boolean
    /** Controlled expanded state */
    expanded?: boolean
    /** Expansion change handler */
    onExpandedChange?: (expanded: boolean) => void
    children: ReactNode
}

export const ExpandableCard = forwardRef<HTMLDivElement, ExpandableCardProps>(
    (
        {
            className,
            header,
            preview,
            defaultExpanded = false,
            expanded: controlledExpanded,
            onExpandedChange,
            children,
            ...props
        },
        ref
    ) => {
        const [internalExpanded, setInternalExpanded] = useState(defaultExpanded)
        const isExpanded = controlledExpanded ?? internalExpanded
        const contentRef = useRef<HTMLDivElement>(null)
        const [height, setHeight] = useState(0)

        const toggle = () => {
            const newState = !isExpanded
            setInternalExpanded(newState)
            onExpandedChange?.(newState)
        }

        useEffect(() => {
            if (contentRef.current) {
                setHeight(isExpanded ? contentRef.current.scrollHeight : 0)
            }
        }, [isExpanded, children])

        return (
            <div
                ref={ref}
                className={clsx(
                    'rounded-xl border border-white/10/50 bg-dark-400/50 backdrop-blur-sm overflow-hidden',
                    className
                )}
                {...props}
            >
                <button
                    type="button"
                    className="w-full flex items-center justify-between gap-4 p-4 text-left hover:bg-dark-300/20 transition-colors"
                    onClick={toggle}
                    aria-expanded={isExpanded}
                >
                    <div className="flex-1">
                        <div className="font-medium text-white">{header}</div>
                        {!isExpanded && preview && (
                            <div className="mt-1 text-sm text-gray-400 line-clamp-2">{preview}</div>
                        )}
                    </div>
                    <svg
                        className={clsx(
                            'w-5 h-5 text-gray-400 transition-transform duration-300 flex-shrink-0',
                            isExpanded && 'rotate-180'
                        )}
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                    >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                </button>

                <div
                    className="overflow-hidden transition-all duration-300 ease-out"
                    style={{ height }}
                    aria-hidden={!isExpanded}
                >
                    <div ref={contentRef} className="px-4 pb-4 border-t border-white/10/50">
                        <div className="pt-4">{children}</div>
                    </div>
                </div>
            </div>
        )
    }
)

ExpandableCard.displayName = 'ExpandableCard'
