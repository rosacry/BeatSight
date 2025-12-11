/**
 * ConfirmDialog - A reusable confirmation dialog component
 * Used for sign-out confirmation, destructive actions, etc.
 * 
 * Styled similar to osu!'s confirmation popups with clean overlay design
 */

import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { lockBodyScroll, unlockBodyScroll } from '@/lib/bodyScrollLock'

interface ConfirmDialogProps {
    isOpen: boolean
    onClose: () => void
    onConfirm: () => void
    title: string
    message: string
    confirmLabel?: string
    cancelLabel?: string
    variant?: 'default' | 'danger' | 'warning' | 'signout'
    isLoading?: boolean
    /** Show as a centered popup overlay (osu-style) vs modal dialog */
    style?: 'modal' | 'popup'
}

const overlayVariants = {
    hidden: { opacity: 0 },
    visible: {
        opacity: 1,
        transition: { duration: 0.2, ease: 'easeOut' }
    },
}

const dialogVariants = {
    hidden: {
        opacity: 0,
        scale: 0.96,
        y: -20
    },
    visible: {
        opacity: 1,
        scale: 1,
        y: 0,
        transition: {
            type: 'spring',
            duration: 0.4,
            bounce: 0.15,
            delay: 0.05
        }
    },
    exit: {
        opacity: 0,
        scale: 0.96,
        y: -10,
        transition: {
            duration: 0.2,
            ease: [0.4, 0, 1, 1]
        }
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
    style = 'modal',
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
    // Use a more robust cleanup that ensures unlock happens even during navigation
    useEffect(() => {
        if (isOpen) {
            lockBodyScroll()
            return () => {
                // Always unlock on cleanup, regardless of current state
                unlockBodyScroll()
            }
        }
    }, [isOpen])

    // Additional safety: ensure body scroll is unlocked when component unmounts
    // This catches cases where isOpen changes during unmount
    useEffect(() => {
        return () => {
            // Force cleanup on unmount to prevent stuck states during navigation
            unlockBodyScroll()
        }
    }, [])

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
            case 'signout':
                return {
                    confirmButton: 'bg-gradient-to-r from-cyan-500 to-teal-500 hover:from-cyan-400 hover:to-teal-400 focus:ring-cyan-500/50 shadow-lg shadow-cyan-500/25',
                    cancelButton: 'bg-slate-700/60 hover:bg-slate-600/60 text-slate-200 border border-slate-600/50 hover:border-slate-500/50',
                    icon: null, // No icon for osu-style signout popup
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

    // osu-style popup for signout variant - rendered via portal for proper centering
    // Note: Using mode="sync" instead of "wait" to prevent animation interruption during navigation
    if (style === 'popup' || variant === 'signout') {
        const dialogContent = (
            <AnimatePresence mode="sync">
                {isOpen && (
                    <motion.div
                        key="popup-overlay"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.25 }}
                        className="fixed inset-0 z-[9999] flex items-center justify-center"
                        onClick={onClose}
                        style={{
                            position: 'fixed',
                            top: 0,
                            left: 0,
                            right: 0,
                            bottom: 0,
                        }}
                    >
                        {/* Full-screen backdrop with blur and dark overlay */}
                        <motion.div
                            className="absolute inset-0 bg-black/80 backdrop-blur-md"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            transition={{ duration: 0.3 }}
                        />

                        {/* Subtle animated gradient overlay for depth */}
                        <motion.div
                            className="absolute inset-0 bg-gradient-to-br from-cyan-900/15 via-transparent to-slate-900/20 pointer-events-none"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            transition={{ duration: 0.4 }}
                        />

                        {/* Dialog Card - Centered */}
                        <motion.div
                            ref={dialogRef}
                            initial={{ opacity: 0, scale: 0.85, y: 30 }}
                            animate={{
                                opacity: 1,
                                scale: 1,
                                y: 0,
                                transition: {
                                    type: 'spring',
                                    duration: 0.5,
                                    bounce: 0.25
                                }
                            }}
                            exit={{
                                opacity: 0,
                                scale: 0.9,
                                y: 20,
                                transition: { duration: 0.2, ease: 'easeIn' }
                            }}
                            onClick={(e) => e.stopPropagation()}
                            tabIndex={-1}
                            className="relative bg-gradient-to-b from-slate-800/95 to-slate-900/95 rounded-3xl border border-white/10 shadow-2xl shadow-black/60 max-w-md w-full mx-4 overflow-hidden focus:outline-none backdrop-blur-xl"
                            role="dialog"
                            aria-modal="true"
                            aria-labelledby="dialog-title"
                        >
                            {/* Decorative top gradient line */}
                            <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-cyan-400 via-cyan-500 to-teal-500" />

                            {/* Subtle glow effect */}
                            <div className="absolute -top-20 left-1/2 -translate-x-1/2 w-64 h-32 bg-cyan-500/15 rounded-full blur-3xl pointer-events-none" />

                            {/* Content */}
                            <div className="relative px-8 pt-10 pb-8 text-center">
                                {/* Icon with animated ring */}
                                <motion.div
                                    className="mx-auto w-16 h-16 rounded-full bg-gradient-to-br from-cyan-500/20 to-teal-500/20 border border-cyan-500/40 flex items-center justify-center mb-5 relative"
                                    initial={{ scale: 0.8 }}
                                    animate={{ scale: 1 }}
                                    transition={{ delay: 0.1, type: 'spring', bounce: 0.4 }}
                                >
                                    {/* Animated ring */}
                                    <motion.div
                                        className="absolute inset-0 rounded-full border-2 border-cyan-400/30"
                                        initial={{ scale: 1, opacity: 0.5 }}
                                        animate={{
                                            scale: [1, 1.3, 1.3],
                                            opacity: [0.5, 0, 0]
                                        }}
                                        transition={{
                                            duration: 2,
                                            repeat: Infinity,
                                            ease: 'easeOut'
                                        }}
                                    />
                                    <svg className="w-8 h-8 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                                    </svg>
                                </motion.div>

                                {/* Title */}
                                <motion.h2
                                    id="dialog-title"
                                    className="text-2xl font-bold text-white mb-3"
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: 0.15 }}
                                >
                                    {title}
                                </motion.h2>

                                {/* Message */}
                                <motion.p
                                    className="text-slate-400 text-base mb-8 leading-relaxed"
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: 0.2 }}
                                >
                                    {message}
                                </motion.p>

                                {/* Buttons */}
                                <motion.div
                                    className="flex gap-4 justify-center"
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: 0.25 }}
                                >
                                    <button
                                        onClick={onClose}
                                        disabled={isLoading}
                                        className={`px-8 py-3 text-sm font-semibold rounded-xl transition-all duration-200
                                                 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-slate-900
                                                 disabled:opacity-50 min-w-[140px] hover:scale-105 active:scale-95
                                                 ${styles.cancelButton || 'bg-slate-700/60 hover:bg-slate-600/60 text-slate-200 border border-slate-600/50 hover:border-slate-500/50 focus:ring-slate-500/50'}`}
                                    >
                                        {cancelLabel}
                                    </button>
                                    <button
                                        onClick={onConfirm}
                                        disabled={isLoading}
                                        className={`px-8 py-3 text-sm font-semibold text-white rounded-xl transition-all duration-200
                                                  focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-slate-900
                                                  disabled:opacity-50 min-w-[140px] hover:scale-105 active:scale-95
                                                  ${styles.confirmButton}`}
                                    >
                                        {isLoading ? (
                                            <span className="flex items-center justify-center gap-2">
                                                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                                </svg>
                                            </span>
                                        ) : (
                                            confirmLabel
                                        )}
                                    </button>
                                </motion.div>
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
        )

        // Use portal to render at document root, escaping any parent positioning
        return createPortal(dialogContent, document.body)
    }

    // Standard modal dialog
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
                                {styles.icon && (
                                    <div className="flex-shrink-0">
                                        {styles.icon}
                                    </div>
                                )}
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