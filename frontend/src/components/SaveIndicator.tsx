/**
 * Save indicator component for osu!-style auto-save feedback.
 * 
 * Shows:
 * - Loading spinner while saving
 * - "Saved" text after successful save
 * - Error message with retry option on failure
 */

import { motion, AnimatePresence } from 'framer-motion'
import type { SaveState } from '@/hooks/useAutoSave'

interface SaveIndicatorProps {
    /** Current save state */
    state: SaveState
    /** Error message to display */
    error?: string | null
    /** Callback when retry is clicked */
    onRetry?: () => void
    /** Size variant */
    size?: 'sm' | 'md'
    /** Custom class name */
    className?: string
}

/**
 * Inline save indicator that shows saving/saved/error states.
 * Matches osu!'s aesthetic with smooth animations.
 */
export function SaveIndicator({
    state,
    error,
    onRetry,
    size = 'sm',
    className = '',
}: SaveIndicatorProps) {
    const textSize = size === 'sm' ? 'text-xs' : 'text-sm'
    const spinnerSize = size === 'sm' ? 'w-3 h-3' : 'w-4 h-4'

    return (
        <AnimatePresence mode="wait">
            {state === 'saving' && (
                <motion.span
                    key="saving"
                    initial={{ opacity: 0, x: -5 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 5 }}
                    transition={{ duration: 0.15 }}
                    className={`inline-flex items-center gap-1.5 text-gray-400 ${textSize} ${className}`}
                >
                    <svg
                        className={`${spinnerSize} animate-spin`}
                        viewBox="0 0 24 24"
                        fill="none"
                    >
                        <circle
                            className="opacity-25"
                            cx="12"
                            cy="12"
                            r="10"
                            stroke="currentColor"
                            strokeWidth="3"
                        />
                        <path
                            className="opacity-75"
                            fill="currentColor"
                            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                        />
                    </svg>
                </motion.span>
            )}

            {state === 'saved' && (
                <motion.span
                    key="saved"
                    initial={{ opacity: 0, x: -5 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 5 }}
                    transition={{ duration: 0.15 }}
                    className={`inline-flex items-center gap-1 text-green-400 font-medium ${textSize} ${className}`}
                >
                    Saved
                </motion.span>
            )}

            {state === 'error' && (
                <motion.span
                    key="error"
                    initial={{ opacity: 0, x: -5 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 5 }}
                    transition={{ duration: 0.15 }}
                    className={`inline-flex items-center gap-1.5 text-red-400 ${textSize} ${className}`}
                >
                    <svg className={spinnerSize} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                        />
                    </svg>
                    <span>{error || 'Failed to save'}</span>
                    {onRetry && (
                        <button
                            onClick={onRetry}
                            className="underline hover:text-red-300 transition-colors"
                        >
                            Retry
                        </button>
                    )}
                </motion.span>
            )}
        </AnimatePresence>
    )
}

/**
 * Auto-save input wrapper that shows save indicator inline.
 * Use this to wrap individual input fields.
 */
interface AutoSaveFieldProps {
    children: React.ReactNode
    state: SaveState
    error?: string | null
    onRetry?: () => void
    /** Show indicator on the right side (default) or left */
    indicatorPosition?: 'left' | 'right'
    className?: string
}

export function AutoSaveField({
    children,
    state,
    error,
    onRetry,
    indicatorPosition = 'right',
    className = '',
}: AutoSaveFieldProps) {
    const indicator = (
        <SaveIndicator
            state={state}
            error={error}
            onRetry={onRetry}
            size="sm"
        />
    )

    return (
        <div className={`flex items-center gap-2 ${className}`}>
            {indicatorPosition === 'left' && indicator}
            <div className="flex-1">{children}</div>
            {indicatorPosition === 'right' && indicator}
        </div>
    )
}

/**
 * Toggle with built-in save indicator.
 * For checkbox/switch style settings that auto-save.
 */
interface AutoSaveToggleProps {
    checked: boolean
    onChange: (checked: boolean) => void
    state: SaveState
    label: string
    description?: string
    disabled?: boolean
    className?: string
}

export function AutoSaveToggle({
    checked,
    onChange,
    state,
    label,
    description,
    disabled = false,
    className = '',
}: AutoSaveToggleProps) {
    return (
        <label className={`flex items-center justify-between cursor-pointer ${disabled ? 'opacity-50 cursor-not-allowed' : ''} ${className}`}>
            <div className="flex-1">
                <span className="text-white">{label}</span>
                {description && (
                    <p className="text-sm text-gray-500">{description}</p>
                )}
            </div>
            <div className="flex items-center gap-3">
                <SaveIndicator state={state} size="sm" />
                <input
                    type="checkbox"
                    checked={checked}
                    onChange={(e) => onChange(e.target.checked)}
                    disabled={disabled}
                    className="w-5 h-5 rounded bg-dark-300 border-gray-600 text-primary-500 focus:ring-primary-500"
                />
            </div>
        </label>
    )
}

export default SaveIndicator
