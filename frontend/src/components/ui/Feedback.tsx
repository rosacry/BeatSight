/**
 * Feedback Components
 * Tooltips, badges, toasts, and notification components.
 */

import {
    forwardRef,
    useState,
    useCallback,
    createContext,
    useContext,
    type HTMLAttributes,
    type ReactNode,
} from 'react'
import { cn } from '../../lib/utils'

// ============================================================================
// TOOLTIP
// ============================================================================

export interface TooltipProps {
    content: ReactNode
    children: ReactNode
    side?: 'top' | 'bottom' | 'left' | 'right'
    delay?: number
    className?: string
}

export function Tooltip({ content, children, side = 'top', delay = 300, className }: TooltipProps) {
    const [isVisible, setIsVisible] = useState(false)
    const [timeoutId, setTimeoutId] = useState<ReturnType<typeof setTimeout> | null>(null)

    const showTooltip = useCallback(() => {
        const id = setTimeout(() => setIsVisible(true), delay)
        setTimeoutId(id)
    }, [delay])

    const hideTooltip = useCallback(() => {
        if (timeoutId) {
            clearTimeout(timeoutId)
            setTimeoutId(null)
        }
        setIsVisible(false)
    }, [timeoutId])

    const sideStyles = {
        top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
        bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
        left: 'right-full top-1/2 -translate-y-1/2 mr-2',
        right: 'left-full top-1/2 -translate-y-1/2 ml-2',
    }

    const arrowStyles = {
        top: 'top-full left-1/2 -translate-x-1/2 border-t-dark-400 border-x-transparent border-b-transparent',
        bottom: 'bottom-full left-1/2 -translate-x-1/2 border-b-dark-400 border-x-transparent border-t-transparent',
        left: 'left-full top-1/2 -translate-y-1/2 border-l-dark-400 border-y-transparent border-r-transparent',
        right: 'right-full top-1/2 -translate-y-1/2 border-r-dark-400 border-y-transparent border-l-transparent',
    }

    return (
        <div className="relative inline-block" onMouseEnter={showTooltip} onMouseLeave={hideTooltip}>
            {children}
            {isVisible && (
                <div
                    className={cn(
                        'absolute z-50 px-2 py-1 text-xs text-gray-200 bg-dark-400 rounded-md shadow-lg whitespace-nowrap',
                        'animate-in fade-in-0 zoom-in-95 duration-150',
                        sideStyles[side],
                        className
                    )}
                >
                    {content}
                    <span
                        className={cn('absolute w-0 h-0 border-4', arrowStyles[side])}
                    />
                </div>
            )}
        </div>
    )
}

// ============================================================================
// BADGE
// ============================================================================

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
    variant?: 'default' | 'secondary' | 'success' | 'warning' | 'danger' | 'info' | 'premium'
    size?: 'sm' | 'md' | 'lg'
    dot?: boolean
    pulse?: boolean
}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
    ({ variant = 'default', size = 'md', dot, pulse, className, children, ...props }, ref) => {
        const variants = {
            default: 'bg-dark-300 text-gray-200',
            secondary: 'bg-dark-400 text-gray-300',
            success: 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30',
            warning: 'bg-amber-500/20 text-amber-400 border border-amber-500/30',
            danger: 'bg-red-500/20 text-red-400 border border-red-500/30',
            info: 'bg-primary-500/20 text-primary-400 border border-primary-500/30',
            premium: 'bg-amber-500/20 text-amber-400 border border-amber-500/30',
        }

        const sizes = {
            sm: 'px-1.5 py-0.5 text-[10px]',
            md: 'px-2 py-0.5 text-xs',
            lg: 'px-2.5 py-1 text-sm',
        }

        return (
            <span
                ref={ref}
                className={cn(
                    'inline-flex items-center gap-1 font-medium rounded-full',
                    variants[variant],
                    sizes[size],
                    className
                )}
                {...props}
            >
                {dot && (
                    <span className={cn('w-1.5 h-1.5 rounded-full bg-current', pulse && 'animate-pulse')} />
                )}
                {children}
            </span>
        )
    }
)
Badge.displayName = 'Badge'

// ============================================================================
// NOTIFICATION DOT
// ============================================================================

export interface NotificationDotProps {
    count?: number
    max?: number
    showZero?: boolean
    className?: string
}

