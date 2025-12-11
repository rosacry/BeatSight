/**
 * Achievement notification toast component.
 * Shows a celebratory toast when achievements are unlocked.
 */

import { useState, useEffect, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '@/lib/utils'

export interface AchievementNotification {
    id: string
    name: string
    description: string
    icon: string
    points: number
    category: string
}

// Map achievement icon names to SVG paths (same as AchievementBadge)
const ICON_PATHS: Record<string, string> = {
    trophy: 'M8.21 14.77L7 14.5V14L6 13V12L7 12.5V11L9 10.5L10.5 10V9L10 7L11 6L12 7L13 6L14 7L13.5 9L13.5 10L15 10.5L17 11V12.5L18 12V13L17 14V14.5L15.79 14.77L14 17H10L8.21 14.77Z',
    music: 'M12 3V13.55C11.41 13.21 10.73 13 10 13C7.79 13 6 14.79 6 17S7.79 21 10 21 14 19.21 14 17V7H18V3H12Z',
    collection: 'M4 6H2V20C2 21.1 2.9 22 4 22H18V20H4V6ZM20 2H8C6.9 2 6 2.9 6 4V16C6 17.1 6.9 18 8 18H20C21.1 18 22 17.1 22 16V4C22 2.9 21.1 2 20 2ZM14 14L11 10.5L8 14H20L16 8L14 11L12 9L14 14Z',
    star: 'M12 17.27L18.18 21L16.54 13.97L22 9.24L14.81 8.63L12 2L9.19 8.63L2 9.24L7.46 13.97L5.82 21L12 17.27Z',
    crown: 'M5 16L3 5L8.5 10L12 4L15.5 10L21 5L19 16H5ZM19 19C19 19.55 18.55 20 18 20H6C5.45 20 5 19.55 5 19V18H19V19Z',
    'graduation-cap': 'M12 3L1 9L12 15L21 10.09V17H23V9M5 13.18V17.18L12 21L19 17.18V13.18L12 17L5 13.18Z',
    clock: 'M12 2C6.5 2 2 6.5 2 12S6.5 22 12 22 22 17.5 22 12 17.5 2 12 2ZM12.5 13H11V7H12.5V11.26L16.2 13.27L15.45 14.54L12.5 13Z',
    fire: 'M17.66 11.2C17.43 10.9 17.15 10.64 16.89 10.38C16.22 9.78 15.46 9.35 14.82 8.72C13.33 7.26 13 4.85 13.95 3C13 3.23 12.17 3.75 11.46 4.32C8.87 6.4 7.85 10.07 9.07 13.22C9.11 13.32 9.15 13.42 9.15 13.55C9.15 13.77 9 13.97 8.8 14.05C8.57 14.15 8.33 14.09 8.14 13.93C8.08 13.88 8.04 13.83 8 13.76C6.87 12.33 6.69 10.28 7.45 8.64C5.78 10 4.87 12.3 5 14.47C5.06 14.97 5.12 15.47 5.29 15.97C5.43 16.57 5.7 17.17 6 17.7C7.08 19.43 8.95 20.67 10.96 20.92C13.1 21.19 15.39 20.8 17.03 19.32C18.86 17.66 19.5 15 18.56 12.72L18.43 12.46C18.22 12 17.66 11.2 17.66 11.2Z',
    pencil: 'M20.71 7.04C21.1 6.65 21.1 6 20.71 5.63L18.37 3.29C18 2.9 17.35 2.9 16.96 3.29L15.12 5.12L18.87 8.87M3 17.25V21H6.75L17.81 9.93L14.06 6.18L3 17.25Z',
    'check-circle': 'M12 2C6.5 2 2 6.5 2 12S6.5 22 12 22 22 17.5 22 12 17.5 2 12 2ZM10 17L5 12L6.41 10.59L10 14.17L17.59 6.58L19 8L10 17Z',
    'arrow-up': 'M13 20H11V8L5.5 13.5L4.08 12.08L12 4.16L19.92 12.08L18.5 13.5L13 8V20Z',
    rocket: 'M12 2.5C8.69 2.5 6 5.19 6 8.5C6 12.5 12 19.5 12 19.5S18 12.5 18 8.5C18 5.19 15.31 2.5 12 2.5ZM12 11C10.62 11 9.5 9.88 9.5 8.5S10.62 6 12 6 14.5 7.12 14.5 8.5 13.38 11 12 11ZM5 20.5C5 22.16 8.13 23.5 12 23.5S19 22.16 19 20.5C19 19.5 17.89 18.62 16.13 18.12L15.21 19.04C16.35 19.28 17 19.63 17 20C17 20.78 14.76 21.5 12 21.5S7 20.78 7 20C7 19.63 7.65 19.28 8.79 19.04L7.87 18.12C6.11 18.62 5 19.5 5 20.5Z',
}

// Category colors for border effects
const CATEGORY_COLORS: Record<string, string> = {
    generation: 'from-blue-500 to-blue-600',
    learning: 'from-green-500 to-green-600',
    contribution: 'from-purple-500 to-purple-600',
    social: 'from-yellow-500 to-yellow-600',
    special: 'from-pink-500 to-pink-600',
    milestone: 'from-purple-500 to-purple-600',
    skill: 'from-blue-500 to-blue-600',
    dedication: 'from-orange-500 to-orange-600',
}

interface AchievementToastProps {
    achievement: AchievementNotification
    onDismiss: () => void
}

export function AchievementToast({ achievement, onDismiss }: AchievementToastProps) {
    const [isVisible, setIsVisible] = useState(false)
    const [isLeaving, setIsLeaving] = useState(false)

    const handleDismiss = useCallback(() => {
        setIsLeaving(true)
        setTimeout(onDismiss, 300) // Wait for exit animation
    }, [onDismiss])

    useEffect(() => {
        // Trigger enter animation
        requestAnimationFrame(() => setIsVisible(true))

        // Auto-dismiss after 5 seconds
        const timer = setTimeout(() => {
            handleDismiss()
        }, 5000)

        return () => clearTimeout(timer)
    }, [handleDismiss])

    const iconPath = ICON_PATHS[achievement.icon] || ICON_PATHS.trophy
    const gradientColor = CATEGORY_COLORS[achievement.category] || CATEGORY_COLORS.generation

    return (
        <div
            className={cn(
                'relative overflow-hidden rounded-xl shadow-2xl transition-all duration-300 ease-out',
                'bg-dark-500 border border-white/10',
                'w-80 cursor-pointer',
                isVisible && !isLeaving ? 'translate-x-0 opacity-100' : 'translate-x-full opacity-0'
            )}
            onClick={handleDismiss}
        >
            {/* Gradient top border */}
            <div className={cn('h-1 bg-gradient-to-r', gradientColor)} />

            {/* Content */}
            <div className="p-4">
                {/* Header with confetti effect */}
                <div className="flex items-center gap-2 mb-3">
                    <span className="text-xl">🎉</span>
                    <span className="text-xs font-semibold uppercase tracking-wider text-yellow-400">
                        Achievement Unlocked!
                    </span>
                </div>

                <div className="flex items-start gap-4">
                    {/* Icon with glow effect */}
                    <div className="relative">
                        <div className={cn(
                            'absolute inset-0 rounded-full blur-md opacity-50 bg-gradient-to-r',
                            gradientColor
                        )} />
                        <div className={cn(
                            'relative flex items-center justify-center w-14 h-14 rounded-full',
                            'bg-gradient-to-r',
                            gradientColor
                        )}>
                            <svg
                                viewBox="0 0 24 24"
                                className="w-7 h-7 text-white"
                                fill="currentColor"
                            >
                                <path d={iconPath} />
                            </svg>
                        </div>
                    </div>

                    {/* Text content */}
                    <div className="flex-1 min-w-0">
                        <h3 className="font-bold text-white truncate">
                            {achievement.name}
                        </h3>
                        <p className="text-sm text-gray-400 line-clamp-2 mt-1">
                            {achievement.description}
                        </p>
                        <div className="flex items-center gap-1 mt-2">
                            <span className="text-yellow-400">⭐</span>
                            <span className="text-sm font-medium text-yellow-400">
                                +{achievement.points} points
                            </span>
                        </div>
                    </div>
                </div>
            </div>

            {/* Progress bar for auto-dismiss */}
            <div className="h-1 bg-dark-400">
                <div
                    className={cn('h-full bg-gradient-to-r transition-all ease-linear', gradientColor)}
                    style={{
                        width: isVisible && !isLeaving ? '0%' : '100%',
                        transitionDuration: isVisible && !isLeaving ? '5000ms' : '0ms',
                    }}
                />
            </div>
        </div>
    )
}

// Global notification queue
let notificationQueue: AchievementNotification[] = []
let setNotificationsCallback: React.Dispatch<React.SetStateAction<AchievementNotification[]>> | null = null

/**
 * Show an achievement unlock notification toast.
 * Can be called from anywhere in the app.
 */
export function showAchievementToast(achievement: AchievementNotification) {
    if (setNotificationsCallback) {
        setNotificationsCallback(prev => [...prev, achievement])
    } else {
        // Queue notifications if provider not mounted yet
        notificationQueue.push(achievement)
    }
}

/**
 * Achievement notification provider component.
 * Renders notification toasts in a portal.
 */
export function AchievementNotificationProvider({ children }: { children: React.ReactNode }) {
    const [notifications, setNotifications] = useState<AchievementNotification[]>([])

    // Register the callback on mount
    useEffect(() => {
        setNotificationsCallback = setNotifications

        // Process any queued notifications
        if (notificationQueue.length > 0) {
            setNotifications(prev => [...prev, ...notificationQueue])
            notificationQueue = []
        }

        return () => {
            setNotificationsCallback = null
        }
    }, [])

    const dismissNotification = useCallback((id: string) => {
        setNotifications(prev => prev.filter(n => n.id !== id))
    }, [])

    return (
        <>
            {children}
            {typeof document !== 'undefined' && createPortal(
                <div className="fixed top-4 right-4 z-50 space-y-3">
                    {notifications.map(achievement => (
                        <AchievementToast
                            key={achievement.id}
                            achievement={achievement}
                            onDismiss={() => dismissNotification(achievement.id)}
                        />
                    ))}
                </div>,
                document.body
            )}
        </>
    )
}
