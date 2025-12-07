// Copyright (c) BeatSight. Licensed under the MIT Licence.
// See the LICENCE file in the repository root for full licence text.

import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '../../lib/utils';

// Notification variants
const notificationVariants = cva(
    'relative flex items-start gap-3 p-4 rounded-lg border shadow-lg transition-all duration-300 ease-out',
    {
        variants: {
            variant: {
                default: 'bg-gray-800 border-gray-700 text-white',
                success: 'bg-green-900/80 border-green-700 text-green-100',
                error: 'bg-red-900/80 border-red-700 text-red-100',
                warning: 'bg-yellow-900/80 border-yellow-700 text-yellow-100',
                info: 'bg-blue-900/80 border-blue-700 text-blue-100',
            },
        },
        defaultVariants: {
            variant: 'default',
        },
    }
);

// Types
export type NotificationVariant = 'default' | 'success' | 'error' | 'warning' | 'info';

export interface NotificationData {
    id: string;
    title?: string;
    message: string;
    variant?: NotificationVariant;
    duration?: number;
    dismissible?: boolean;
    action?: {
        label: string;
        onClick: () => void;
    };
}

export interface NotificationProps extends NotificationData {
    onDismiss?: () => void;
}

export interface NotificationProviderProps {
    children: React.ReactNode;
    position?: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right' | 'top-center' | 'bottom-center';
    maxNotifications?: number;
}

export interface NotificationContextType {
    notifications: NotificationData[];
    addNotification: (notification: Omit<NotificationData, 'id'>) => string;
    removeNotification: (id: string) => void;
    clearAll: () => void;
}

// Icons
const CheckIcon: React.FC<{ className?: string }> = ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M20 6L9 17l-5-5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
);

const XCircleIcon: React.FC<{ className?: string }> = ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="10" />
        <path d="M15 9l-6 6M9 9l6 6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
);

const AlertIcon: React.FC<{ className?: string }> = ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
        <line x1="12" y1="9" x2="12" y2="13" strokeLinecap="round" strokeLinejoin="round" />
        <line x1="12" y1="17" x2="12.01" y2="17" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
);

const InfoIcon: React.FC<{ className?: string }> = ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="16" x2="12" y2="12" strokeLinecap="round" />
        <line x1="12" y1="8" x2="12.01" y2="8" strokeLinecap="round" />
    </svg>
);

const XIcon: React.FC<{ className?: string }> = ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <line x1="18" y1="6" x2="6" y2="18" strokeLinecap="round" strokeLinejoin="round" />
        <line x1="6" y1="6" x2="18" y2="18" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
);

const BellIcon: React.FC<{ className?: string }> = ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M13.73 21a2 2 0 01-3.46 0" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
);

const getVariantIcon = (variant: NotificationVariant) => {
    switch (variant) {
        case 'success':
            return <CheckIcon className="w-5 h-5 text-green-400" />;
        case 'error':
            return <XCircleIcon className="w-5 h-5 text-red-400" />;
        case 'warning':
            return <AlertIcon className="w-5 h-5 text-yellow-400" />;
        case 'info':
            return <InfoIcon className="w-5 h-5 text-blue-400" />;
        default:
            return <BellIcon className="w-5 h-5 text-gray-400" />;
    }
};

// Context
const NotificationContext = React.createContext<NotificationContextType | null>(null);

/**
 * useNotification - Hook to access notification system
 */
export const useNotification = (): NotificationContextType => {
    const context = React.useContext(NotificationContext);
    if (!context) {
        throw new Error('useNotification must be used within a NotificationProvider');
    }
    return context;
};

/**
 * Notification - Single notification component
 */
export const Notification = React.forwardRef<HTMLDivElement, NotificationProps & VariantProps<typeof notificationVariants>>(
    ({ id: _id, title, message, variant = 'default', dismissible = true, action, onDismiss, ...props }, ref) => {
        return (
            <div
                ref={ref}
                className={cn(notificationVariants({ variant }))}
                role="alert"
                aria-live="polite"
                {...props}
            >
                {/* Icon */}
                <div className="flex-shrink-0 mt-0.5">{getVariantIcon(variant)}</div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                    {title && <h4 className="text-sm font-semibold mb-1">{title}</h4>}
                    <p className="text-sm opacity-90">{message}</p>

                    {/* Action Button */}
                    {action && (
                        <button
                            onClick={action.onClick}
                            className="mt-2 text-sm font-medium hover:underline focus:outline-none"
                        >
                            {action.label}
                        </button>
                    )}
                </div>

                {/* Dismiss Button */}
                {dismissible && onDismiss && (
                    <button
                        onClick={onDismiss}
                        className="flex-shrink-0 p-1 rounded-full opacity-70 hover:opacity-100 hover:bg-white/10 transition-opacity"
                        aria-label="Dismiss"
                    >
                        <XIcon className="w-4 h-4" />
                    </button>
                )}
            </div>
        );
    }
);
Notification.displayName = 'Notification';

/**
 * NotificationContainer - Container for positioned notifications
 */
const positionClasses = {
    'top-left': 'top-4 left-4',
    'top-right': 'top-4 right-4',
    'bottom-left': 'bottom-4 left-4',
    'bottom-right': 'bottom-4 right-4',
    'top-center': 'top-4 left-1/2 -translate-x-1/2',
    'bottom-center': 'bottom-4 left-1/2 -translate-x-1/2',
};

interface NotificationContainerProps {
    notifications: NotificationData[];
    position: keyof typeof positionClasses;
    onDismiss: (id: string) => void;
}

