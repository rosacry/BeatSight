/**
 * BeatSight Advanced Modal Components
 * 
 * Additional modal variants that complement the base Modal:
 * - Sheet (slide-out panel)
 * - Command Palette
 * - Drawer (mobile-friendly)
 * - Fullscreen Overlay
 */

import React, {
    useState,
    useEffect,
    useCallback,
    useRef,
    type ReactNode,
} from 'react'
import { createPortal } from 'react-dom'
import { clsx } from 'clsx'
import { cva, type VariantProps } from 'class-variance-authority'
import {
    useFocusTrap,
    useKeyboardShortcut,
    announce,
    ARIA_LABELS,
} from '@/lib/accessibility'
import { usePrefersReducedMotion } from '@/lib/animations'

// ============================================================================
// TYPES
// ============================================================================

export type SheetSide = 'top' | 'right' | 'bottom' | 'left'
export type SheetSize = 'sm' | 'md' | 'lg' | 'full'

// ============================================================================
// OVERLAY STYLES
// ============================================================================

const overlayStyles = cva(
    'fixed inset-0 z-50 bg-black/60 backdrop-blur-sm',
    {
        variants: {
            animation: {
                fade: 'data-[state=open]:animate-[fade-in_200ms_ease-out] data-[state=closed]:animate-[fade-out_150ms_ease-in]',
                none: '',
            },
        },
        defaultVariants: {
            animation: 'fade',
        },
    }
)

// ============================================================================
// SHEET STYLES
// ============================================================================

const sheetStyles = cva(
    'fixed z-50 bg-gray-800 border-gray-700/50 shadow-2xl outline-none overflow-auto',
    {
        variants: {
            side: {
                top: 'inset-x-0 top-0 border-b rounded-b-xl data-[state=open]:animate-[slide-in-down_300ms_ease-out] data-[state=closed]:animate-[slide-out-up_200ms_ease-in]',
                right: 'inset-y-0 right-0 border-l rounded-l-xl h-full data-[state=open]:animate-[slide-in-right_300ms_ease-out] data-[state=closed]:animate-[slide-out-right_200ms_ease-in]',
                bottom: 'inset-x-0 bottom-0 border-t rounded-t-xl data-[state=open]:animate-[slide-in-up_300ms_ease-out] data-[state=closed]:animate-[slide-out-down_200ms_ease-in]',
                left: 'inset-y-0 left-0 border-r rounded-r-xl h-full data-[state=open]:animate-[slide-in-left_300ms_ease-out] data-[state=closed]:animate-[slide-out-left_200ms_ease-in]',
            },
            size: {
                sm: '',
                md: '',
                lg: '',
                full: '',
            },
        },
        compoundVariants: [
            { side: 'left', size: 'sm', className: 'w-64' },
            { side: 'left', size: 'md', className: 'w-80' },
            { side: 'left', size: 'lg', className: 'w-96' },
            { side: 'left', size: 'full', className: 'w-screen' },
            { side: 'right', size: 'sm', className: 'w-64' },
            { side: 'right', size: 'md', className: 'w-80' },
            { side: 'right', size: 'lg', className: 'w-96' },
            { side: 'right', size: 'full', className: 'w-screen' },
            { side: 'top', size: 'sm', className: 'max-h-40' },
            { side: 'top', size: 'md', className: 'max-h-60' },
            { side: 'top', size: 'lg', className: 'max-h-80' },
            { side: 'top', size: 'full', className: 'h-screen' },
            { side: 'bottom', size: 'sm', className: 'max-h-40' },
            { side: 'bottom', size: 'md', className: 'max-h-60' },
            { side: 'bottom', size: 'lg', className: 'max-h-80' },
            { side: 'bottom', size: 'full', className: 'h-screen' },
        ],
        defaultVariants: {
            side: 'right',
            size: 'md',
        },
    }
)

// ============================================================================
// SHEET (SLIDE-OUT PANEL)
// ============================================================================

