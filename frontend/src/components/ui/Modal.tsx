/**
 * Modal/Dialog component with animations and accessibility.
 */

import {
    forwardRef,
    type ReactNode,
    type HTMLAttributes,
    useEffect,
    useCallback,
    useRef,
} from 'react'
import { createPortal } from 'react-dom'
import { cva, type VariantProps } from 'class-variance-authority'
import { clsx } from 'clsx'

const modalVariants = cva(
    // Base styles
    [
        'relative bg-gray-800 rounded-xl shadow-2xl',
        'border border-gray-700/50',
        'transform transition-all duration-300',
    ],
    {
        variants: {
            size: {
                sm: 'max-w-sm w-full',
                md: 'max-w-md w-full',
                lg: 'max-w-lg w-full',
                xl: 'max-w-xl w-full',
                '2xl': 'max-w-2xl w-full',
                full: 'max-w-[90vw] w-full max-h-[90vh]',
            },
        },
        defaultVariants: {
            size: 'md',
        },
    }
)

export interface ModalProps extends VariantProps<typeof modalVariants> {
    /** Whether the modal is open */
    open: boolean
    /** Callback when modal should close */
    onClose: () => void
    /** Modal content */
    children: ReactNode
    /** Close on backdrop click */
    closeOnBackdrop?: boolean
    /** Close on Escape key */
    closeOnEscape?: boolean
    /** Show close button */
    showCloseButton?: boolean
    /** Additional class name */
    className?: string
    /** Center content vertically */
    centered?: boolean
}

export function Modal({
    open,
    onClose,
    children,
    size,
    closeOnBackdrop = true,
    closeOnEscape = true,
    showCloseButton = true,
    className,
    centered = true,
}: ModalProps) {
    const modalRef = useRef<HTMLDivElement>(null)

    // Handle escape key
    const handleKeyDown = useCallback(
        (e: KeyboardEvent) => {
            if (e.key === 'Escape' && closeOnEscape) {
                onClose()
            }
        },
        [closeOnEscape, onClose]
    )

    // Handle backdrop click
    const handleBackdropClick = useCallback(
        (e: React.MouseEvent) => {
            if (e.target === e.currentTarget && closeOnBackdrop) {
                onClose()
            }
        },
        [closeOnBackdrop, onClose]
    )

    // Lock body scroll and add event listeners
    useEffect(() => {
        if (open) {
            document.body.style.overflow = 'hidden'
            document.addEventListener('keydown', handleKeyDown)

            // Focus trap - focus first focusable element
            const focusableElements = modalRef.current?.querySelectorAll(
                'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
            )
            const firstFocusable = focusableElements?.[0] as HTMLElement
            firstFocusable?.focus()

            return () => {
                document.body.style.overflow = ''
                document.removeEventListener('keydown', handleKeyDown)
            }
        }
    }, [open, handleKeyDown])

    if (!open) return null

    return createPortal(
        <div
            className={clsx(
                'fixed inset-0 z-50 overflow-y-auto',
                'flex min-h-full p-4',
                centered ? 'items-center justify-center' : 'items-start justify-center pt-20'
            )}
            role="dialog"
            aria-modal="true"
        >
            {/* Backdrop */}
            <div
                className="fixed inset-0 bg-black/70 backdrop-blur-sm transition-opacity animate-[fade-in_0.2s_ease-out]"
                onClick={handleBackdropClick}
                aria-hidden="true"
            />

            {/* Modal */}
            <div
                ref={modalRef}
                className={clsx(
                    modalVariants({ size }),
                    'animate-[fade-in-scale_0.3s_ease-out]',
                    className
                )}
            >
                {/* Close button */}
                {showCloseButton && (
                    <button
                        type="button"
                        onClick={onClose}
                        className={clsx(
                            'absolute top-4 right-4 z-10',
                            'p-2 rounded-lg',
                            'text-gray-400 hover:text-white',
                            'hover:bg-gray-700/50 transition-colors'
                        )}
                        aria-label="Close modal"
                    >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M6 18L18 6M6 6l12 12"
                            />
                        </svg>
                    </button>
                )}

                {children}
            </div>
        </div>,
        document.body
    )
}

/**
 * Modal Header component
 */
interface ModalHeaderProps extends HTMLAttributes<HTMLDivElement> {
    title: string
    description?: string
    icon?: ReactNode
}