export function NotificationDot({ count, max = 99, showZero = false, className }: NotificationDotProps) {
    if (!showZero && (!count || count === 0)) return null

    const displayCount = count && count > max ? `${max}+` : count

    return (
        <span
            className={cn(
                'absolute -top-1 -right-1 flex items-center justify-center min-w-[18px] h-[18px] px-1',
                'bg-red-500 text-white text-[10px] font-bold rounded-full',
                'animate-in zoom-in-50 duration-200',
                className
            )}
        >
            {displayCount}
        </span>
    )
}

// ============================================================================
// TOAST SYSTEM
// ============================================================================

type ToastVariant = 'default' | 'success' | 'error' | 'warning' | 'info'

interface Toast {
    id: string
    message: string
    variant: ToastVariant
    duration?: number
    action?: {
        label: string
        onClick: () => void
    }
}

interface ToastContextValue {
    toasts: Toast[]
    addToast: (message: string, variant?: ToastVariant, duration?: number, action?: Toast['action']) => void
    removeToast: (id: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function useToast() {
    const context = useContext(ToastContext)
    if (!context) {
        throw new Error('useToast must be used within a ToastProvider')
    }
    return context
}

export interface ToastProviderProps {
    children: ReactNode
    position?: 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left' | 'top-center' | 'bottom-center'
}

export function ToastProvider({ children, position = 'bottom-right' }: ToastProviderProps) {
    const [toasts, setToasts] = useState<Toast[]>([])

    const addToast = useCallback(
        (message: string, variant: ToastVariant = 'default', duration = 5000, action?: Toast['action']) => {
            const id = Math.random().toString(36).substring(2)
            const toast: Toast = { id, message, variant, duration, action }
            setToasts((prev) => [...prev, toast])

            if (duration > 0) {
                setTimeout(() => {
                    setToasts((prev) => prev.filter((t) => t.id !== id))
                }, duration)
            }
        },
        []
    )

    const removeToast = useCallback((id: string) => {
        setToasts((prev) => prev.filter((t) => t.id !== id))
    }, [])

    const positionStyles = {
        'top-right': 'top-4 right-4',
        'top-left': 'top-4 left-4',
        'bottom-right': 'bottom-4 right-4',
        'bottom-left': 'bottom-4 left-4',
        'top-center': 'top-4 left-1/2 -translate-x-1/2',
        'bottom-center': 'bottom-4 left-1/2 -translate-x-1/2',
    }

    return (
        <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
            {children}
            <div className={cn('fixed z-50 flex flex-col gap-2 max-w-sm', positionStyles[position])}>
                {toasts.map((toast) => (
                    <ToastItem key={toast.id} toast={toast} onDismiss={() => removeToast(toast.id)} />
                ))}
            </div>
        </ToastContext.Provider>
    )
}

interface ToastItemProps {
    toast: Toast
    onDismiss: () => void
}

function ToastItem({ toast, onDismiss }: ToastItemProps) {
    const variantStyles = {
        default: 'bg-dark-400 border-white/10 text-gray-200',
        success: 'bg-emerald-900/90 border-emerald-700 text-emerald-100',
        error: 'bg-red-900/90 border-red-700 text-red-100',
        warning: 'bg-amber-900/90 border-amber-700 text-amber-100',
        info: 'bg-primary-900/90 border-primary-700 text-primary-100',
    }

    const icons = {
        default: null,
        success: (
            <svg className="w-5 h-5 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <path d="M9 12l2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
        ),
        error: (
            <svg className="w-5 h-5 text-red-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <path d="M15 9l-6 6M9 9l6 6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
        ),
        warning: (
            <svg className="w-5 h-5 text-amber-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                <path d="M12 9v4M12 17h.01" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
        ),
        info: (
            <svg className="w-5 h-5 text-primary-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 16v-4M12 8h.01" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
        ),
    }

    return (
        <div
            className={cn(
                'flex items-start gap-3 p-4 rounded-lg border shadow-lg backdrop-blur-sm',
                'animate-in slide-in-from-right-full fade-in-0 duration-300',
                variantStyles[toast.variant]
            )}
        >
            {icons[toast.variant]}
            <div className="flex-1 min-w-0">
                <p className="text-sm">{toast.message}</p>
                {toast.action && (
                    <button
                        onClick={toast.action.onClick}
                        className="mt-2 text-xs font-medium underline underline-offset-2 opacity-80 hover:opacity-100"
                    >
                        {toast.action.label}
                    </button>
                )}
            </div>
            <button
                onClick={onDismiss}
                className="text-current opacity-50 hover:opacity-100 transition-opacity"
            >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M18 6L6 18M6 6l12 12" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
            </button>
        </div>
    )
}

// ============================================================================
// PROGRESS RING
// ============================================================================

interface ProgressRingProps {
    progress: number
    size?: number
    strokeWidth?: number
    className?: string
    children?: ReactNode
}

export function ProgressRing({
    progress,
    size = 48,
    strokeWidth = 4,
    className,
    children,
}: ProgressRingProps) {
    const radius = (size - strokeWidth) / 2
    const circumference = 2 * Math.PI * radius
    const offset = circumference - (progress / 100) * circumference

    return (
        <div className={cn('relative inline-flex items-center justify-center', className)}>
            <svg width={size} height={size} className="transform -rotate-90">
                {/* Background circle */}
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={strokeWidth}
                    className="text-gray-700"
                />
                {/* Progress circle */}
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke="url(#progressGradient)"
                    strokeWidth={strokeWidth}
                    strokeLinecap="round"
                    strokeDasharray={circumference}
                    strokeDashoffset={offset}
                    className="transition-all duration-300 ease-out"
                />
                <defs>
                    <linearGradient id="progressGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="#ff66ab" />
                        <stop offset="100%" stopColor="#aa92ff" />
                    </linearGradient>
                </defs>
            </svg>
            {children && (
                <div className="absolute inset-0 flex items-center justify-center text-sm font-medium">
                    {children}
                </div>
            )}
        </div>
    )
}

// ============================================================================
// STATUS INDICATOR
// ============================================================================

export interface StatusIndicatorProps {
    status: 'online' | 'offline' | 'busy' | 'away' | 'processing'
    size?: 'sm' | 'md' | 'lg'
    showLabel?: boolean
    className?: string
}

export function StatusIndicator({ status, size = 'md', showLabel, className }: StatusIndicatorProps) {
    const statusStyles = {
        online: { color: 'bg-emerald-500', label: 'Online' },
        offline: { color: 'bg-gray-500', label: 'Offline' },
        busy: { color: 'bg-red-500', label: 'Busy' },
        away: { color: 'bg-amber-500', label: 'Away' },
        processing: { color: 'bg-primary-500', label: 'Processing' },
    }

    const sizes = {
        sm: 'w-2 h-2',
        md: 'w-2.5 h-2.5',
        lg: 'w-3 h-3',
    }

    const { color, label } = statusStyles[status]

    return (
        <span className={cn('inline-flex items-center gap-1.5', className)}>
            <span className={cn('rounded-full', sizes[size], color, status === 'processing' && 'animate-pulse')} />
            {showLabel && <span className="text-xs text-gray-400">{label}</span>}
        </span>
    )
}

// ============================================================================
// HIGHLIGHT TAG
// ============================================================================

export interface HighlightTagProps extends HTMLAttributes<HTMLSpanElement> {
    color?: 'cyan' | 'fuchsia' | 'amber' | 'emerald' | 'red'
}

export const HighlightTag = forwardRef<HTMLSpanElement, HighlightTagProps>(
    ({ color = 'cyan', className, children, ...props }, ref) => {
        const colors = {
            cyan: 'from-primary-500/20 to-primary-500/10 text-primary-400 border-primary-500/30',
            fuchsia: 'from-fuchsia-500/20 to-fuchsia-500/10 text-fuchsia-400 border-fuchsia-500/30',
            amber: 'from-amber-500/20 to-amber-500/10 text-amber-400 border-amber-500/30',
            emerald: 'from-emerald-500/20 to-emerald-500/10 text-emerald-400 border-emerald-500/30',
            red: 'from-red-500/20 to-red-500/10 text-red-400 border-red-500/30',
        }

        return (
            <span
                ref={ref}
                className={cn(
                    'inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-md',
                    'bg-gradient-to-r border',
                    colors[color],
                    className
                )}
                {...props}
            >
                {children}
            </span>
        )
    }
)
HighlightTag.displayName = 'HighlightTag'