export interface SheetProps extends VariantProps<typeof sheetStyles> {
    children: ReactNode
    isOpen: boolean
    onClose: () => void
    title?: string
    description?: string
    showCloseButton?: boolean
    className?: string
}

export function Sheet({
    children,
    isOpen,
    onClose,
    side = 'right',
    size = 'md',
    title,
    description,
    showCloseButton = true,
    className,
}: SheetProps) {
    const focusTrapRef = useFocusTrap(isOpen, { returnFocus: true })
    const prefersReducedMotion = usePrefersReducedMotion()
    const titleId = React.useId()
    const descriptionId = React.useId()

    useKeyboardShortcut('Escape', onClose, { enabled: isOpen })

    // Prevent body scroll
    useEffect(() => {
        if (isOpen) {
            const originalOverflow = document.body.style.overflow
            document.body.style.overflow = 'hidden'
            return () => {
                document.body.style.overflow = originalOverflow
            }
        }
    }, [isOpen])

    if (!isOpen) return null

    return createPortal(
        <>
            <div
                className={overlayStyles({ animation: prefersReducedMotion ? 'none' : 'fade' })}
                data-state={isOpen ? 'open' : 'closed'}
                onClick={onClose}
                aria-hidden="true"
            />
            <div
                ref={focusTrapRef}
                role="dialog"
                aria-modal="true"
                aria-labelledby={title ? titleId : undefined}
                aria-describedby={description ? descriptionId : undefined}
                data-state={isOpen ? 'open' : 'closed'}
                className={clsx(
                    sheetStyles({ side, size }),
                    prefersReducedMotion && 'animate-none',
                    className
                )}
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                {(title || showCloseButton) && (
                    <div className="flex items-center justify-between p-4 border-b border-gray-700/50">
                        <div>
                            {title && (
                                <h2 id={titleId} className="text-lg font-semibold text-white">
                                    {title}
                                </h2>
                            )}
                            {description && (
                                <p id={descriptionId} className="text-sm text-gray-400 mt-1">
                                    {description}
                                </p>
                            )}
                        </div>
                        {showCloseButton && (
                            <button
                                onClick={onClose}
                                className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-700/50 transition-colors"
                                aria-label={ARIA_LABELS.CLOSE}
                            >
                                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                                    <path d="M18 6L6 18M6 6l12 12" />
                                </svg>
                            </button>
                        )}
                    </div>
                )}

                {/* Content */}
                <div className="p-4">
                    {children}
                </div>
            </div>
        </>,
        document.body
    )
}

// ============================================================================
// COMMAND PALETTE
// ============================================================================

export interface CommandItem {
    id: string
    label: string
    description?: string
    icon?: ReactNode
    shortcut?: string
    onSelect: () => void
    disabled?: boolean
    group?: string
}

export interface CommandPaletteProps {
    isOpen: boolean
    onClose: () => void
    items: CommandItem[]
    placeholder?: string
    emptyMessage?: string
    className?: string
}

