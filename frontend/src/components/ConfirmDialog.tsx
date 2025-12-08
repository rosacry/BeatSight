/**
 * ConfirmDialog - A reusable confirmation dialog component
 * Used for sign-out confirmation, destructive actions, etc.
 * 
 * Similar to osu!'s confirmation popups
 */

import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

interface ConfirmDialogProps {
    isOpen: boolean
    onClose: () => void
    onConfirm: () => void
    title: string
    message: string
    confirmLabel?: string
    cancelLabel?: string
    variant?: 'default' | 'danger' | 'warning'
    isLoading?: boolean
}

const overlayVariants = {
    hidden: { opacity: 0 },
    visible: { opacity: 1 },
}

const dialogVariants = {
    hidden: { opacity: 0, scale: 0.95, y: 10 },
    visible: {
        opacity: 1,
        scale: 1,
        y: 0,
        transition: { type: 'spring', duration: 0.3, bounce: 0.2 }
    },
    exit: {
        opacity: 0,
        scale: 0.95,
        y: 10,
        transition: { duration: 0.15 }
    },
}

export function ConfirmDialog({
    isOpen,
    onClose,
    onConfirm,
    title,
    message,
    confirmLabel = 'Confirm',
    cancelLabel = 'Cancel',
    variant = 'default',
    isLoading = false,
}: ConfirmDialogProps) {
    const dialogRef = useRef<HTMLDivElement>(null)

    // Handle escape key
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape' && isOpen) {
                onClose()
            }
        }

        if (isOpen) {
            document.addEventListener('keydown', handleKeyDown)
            // Focus the dialog when opened
            dialogRef.current?.focus()
        }

        return () => {
            document.removeEventListener('keydown', handleKeyDown)
        }
    }, [isOpen, onClose])

    // Prevent body scroll when dialog is open
    useEffect(() => {
        if (isOpen) {
            document.body.style.overflow = 'hidden'
        } else {
            document.body.style.overflow = ''
        }

        return () => {
            document.body.style.overflow = ''
        }
    }, [isOpen])

    const getVariantStyles = () => {
        switch (variant) {
            case 'danger':
                return {
                    confirmButton: 'bg-red-500 hover:bg-red-600 focus:ring-red-500/50',
                    icon: (
                        <svg className="w-6 h-6 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                    ),
                }
            case 'warning':
                return {
                    confirmButton: 'bg-amber-500 hover:bg-amber-600 focus:ring-amber-500/50',
                    icon: (
                        <svg className="w-6 h-6 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                    ),
                }
            default:
                return {
                    confirmButton: 'bg-cyan-500 hover:bg-cyan-600 focus:ring-cyan-500/50',
                    icon: (
                        <svg className="w-6 h-6 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                    ),
                }
        }
    }

    const styles = getVariantStyles()

    return (
        <AnimatePresence>
            {isOpen && (
                <motion.div
                    initial="hidden"
                    animate="visible"
                    exit="hidden"
                    variants={overlayVariants}
                    className="fixed inset-0 z-50 flex items-center justify-center p-4"
                    onClick={onClose}
                >
                    {/* Backdrop */}
                    <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

                    {/* Dialog */}
                    <motion.div
                        ref={dialogRef}
                        variants={dialogVariants}
                        initial="hidden"
                        animate="visible"
                        exit="exit"
                        onClick={(e) => e.stopPropagation()}
                        tabIndex={-1}
                        className="relative bg-gray-800 rounded-2xl border border-gray-700 shadow-2xl shadow-black/50 max-w-sm w-full overflow-hidden focus:outline-none"
                        role="dialog"
                        aria-modal="true"
                        aria-labelledby="dialog-title"
                    >
                        {/* Header */}
                        <div className="px-6 py-5 border-b border-gray-700">
                            <div className="flex items-center gap-3">
                                <div className="flex-shrink-0">
                                    {styles.icon}
                                </div>
                                <h2 id="dialog-title" className="text-lg font-semibold text-white">
                                    {title}
                                </h2>
                            </div>
                        </div>

                        {/* Content */}
                        <div className="px-6 py-4">
                            <p className="text-gray-300">{message}</p>
                        </div>

                        {/* Actions */}
                        <div className="px-6 py-4 bg-gray-900/50 flex gap-3 justify-end">
                            <button
                                onClick={onClose}
                                disabled={isLoading}
                                className="px-4 py-2 text-sm font-medium text-gray-300 hover:text-white 
                                         bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors
                                         focus:outline-none focus:ring-2 focus:ring-gray-500/50
                                         disabled:opacity-50"
                            >
                                {cancelLabel}
                            </button>
                            <button
                                onClick={onConfirm}
                                disabled={isLoading}
                                className={`px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors
                                          focus:outline-none focus:ring-2 disabled:opacity-50
                                          ${styles.confirmButton}`}
                            >
                                {isLoading ? (
                                    <span className="flex items-center gap-2">
                                        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                        </svg>
                                        Processing...
                                    </span>
                                ) : (
                                    confirmLabel
                                )}
                            </button>
                        </div>
                    </motion.div>
                </motion.div>
            )}
        </AnimatePresence>
    )
}

/**
 * Hook for easily managing confirm dialog state
 */
export function useConfirmDialog() {
    const [isOpen, setIsOpen] = useState(false)
    const [config, setConfig] = useState<Omit<ConfirmDialogProps, 'isOpen' | 'onClose' | 'onConfirm'>>({
        title: '',
        message: '',
    })
    const resolveRef = useRef<((value: boolean) => void) | null>(null)

    const confirm = (options: Omit<ConfirmDialogProps, 'isOpen' | 'onClose' | 'onConfirm'>): Promise<boolean> => {
        setConfig(options)
        setIsOpen(true)

        return new Promise((resolve) => {
            resolveRef.current = resolve
        })
    }

    const handleClose = () => {
        setIsOpen(false)
        resolveRef.current?.(false)
    }

    const handleConfirm = () => {
        setIsOpen(false)
        resolveRef.current?.(true)
    }

    const Dialog = () => (
        <ConfirmDialog
            isOpen={isOpen}
            onClose={handleClose}
            onConfirm={handleConfirm}
            {...config}
        />
    )

    return { confirm, Dialog }
}