export const ModalHeader = forwardRef<HTMLDivElement, ModalHeaderProps>(
    ({ className, title, description, icon, ...props }, ref) => {
        return (
            <div
                ref={ref}
                className={clsx('px-6 pt-6 pb-4', className)}
                {...props}
            >
                <div className="flex items-start gap-4">
                    {icon && (
                        <div className="shrink-0 p-2 rounded-lg bg-primary-500/10 text-primary-400">
                            {icon}
                        </div>
                    )}
                    <div>
                        <h2 className="text-lg font-semibold text-white">{title}</h2>
                        {description && (
                            <p className="mt-1 text-sm text-gray-400">{description}</p>
                        )}
                    </div>
                </div>
            </div>
        )
    }
)

ModalHeader.displayName = 'ModalHeader'

/**
 * Modal Body component
 */
export const ModalBody = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
    ({ className, ...props }, ref) => {
        return (
            <div
                ref={ref}
                className={clsx('px-6 py-4', className)}
                {...props}
            />
        )
    }
)

ModalBody.displayName = 'ModalBody'

/**
 * Modal Footer component
 */
export const ModalFooter = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
    ({ className, ...props }, ref) => {
        return (
            <div
                ref={ref}
                className={clsx(
                    'px-6 py-4 border-t border-gray-700/50',
                    'flex items-center justify-end gap-3',
                    className
                )}
                {...props}
            />
        )
    }
)

ModalFooter.displayName = 'ModalFooter'

/**
 * Confirmation Dialog - specialized modal for confirmations
 */
interface ConfirmDialogProps {
    open: boolean
    onClose: () => void
    onConfirm: () => void
    title: string
    message: string
    confirmText?: string
    cancelText?: string
    variant?: 'danger' | 'warning' | 'default'
    loading?: boolean
}

export function ConfirmDialog({
    open,
    onClose,
    onConfirm,
    title,
    message,
    confirmText = 'Confirm',
    cancelText = 'Cancel',
    variant = 'default',
    loading = false,
}: ConfirmDialogProps) {
    const variantStyles = {
        danger: {
            icon: (
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                    />
                </svg>
            ),
            iconBg: 'bg-red-500/10 text-red-400',
            confirmBtn: 'bg-red-600 hover:bg-red-500 text-white',
        },
        warning: {
            icon: (
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                    />
                </svg>
            ),
            iconBg: 'bg-yellow-500/10 text-yellow-400',
            confirmBtn: 'bg-yellow-600 hover:bg-yellow-500 text-white',
        },
        default: {
            icon: (
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                </svg>
            ),
            iconBg: 'bg-primary-500/10 text-primary-400',
            confirmBtn: 'bg-primary-600 hover:bg-primary-500 text-white',
        },
    }

    const styles = variantStyles[variant]

    return (
        <Modal open={open} onClose={onClose} size="sm" showCloseButton={false}>
            <div className="p-6 text-center">
                <div className={clsx('mx-auto w-12 h-12 rounded-full flex items-center justify-center mb-4', styles.iconBg)}>
                    {styles.icon}
                </div>

                <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
                <p className="text-gray-400 text-sm mb-6">{message}</p>

                <div className="flex gap-3 justify-center">
                    <button
                        type="button"
                        onClick={onClose}
                        disabled={loading}
                        className="px-4 py-2 text-sm font-medium text-gray-300 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors disabled:opacity-50"
                    >
                        {cancelText}
                    </button>
                    <button
                        type="button"
                        onClick={onConfirm}
                        disabled={loading}
                        className={clsx(
                            'px-4 py-2 text-sm font-medium rounded-lg transition-colors disabled:opacity-50',
                            styles.confirmBtn
                        )}
                    >
                        {loading ? (
                            <span className="flex items-center gap-2">
                                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                                    <circle
                                        className="opacity-25"
                                        cx="12"
                                        cy="12"
                                        r="10"
                                        stroke="currentColor"
                                        strokeWidth="4"
                                        fill="none"
                                    />
                                    <path
                                        className="opacity-75"
                                        fill="currentColor"
                                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                                    />
                                </svg>
                                Processing...
                            </span>
                        ) : (
                            confirmText
                        )}
                    </button>
                </div>
            </div>
        </Modal>
    )
}

export { modalVariants }
