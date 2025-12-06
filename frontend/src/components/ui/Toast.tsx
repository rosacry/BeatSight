/**
 * Toast Notifications - Beautiful toast system powered by Sonner
 * 
 * Usage:
 *   import { toast, Toaster } from '@/components/ui/Toast'
 *   
 *   // In your app root:
 *   <Toaster />
 *   
 *   // Anywhere in your app:
 *   toast.success('Profile updated!')
 *   toast.error('Something went wrong')
 *   toast.promise(saveData(), {
 *     loading: 'Saving...',
 *     success: 'Saved!',
 *     error: 'Failed to save'
 *   })
 */

import { Toaster as SonnerToaster, toast as sonnerToast } from 'sonner'
import React from 'react'

// ============================================================================
// Toaster Provider Component
// ============================================================================

interface ToasterProps {
    position?: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right' | 'top-center' | 'bottom-center'
    expand?: boolean
    richColors?: boolean
    closeButton?: boolean
    duration?: number
}

export function Toaster({
    position = 'bottom-right',
    expand = false,
    richColors = true,
    closeButton = true,
    duration = 4000,
}: ToasterProps) {
    return (
        <SonnerToaster
            position={position}
            expand={expand}
            richColors={richColors}
            closeButton={closeButton}
            duration={duration}
            toastOptions={{
                style: {
                    background: 'rgba(17, 24, 39, 0.95)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    color: '#fff',
                    backdropFilter: 'blur(12px)',
                },
                className: 'beatsight-toast',
                descriptionClassName: 'text-gray-400',
            }}
            theme="dark"
        />
    )
}

// ============================================================================
// Custom Toast Functions with BeatSight Styling
// ============================================================================

interface ToastOptions {
    description?: string
    duration?: number
    action?: {
        label: string
        onClick: () => void
    }
    id?: string | number
    dismissible?: boolean
    onDismiss?: () => void
    onAutoClose?: () => void
}

interface PromiseOptions<T> {
    loading: string
    success: string | ((data: T) => string)
    error: string | ((error: Error) => string)
    description?: string
}

const baseStyle = {
    background: 'rgba(17, 24, 39, 0.95)',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    color: '#fff',
}