export function CommandPalette({
    isOpen,
    onClose,
    items,
    placeholder = 'Type a command or search...',
    emptyMessage = 'No results found.',
    className,
}: CommandPaletteProps) {
    const [query, setQuery] = useState('')
    const [selectedIndex, setSelectedIndex] = useState(0)
    const focusTrapRef = useFocusTrap(isOpen, { returnFocus: true })
    const inputRef = useRef<HTMLInputElement>(null)
    const prefersReducedMotion = usePrefersReducedMotion()

    // Filter items based on query
    const filteredItems = items.filter(
        (item) =>
            item.label.toLowerCase().includes(query.toLowerCase()) ||
            item.description?.toLowerCase().includes(query.toLowerCase())
    )

    // Group items
    const groupedItems = filteredItems.reduce<Record<string, CommandItem[]>>((acc, item) => {
        const group = item.group || 'Other'
        if (!acc[group]) acc[group] = []
        acc[group].push(item)
        return acc
    }, {})

    // Reset selection when query changes
    useEffect(() => {
        setSelectedIndex(0)
    }, [query])

    // Reset when closed
    useEffect(() => {
        if (!isOpen) {
            setQuery('')
            setSelectedIndex(0)
        } else {
            // Focus input when opened
            setTimeout(() => inputRef.current?.focus(), 0)
        }
    }, [isOpen])

    // Keyboard navigation
    const handleKeyDown = (e: React.KeyboardEvent) => {
        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault()
                setSelectedIndex((prev) => Math.min(prev + 1, filteredItems.length - 1))
                break
            case 'ArrowUp':
                e.preventDefault()
                setSelectedIndex((prev) => Math.max(prev - 1, 0))
                break
            case 'Enter': {
                e.preventDefault()
                const selected = filteredItems[selectedIndex]
                if (selected && !selected.disabled) {
                    selected.onSelect()
                    onClose()
                }
                break
            }
            case 'Escape':
                e.preventDefault()
                onClose()
                break
        }
    }

    // Announce results to screen readers
    useEffect(() => {
        if (isOpen && query) {
            announce(`${filteredItems.length} results found`)
        }
    }, [filteredItems.length, isOpen, query])

    useKeyboardShortcut('Escape', onClose, { enabled: isOpen })

    if (!isOpen) return null

    return createPortal(
        <>
            <div
                className={overlayStyles({ animation: prefersReducedMotion ? 'none' : 'fade' })}
                data-state="open"
                onClick={onClose}
                aria-hidden="true"
            />
            <div
                ref={focusTrapRef}
                role="dialog"
                aria-modal="true"
                aria-label="Command palette"
                data-state="open"
                className={clsx(
                    'fixed left-1/2 top-[15%] -translate-x-1/2 z-50',
                    'w-full max-w-xl bg-gray-800 border border-gray-700/50 rounded-xl shadow-2xl overflow-hidden',
                    !prefersReducedMotion && 'animate-[fade-in-scale_200ms_ease-out]',
                    className
                )}
                onKeyDown={handleKeyDown}
            >
                {/* Search input */}
                <div className="flex items-center gap-3 p-4 border-b border-gray-700/50">
                    <svg className="w-5 h-5 text-gray-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                        <circle cx="11" cy="11" r="8" />
                        <path d="M21 21l-4.35-4.35" />
                    </svg>
                    <input
                        ref={inputRef}
                        type="text"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder={placeholder}
                        className="flex-1 bg-transparent text-white placeholder:text-gray-500 outline-none"
                        autoFocus
                    />
                    <kbd className="px-2 py-1 text-xs text-gray-400 bg-gray-700/50 rounded">ESC</kbd>
                </div>

                {/* Results */}
                <div className="max-h-80 overflow-auto p-2">
                    {filteredItems.length === 0 ? (
                        <div className="px-4 py-8 text-center text-gray-400">
                            {emptyMessage}
                        </div>
                    ) : (
                        Object.entries(groupedItems).map(([group, groupItems]) => (
                            <div key={group} className="mb-2">
                                <div className="px-3 py-1.5 text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    {group}
                                </div>
                                {groupItems.map((item) => {
                                    const globalIndex = filteredItems.indexOf(item)
                                    const isSelected = globalIndex === selectedIndex

                                    return (
                                        <button
                                            key={item.id}
                                            onClick={() => {
                                                if (!item.disabled) {
                                                    item.onSelect()
                                                    onClose()
                                                }
                                            }}
                                            disabled={item.disabled}
                                            className={clsx(
                                                'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-colors',
                                                isSelected
                                                    ? 'bg-primary-500/20 text-white'
                                                    : 'text-gray-300 hover:bg-gray-700/50',
                                                item.disabled && 'opacity-50 cursor-not-allowed'
                                            )}
                                        >
                                            {item.icon && (
                                                <span className="flex-shrink-0 w-5 h-5 text-gray-400">
                                                    {item.icon}
                                                </span>
                                            )}
                                            <div className="flex-1 min-w-0">
                                                <div className="font-medium truncate">{item.label}</div>
                                                {item.description && (
                                                    <div className="text-sm text-gray-500 truncate">
                                                        {item.description}
                                                    </div>
                                                )}
                                            </div>
                                            {item.shortcut && (
                                                <kbd className="flex-shrink-0 px-2 py-1 text-xs text-gray-400 bg-gray-700/50 rounded">
                                                    {item.shortcut}
                                                </kbd>
                                            )}
                                        </button>
                                    )
                                })}
                            </div>
                        ))
                    )}
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between px-4 py-2 border-t border-gray-700/50 text-xs text-gray-500">
                    <div className="flex items-center gap-2">
                        <span className="flex items-center gap-1">
                            <kbd className="px-1.5 py-0.5 bg-gray-700/50 rounded">↑</kbd>
                            <kbd className="px-1.5 py-0.5 bg-gray-700/50 rounded">↓</kbd>
                            navigate
                        </span>
                        <span className="flex items-center gap-1">
                            <kbd className="px-1.5 py-0.5 bg-gray-700/50 rounded">↵</kbd>
                            select
                        </span>
                    </div>
                    <span className="flex items-center gap-1">
                        <kbd className="px-1.5 py-0.5 bg-gray-700/50 rounded">esc</kbd>
                        close
                    </span>
                </div>
            </div>
        </>,
        document.body
    )
}

