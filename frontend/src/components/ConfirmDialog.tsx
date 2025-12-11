/**
 * ConfirmDialog - A reusable confirmation dialog component
 * Used for sign-out confirmation, destructive actions, etc.
 * 
 * Styled similar to osu!'s confirmation popups with clean overlay design
 * 
 * NOTE: This component avoids AnimatePresence + createPortal combination
 * which causes "removeChild" errors during navigation unmounts.
 * Uses CSS transitions via tailwindcss-animate for animations instead.
 */

import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
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
            dialogRef.current?.focus()
        }

        return () => {
            document.removeEventListener('keydown', handleKeyDown)
        }
    }, [isOpen, onClose])

    // Prevent body scroll when dialog is open
    useEffect(() => {
        if (isOpen) {
            lockBodyScroll()
            return () => {
                unlockBodyScroll()
            }
        }
    }, [isOpen])

    // Safety: ensure body scroll is unlocked when component unmounts
    useEffect(() => {
        return () => {
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
                    confirmButton: 'bg-primary-500 hover:bg-primary-400 focus:ring-primary-500/50 shadow-lg shadow-primary-500/25',
                    cancelButton: 'bg-dark-300 hover:bg-dark-300/80 text-gray-200 border border-white/10 hover:border-white/20',
                    icon: null,
                }
            default:
                return {
                    confirmButton: 'bg-primary-500 hover:bg-primary-600 focus:ring-primary-500/50',
                    icon: (
                        <svg className="w-6 h-6 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                    ),
                }
        }
    }

    const styles = getVariantStyles()

    // Don't render anything if not open (avoids animation issues during navigation)
    if (!isOpen) {
        return null
    }

    // osu-style popup for signout variant
    if (style === 'popup' || variant === 'signout') {
        const dialogContent = (
            <div
                className="fixed inset-0 z-[9999] flex items-center justify-center animate-in fade-in duration-200"
                onClick={onClose}
            >
                {/* Full-screen backdrop */}
                <div className="absolute inset-0 bg-black/80 backdrop-blur-md" />

                {/* Dialog Card */}
                <div
                    ref={dialogRef}
                    onClick={(e) => e.stopPropagation()}
                    tabIndex={-1}
                    className="relative bg-dark-400 rounded-2xl border border-white/10 shadow-2xl shadow-black/60 max-w-md w-full mx-4 overflow-hidden focus:outline-none animate-in zoom-in-95 slide-in-from-bottom-4 duration-300"
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="dialog-title"
                >
                    {/* Decorative top accent line */}
                    <div className="absolute top-0 left-0 right-0 h-1 bg-primary-500" />

                    {/* Content */}
                    <div className="relative px-8 pt-10 pb-8 text-center">
                        {/* Icon */}
                        <div className="mx-auto w-16 h-16 rounded-full bg-primary-500/15 border border-primary-500/30 flex items-center justify-center mb-5">
                            <svg className="w-8 h-8 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                            </svg>
                        </div>

                        {/* Title */}
                        <h2
                            id="dialog-title"
                            className="text-2xl font-bold text-white mb-3"
                        >
                            {title}
                        </h2>

                        {/* Message */}
                        <p className="text-gray-400 text-base mb-8 leading-relaxed">
                            {message}
                        </p>

                        {/* Buttons */}
                        <div className="flex gap-4 justify-center">
                            <button
                                onClick={onClose}
                                disabled={isLoading}
                                className={`px-8 py-3 text-sm font-semibold rounded-xl transition-all duration-200
                                         focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-dark-500
                                         disabled:opacity-50 min-w-[140px] hover:scale-105 active:scale-95
                                         ${styles.cancelButton || 'bg-dark-300 hover:bg-dark-300/80 text-gray-200 border border-white/10 hover:border-white/20 focus:ring-gray-500/50'}`}
                            >
                                {cancelLabel}
                            </button>
                            <button
                                onClick={onConfirm}
                                disabled={isLoading}
                                className={`px-8 py-3 text-sm font-semibold text-white rounded-xl transition-all duration-200
                                          focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-dark-500
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
                        </div>
                    </div>
                </div>
            </div>
        )

        return createPortal(dialogContent, document.body)
    }

    // Standard modal dialog (for non-signout variants)
    const modalContent = (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-in fade-in duration-200"
            onClick={onClose}
        >
            {/* Backdrop */}
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

            {/* Dialog */}
            <div
                ref={dialogRef}
                onClick={(e) => e.stopPropagation()}
                tabIndex={-1}
                className="relative bg-dark-400 rounded-2xl border border-white/10 shadow-2xl shadow-black/50 max-w-sm w-full overflow-hidden focus:outline-none animate-in zoom-in-95 slide-in-from-bottom-4 duration-300"
                role="dialog"
                aria-modal="true"
                aria-labelledby="dialog-title"
            >
                {/* Header */}
                <div className="px-6 py-5 border-b border-white/10">
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

                {/* Body */}
                <div className="px-6 py-4">
                    <p className="text-gray-400 text-sm leading-relaxed">
                        {message}
                    </p>
                </div>

                {/* Footer */}
                <div className="px-6 py-4 bg-dark-500/50 border-t border-white/5 flex justify-end gap-3">
                    <button
                        onClick={onClose}
                        disabled={isLoading}
                        className="px-4 py-2 text-sm font-medium text-gray-300 rounded-lg
                                 bg-dark-300 border border-white/10 
                                 hover:bg-dark-200 hover:border-white/20
                                 focus:outline-none focus:ring-2 focus:ring-gray-500/50
                                 disabled:opacity-50 transition-all duration-200"
                    >
                        {cancelLabel}
                    </button>
                    <button
                        onClick={onConfirm}
                        disabled={isLoading}
                        className={`px-4 py-2 text-sm font-medium text-white rounded-lg
                                  focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-dark-500
                                  disabled:opacity-50 transition-all duration-200
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
            </div>
        </div>
    )

    return createPortal(modalContent, document.body)
}

export default ConfirmDialog