// Extended toast object with custom methods
export const toast = {
    // Basic toasts
    show: (message: string, options?: ToastOptions) => {
        return sonnerToast(message, {
            description: options?.description,
            duration: options?.duration,
            id: options?.id,
            dismissible: options?.dismissible,
            onDismiss: options?.onDismiss,
            onAutoClose: options?.onAutoClose,
            action: options?.action ? {
                label: options.action.label,
                onClick: options.action.onClick,
            } : undefined,
        })
    },

    success: (message: string, options?: ToastOptions) => {
        return sonnerToast.success(message, {
            description: options?.description,
            duration: options?.duration,
            id: options?.id,
            style: {
                ...baseStyle,
                border: '1px solid rgba(34, 197, 94, 0.3)',
            },
        })
    },

    error: (message: string, options?: ToastOptions) => {
        return sonnerToast.error(message, {
            description: options?.description,
            duration: options?.duration ?? 6000, // Errors stay longer
            id: options?.id,
            style: {
                ...baseStyle,
                border: '1px solid rgba(239, 68, 68, 0.3)',
            },
        })
    },

    warning: (message: string, options?: ToastOptions) => {
        return sonnerToast.warning(message, {
            description: options?.description,
            duration: options?.duration,
            id: options?.id,
            style: {
                ...baseStyle,
                border: '1px solid rgba(245, 158, 11, 0.3)',
            },
        })
    },

    info: (message: string, options?: ToastOptions) => {
        return sonnerToast.info(message, {
            description: options?.description,
            duration: options?.duration,
            id: options?.id,
            style: {
                ...baseStyle,
                border: '1px solid rgba(0, 212, 255, 0.3)',
            },
        })
    },

    // Promise toast - great for async operations
    promise: <T,>(promise: Promise<T>, options: PromiseOptions<T>) => {
        return sonnerToast.promise(promise, options)
    },

    // Loading toast
    loading: (message: string, options?: ToastOptions) => {
        return sonnerToast.loading(message, {
            description: options?.description,
            duration: options?.duration,
            id: options?.id,
        })
    },

    // Custom toast with JSX
    custom: (content: React.ReactElement, options?: ToastOptions) => {
        return sonnerToast.custom(() => content, {
            duration: options?.duration,
            id: options?.id,
        })
    },

    // Dismiss toasts
    dismiss: (toastId?: string | number) => {
        return sonnerToast.dismiss(toastId)
    },

    // BeatSight-specific toasts
    creditsPurchased: (amount: number) => {
        return sonnerToast.success(`${amount} credits purchased!`, {
            description: 'Your credits have been added to your account.',
            style: {
                background: 'linear-gradient(135deg, rgba(17, 24, 39, 0.95) 0%, rgba(6, 78, 59, 0.3) 100%)',
                border: '1px solid rgba(34, 197, 94, 0.4)',
            },
        })
    },

    transcriptionStarted: (songName: string) => {
        return sonnerToast.loading(`Transcribing "${songName}"...`, {
            description: 'This may take a few minutes.',
            duration: Infinity,
        })
    },

    transcriptionComplete: (songName: string, toastId?: string | number) => {
        if (toastId) sonnerToast.dismiss(toastId)
        return sonnerToast.success(`"${songName}" transcribed!`, {
            description: 'Your beatmap is ready to play.',
            action: {
                label: 'View Map',
                onClick: () => {
                    // Navigate to map - implement based on your routing
                },
            },
        })
    },

    mapUploaded: (mapName: string) => {
        return sonnerToast.success(`"${mapName}" uploaded!`, {
            description: 'Your beatmap is now live.',
            style: {
                background: 'linear-gradient(135deg, rgba(17, 24, 39, 0.95) 0%, rgba(0, 212, 255, 0.1) 100%)',
                border: '1px solid rgba(0, 212, 255, 0.3)',
            },
        })
    },

    achievementUnlocked: (achievementName: string, description?: string) => {
        return sonnerToast.custom(() => (
            <div className="flex items-center gap-3 p-1">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-yellow-400 to-orange-500">
                    <span className="text-xl">🏆</span>
                </div>
                <div>
                    <div className="font-semibold text-white">Achievement Unlocked!</div>
                    <div className="text-sm text-yellow-400">{achievementName}</div>
                    {description && (
                        <div className="text-xs text-gray-400">{description}</div>
                    )}
                </div>
            </div>
        ), {
            duration: 6000,
            style: {
                background: 'linear-gradient(135deg, rgba(17, 24, 39, 0.95) 0%, rgba(245, 158, 11, 0.2) 100%)',
                border: '1px solid rgba(245, 158, 11, 0.4)',
            },
        })
    },

    levelUp: (newLevel: number) => {
        return sonnerToast.custom(() => (
            <div className="flex items-center gap-3 p-1">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-cyan-400 to-magenta-500">
                    <span className="text-xl">⬆️</span>
                </div>
                <div>
                    <div className="font-semibold text-white">Level Up!</div>
                    <div className="text-lg font-bold bg-gradient-to-r from-cyan-400 to-magenta-400 bg-clip-text text-transparent">
                        Level {newLevel}
                    </div>
                </div>
            </div>
        ), {
            duration: 6000,
            style: {
                background: 'linear-gradient(135deg, rgba(17, 24, 39, 0.95) 0%, rgba(0, 212, 255, 0.2) 100%)',
                border: '1px solid rgba(0, 212, 255, 0.4)',
            },
        })
    },

    connectionLost: () => {
        return sonnerToast.error('Connection Lost', {
            description: 'Attempting to reconnect...',
            duration: Infinity,
            id: 'connection-lost',
        })
    },

    connectionRestored: () => {
        sonnerToast.dismiss('connection-lost')
        return sonnerToast.success('Connection Restored', {
            description: 'You\'re back online!',
        })
    },
}

// ============================================================================
// Toast CSS (add to your global styles)
// ============================================================================

export const toastStyles = `
/* Sonner toast customizations */
[data-sonner-toaster] {
    font-family: inherit;
}

[data-sonner-toast] {
    --toast-bg: rgba(17, 24, 39, 0.95);
    --toast-border: rgba(255, 255, 255, 0.1);
    --toast-color: #fff;
}

[data-sonner-toast][data-type="success"] {
    --toast-border: rgba(34, 197, 94, 0.3);
}

[data-sonner-toast][data-type="error"] {
    --toast-border: rgba(239, 68, 68, 0.3);
}

[data-sonner-toast][data-type="warning"] {
    --toast-border: rgba(245, 158, 11, 0.3);
}

[data-sonner-toast][data-type="info"] {
    --toast-border: rgba(0, 212, 255, 0.3);
}

/* Toast action button */
[data-sonner-toast] [data-button] {
    background: rgba(0, 212, 255, 0.2);
    color: #00d4ff;
    border: 1px solid rgba(0, 212, 255, 0.3);
    font-weight: 500;
}

[data-sonner-toast] [data-button]:hover {
    background: rgba(0, 212, 255, 0.3);
}

/* Toast close button */
[data-sonner-toast] [data-close-button] {
    background: rgba(255, 255, 255, 0.1);
    border-color: rgba(255, 255, 255, 0.2);
    color: #9ca3af;
}

[data-sonner-toast] [data-close-button]:hover {
    background: rgba(255, 255, 255, 0.2);
    color: #fff;
}
`