// ============================================================================
// DRAWER (MOBILE-FRIENDLY BOTTOM SHEET)
// ============================================================================

export interface DrawerProps {
    children: ReactNode
    isOpen: boolean
    onClose: () => void
    title?: string
    description?: string
    showHandle?: boolean
    className?: string
}

export function Drawer({
    children,
    isOpen,
    onClose,
    title,
    description,
    showHandle = true,
    className,
}: DrawerProps) {
    const focusTrapRef = useFocusTrap(isOpen, { returnFocus: true })
    const prefersReducedMotion = usePrefersReducedMotion()
    const titleId = React.useId()

    useKeyboardShortcut('Escape', onClose, { enabled: isOpen })

    // Prevent body scroll
    useEffect(() => {
        if (isOpen) {
            const originalOverflow = document.body.style.overflow
            document.body.style.overflow = 'hidden'
            return () => {
                document.body.style.overflow = originalOverflow
            }
        }
    }, [isOpen])

    if (!isOpen) return null

    return createPortal(
        <>
            <div
                className={overlayStyles({ animation: prefersReducedMotion ? 'none' : 'fade' })}
                data-state="open"
                onClick={onClose}
                aria-hidden="true"
            />
            <div
                ref={focusTrapRef}
                role="dialog"
                aria-modal="true"
                aria-labelledby={title ? titleId : undefined}
                data-state="open"
                className={clsx(
                    'fixed inset-x-0 bottom-0 z-50 bg-gray-800 border-t border-gray-700/50 rounded-t-2xl max-h-[85vh] overflow-auto',
                    !prefersReducedMotion && 'animate-[slide-in-up_300ms_ease-out]',
                    className
                )}
            >
                {/* Drag handle */}
                {showHandle && (
                    <div className="flex justify-center py-3">
                        <div className="w-10 h-1 bg-gray-600 rounded-full" />
                    </div>
                )}

                {/* Header */}
                {title && (
                    <div className="flex items-center justify-between px-4 pb-3 border-b border-gray-700/50">
                        <div>
                            <h2 id={titleId} className="text-lg font-semibold text-white">
                                {title}
                            </h2>
                            {description && (
                                <p className="text-sm text-gray-400 mt-0.5">{description}</p>
                            )}
                        </div>
                        <button
                            onClick={onClose}
                            className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-700/50 transition-colors"
                            aria-label={ARIA_LABELS.CLOSE}
                        >
                            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                                <path d="M18 6L6 18M6 6l12 12" />
                            </svg>
                        </button>
                    </div>
                )}

                {/* Content */}
                <div className="p-4">
                    {children}
                </div>
            </div>
        </>,
        document.body
    )
}