const NotificationContainer: React.FC<NotificationContainerProps> = ({ notifications, position, onDismiss }) => {
    return (
        <div
            className={cn(
                'fixed z-50 flex flex-col gap-3 max-w-sm w-full pointer-events-none',
                positionClasses[position]
            )}
        >
            {notifications.map((notification) => (
                <div
                    key={notification.id}
                    className="pointer-events-auto animate-in fade-in slide-in-from-top-2 duration-300"
                >
                    <Notification {...notification} onDismiss={() => onDismiss(notification.id)} />
                </div>
            ))}
        </div>
    );
};

/**
 * NotificationProvider - Context provider for notification system
 */
export const NotificationProvider: React.FC<NotificationProviderProps> = ({
    children,
    position = 'top-right',
    maxNotifications = 5,
}) => {
    const [notifications, setNotifications] = React.useState<NotificationData[]>([]);

    const addNotification = React.useCallback(
        (notification: Omit<NotificationData, 'id'>): string => {
            const id = `notification-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
            const newNotification: NotificationData = {
                id,
                dismissible: true,
                duration: 5000,
                ...notification,
            };

            setNotifications((prev) => {
                const updated = [newNotification, ...prev];
                return updated.slice(0, maxNotifications);
            });

            // Auto-dismiss after duration
            if (newNotification.duration && newNotification.duration > 0) {
                setTimeout(() => {
                    setNotifications((prev) => prev.filter((n) => n.id !== id));
                }, newNotification.duration);
            }

            return id;
        },
        [maxNotifications]
    );

    const removeNotification = React.useCallback((id: string) => {
        setNotifications((prev) => prev.filter((n) => n.id !== id));
    }, []);

    const clearAll = React.useCallback(() => {
        setNotifications([]);
    }, []);

    const contextValue = React.useMemo(
        () => ({
            notifications,
            addNotification,
            removeNotification,
            clearAll,
        }),
        [notifications, addNotification, removeNotification, clearAll]
    );

    return (
        <NotificationContext.Provider value={contextValue}>
            {children}
            <NotificationContainer notifications={notifications} position={position} onDismiss={removeNotification} />
        </NotificationContext.Provider>
    );
};

// Utility functions for quick notifications
export const notify = {
    success: (message: string, options?: Partial<NotificationData>) => ({
        message,
        variant: 'success' as const,
        ...options,
    }),
    error: (message: string, options?: Partial<NotificationData>) => ({
        message,
        variant: 'error' as const,
        ...options,
    }),
    warning: (message: string, options?: Partial<NotificationData>) => ({
        message,
        variant: 'warning' as const,
        ...options,
    }),
    info: (message: string, options?: Partial<NotificationData>) => ({
        message,
        variant: 'info' as const,
        ...options,
    }),
};

/**
 * Toast - Simple toast notification shorthand
 */
export interface ToastProps {
    message: string;
    variant?: NotificationVariant;
    duration?: number;
}

/**
 * NotificationBadge - Badge indicator for unread notifications
 */
export interface NotificationBadgeProps {
    count: number;
    max?: number;
    className?: string;
}

export const NotificationBadge: React.FC<NotificationBadgeProps> = ({ count, max = 99, className }) => {
    if (count <= 0) return null;

    const displayCount = count > max ? `${max}+` : count.toString();

    return (
        <span
            className={cn(
                'inline-flex items-center justify-center min-w-5 h-5 px-1.5 text-xs font-bold text-white bg-red-500 rounded-full',
                className
            )}
        >
            {displayCount}
        </span>
    );
};

/**
 * NotificationBell - Bell icon with badge for notification indicator
 */
export interface NotificationBellProps {
    count?: number;
    onClick?: () => void;
    className?: string;
}

export const NotificationBell: React.FC<NotificationBellProps> = ({ count = 0, onClick, className }) => {
    return (
        <button
            onClick={onClick}
            className={cn(
                'relative p-2 rounded-full hover:bg-gray-700 transition-colors focus:outline-none focus:ring-2 focus:ring-primary',
                className
            )}
            aria-label={`Notifications${count > 0 ? ` (${count} unread)` : ''}`}
        >
            <BellIcon className="w-5 h-5 text-gray-300" />
            {count > 0 && (
                <span className="absolute top-0 right-0 w-4 h-4 bg-red-500 rounded-full text-xs text-white flex items-center justify-center">
                    {count > 9 ? '9+' : count}
                </span>
            )}
        </button>
    );
};

/**
 * NotificationList - List view for notification center
 */
export interface NotificationListProps {
    notifications: NotificationData[];
    onDismiss?: (id: string) => void;
    onClearAll?: () => void;
    emptyMessage?: string;
    className?: string;
}

export const NotificationList: React.FC<NotificationListProps> = ({
    notifications,
    onDismiss,
    onClearAll,
    emptyMessage = 'No notifications',
    className,
}) => {
    return (
        <div className={cn('w-full', className)}>
            {/* Header */}
            <div className="flex items-center justify-between pb-3 border-b border-gray-700">
                <h3 className="text-sm font-semibold text-white">Notifications</h3>
                {notifications.length > 0 && onClearAll && (
                    <button onClick={onClearAll} className="text-xs text-primary hover:underline">
                        Clear all
                    </button>
                )}
            </div>

            {/* List */}
            <div className="mt-3 space-y-2 max-h-80 overflow-y-auto">
                {notifications.length === 0 ? (
                    <div className="py-8 text-center text-gray-500 text-sm">{emptyMessage}</div>
                ) : (
                    notifications.map((notification) => (
                        <Notification
                            key={notification.id}
                            {...notification}
                            onDismiss={onDismiss ? () => onDismiss(notification.id) : undefined}
                        />
                    ))
                )}
            </div>
        </div>
    );
};

export default NotificationProvider;