// ============================================================================
// FULLSCREEN OVERLAY
// ============================================================================

export interface FullscreenOverlayProps {
    children: ReactNode
    isOpen: boolean
    onClose: () => void
    showCloseButton?: boolean
    className?: string
}

export function FullscreenOverlay({
    children,
    isOpen,
    onClose,
    showCloseButton = true,
    className,
}: FullscreenOverlayProps) {
    const focusTrapRef = useFocusTrap(isOpen, { returnFocus: true })
    const prefersReducedMotion = usePrefersReducedMotion()

    useKeyboardShortcut('Escape', onClose, { enabled: isOpen })

    // Prevent body scroll
    useEffect(() => {
        if (isOpen) {
            const originalOverflow = document.body.style.overflow
            document.body.style.overflow = 'hidden'
            return () => {
                document.body.style.overflow = originalOverflow
            }
        }
    }, [isOpen])

    if (!isOpen) return null

    return createPortal(
        <div
            ref={focusTrapRef}
            role="dialog"
            aria-modal="true"
            className={clsx(
                'fixed inset-0 z-50 bg-gray-900',
                !prefersReducedMotion && 'animate-[fade-in_200ms_ease-out]',
                className
            )}
        >
            {/* Close button */}
            {showCloseButton && (
                <button
                    onClick={onClose}
                    className="absolute top-4 right-4 z-10 p-3 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
                    aria-label={ARIA_LABELS.CLOSE}
                >
                    <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                        <path d="M18 6L6 18M6 6l12 12" />
                    </svg>
                </button>
            )}
            {children}
        </div>,
        document.body
    )
}

// ============================================================================
// HOOKS
// ============================================================================

/**
 * Hook for controlling modal state
 */
export function useModalState(initialState = false) {
    const [isOpen, setIsOpen] = useState(initialState)

    const open = useCallback(() => setIsOpen(true), [])
    const close = useCallback(() => setIsOpen(false), [])
    const toggle = useCallback(() => setIsOpen((prev) => !prev), [])

    return { isOpen, open, close, toggle, setIsOpen }
}

/**
 * Hook for command palette with keyboard shortcut
 */
export function useCommandPalette(shortcut = 'k', ctrl = true) {
    const { isOpen, open, close } = useModalState(false)

    useKeyboardShortcut(shortcut, open, { ctrl, enabled: !isOpen })

    return { isOpen, open, close }
}

/**
 * Hook for confirm dialogs
 */
export function useConfirmDialog() {
    const [state, setState] = useState<{
        isOpen: boolean
        title: string
        message: string
        variant?: 'danger' | 'warning' | 'default'
        resolve?: (confirmed: boolean) => void
    }>({
        isOpen: false,
        title: '',
        message: '',
    })

    const confirm = useCallback(
        (options: {
            title: string
            message: string
            variant?: 'danger' | 'warning' | 'default'
        }): Promise<boolean> => {
            return new Promise((resolve) => {
                setState({
                    isOpen: true,
                    title: options.title,
                    message: options.message,
                    variant: options.variant,
                    resolve,
                })
            })
        },
        []
    )

    const handleConfirm = useCallback(() => {
        state.resolve?.(true)
        setState((prev) => ({ ...prev, isOpen: false }))
    }, [state])

    const handleClose = useCallback(() => {
        state.resolve?.(false)
        setState((prev) => ({ ...prev, isOpen: false }))
    }, [state])

    return {
        isOpen: state.isOpen,
        title: state.title,
        message: state.message,
        variant: state.variant,
        onConfirm: handleConfirm,
        onClose: handleClose,
        confirm,
    }
}
