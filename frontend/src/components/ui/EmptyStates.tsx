/**
 * Empty State Components
 * Engaging, helpful empty states that guide users to take action.
 */

import { forwardRef, type HTMLAttributes, type ReactNode } from 'react'
import { cn } from '../../lib/utils'

// ============================================================================
// BASE EMPTY STATE
// ============================================================================

export interface EmptyStateProps extends HTMLAttributes<HTMLDivElement> {
    icon?: ReactNode
    title: string
    description?: string
    action?: ReactNode
    secondaryAction?: ReactNode
    size?: 'sm' | 'md' | 'lg'
}

const sizeStyles = {
    sm: {
        container: 'py-8 px-4',
        icon: 'w-12 h-12 mb-3',
        title: 'text-lg',
        description: 'text-sm',
    },
    md: {
        container: 'py-12 px-6',
        icon: 'w-16 h-16 mb-4',
        title: 'text-xl',
        description: 'text-base',
    },
    lg: {
        container: 'py-16 px-8',
        icon: 'w-20 h-20 mb-6',
        title: 'text-2xl',
        description: 'text-lg',
    },
}

export const EmptyState = forwardRef<HTMLDivElement, EmptyStateProps>(
    (
        {
            icon,
            title,
            description,
            action,
            secondaryAction,
            size = 'md',
            className,
            ...props
        },
        ref
    ) => {
        const styles = sizeStyles[size]

        return (
            <div
                ref={ref}
                className={cn(
                    'flex flex-col items-center justify-center text-center',
                    styles.container,
                    className
                )}
                {...props}
            >
                {icon && (
                    <div className={cn('text-slate-600', styles.icon)}>
                        {icon}
                    </div>
                )}

                <h3 className={cn('font-semibold text-slate-200 mb-2', styles.title)}>
                    {title}
                </h3>

                {description && (
                    <p className={cn('text-slate-400 max-w-sm mb-6', styles.description)}>
                        {description}
                    </p>
                )}

                {(action || secondaryAction) && (
                    <div className="flex flex-col sm:flex-row items-center gap-3">
                        {action}
                        {secondaryAction}
                    </div>
                )}
            </div>
        )
    }
)
EmptyState.displayName = 'EmptyState'

// ============================================================================
// PRESET ICONS
// ============================================================================

export function NoDataIcon({ className }: { className?: string }) {
    return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
    )
}

export function NoSongsIcon({ className }: { className?: string }) {
    return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2z" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
    )
}

export function NoSearchResultsIcon({ className }: { className?: string }) {
    return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <circle cx="11" cy="11" r="8" />
            <path d="M21 21l-4.35-4.35M8 8l6 6M14 8l-6 6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
    )
}

export function NoNotificationsIcon({ className }: { className?: string }) {
    return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 01-3.46 0" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M3 3l18 18" strokeLinecap="round" />
        </svg>
    )
}

export function NoActivityIcon({ className }: { className?: string }) {
    return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M22 12h-4l-3 9L9 3l-3 9H2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
    )
}

export function ErrorIcon({ className }: { className?: string }) {
    return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 8v4M12 16h.01" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
    )
}

export function OfflineIcon({ className }: { className?: string }) {
    return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M1 1l22 22M16.72 11.06A10.94 10.94 0 0119 12.55M5 12.55a10.94 10.94 0 015.17-2.39M10.71 5.05A16 16 0 0122.58 9M1.42 9a15.91 15.91 0 014.7-2.88M8.53 16.11a6 6 0 016.95 0M12 20h.01" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
    )
}

export function UploadIcon({ className }: { className?: string }) {
    return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
    )
}

// ============================================================================
// PRESET EMPTY STATES
// ============================================================================

interface PresetEmptyStateProps {
    action?: ReactNode
    secondaryAction?: ReactNode
    className?: string
}

export function NoSongsEmptyState({ action, secondaryAction, className }: PresetEmptyStateProps) {
    return (
        <EmptyState
            icon={<NoSongsIcon className="w-full h-full" />}
            title="No songs yet"
            description="Upload your first track to start creating beatmaps—build from scratch or use AI-assisted transcription."
            action={action}
            secondaryAction={secondaryAction}
            className={className}
        />
    )
}

export function NoSearchResultsEmptyState({
    query,
    action,
    className,
}: PresetEmptyStateProps & { query?: string }) {
    return (
        <EmptyState
            icon={<NoSearchResultsIcon className="w-full h-full" />}
            title="No results found"
            description={
                query
                    ? `We couldn't find anything matching "${query}". Try adjusting your search.`
                    : "We couldn't find what you're looking for. Try different keywords."
            }
            action={action}
            className={className}
        />
    )
}

export function NoNotificationsEmptyState({ className }: PresetEmptyStateProps) {
    return (
        <EmptyState
            icon={<NoNotificationsIcon className="w-full h-full" />}
            title="All caught up!"
            description="You have no new notifications. We'll let you know when something happens."
            size="sm"
            className={className}
        />
    )
}

export function ErrorEmptyState({
    title = 'Something went wrong',
    description = "We're having trouble loading this content. Please try again.",
    action,
    className,
}: PresetEmptyStateProps & { title?: string; description?: string }) {
    return (
        <EmptyState
            icon={<ErrorIcon className="w-full h-full text-red-500" />}
            title={title}
            description={description}
            action={action}
            className={className}
        />
    )
}

export function OfflineEmptyState({ action, className }: PresetEmptyStateProps) {
    return (
        <EmptyState
            icon={<OfflineIcon className="w-full h-full text-amber-500" />}
            title="You're offline"
            description="Check your internet connection and try again."
            action={action}
            className={className}
        />
    )
}

export function UploadEmptyState({ action, className }: PresetEmptyStateProps) {
    return (
        <EmptyState
            icon={<UploadIcon className="w-full h-full" />}
            title="Upload a file"
            description="Drag and drop your audio file here, or click to browse."
            action={action}
            className={className}
        />
    )
}

export function NoBeatmapsEmptyState({ action, secondaryAction, className }: PresetEmptyStateProps) {
    return (
        <EmptyState
            icon={
                <svg className="w-full h-full" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <rect x="3" y="3" width="18" height="18" rx="2" />
                    <path d="M3 9h18M9 21V9" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
            }
            title="No beatmaps"
            description="Create your first beatmap by uploading a song and letting our AI transcribe the drums."
            action={action}
            secondaryAction={secondaryAction}
            className={className}
        />
    )
}

export function NoActivityEmptyState({ className }: PresetEmptyStateProps) {
    return (
        <EmptyState
            icon={<NoActivityIcon className="w-full h-full" />}
            title="No activity yet"
            description="Your recent activity will appear here once you start using BeatSight."
            size="sm"
            className={className}
        />
    )
}

// ============================================================================
// ILLUSTRATED EMPTY STATE
// ============================================================================

export interface IllustratedEmptyStateProps extends EmptyStateProps {
    illustration?: 'music' | 'search' | 'error' | 'upload' | 'drum'
}

const illustrations: Record<string, ReactNode> = {
    music: (
        <div className="relative w-32 h-32">
            {/* Background circles */}
            <div className="absolute inset-0 rounded-full bg-gradient-to-br from-cyan-500/20 to-fuchsia-500/20 animate-pulse" />
            <div className="absolute inset-4 rounded-full bg-gradient-to-br from-cyan-500/10 to-fuchsia-500/10" />

            {/* Music note */}
            <svg className="absolute inset-0 w-full h-full p-8 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M9 18V5l12-2v13M9 18c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2z" strokeLinecap="round" strokeLinejoin="round" />
            </svg>

            {/* Floating notes */}
            <div className="absolute -top-2 -right-2 w-6 h-6 text-cyan-400 animate-float">
                <svg viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z" />
                </svg>
            </div>
            <div className="absolute -bottom-1 -left-1 w-4 h-4 text-fuchsia-400 animate-float" style={{ animationDelay: '0.5s' }}>
                <svg viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z" />
                </svg>
            </div>
        </div>
    ),
    drum: (
        <div className="relative w-32 h-32">
            {/* Drum kit illustration */}
            <div className="absolute inset-0 flex items-center justify-center">
                <div className="relative">
                    {/* Snare */}
                    <div className="w-16 h-8 bg-gradient-to-b from-slate-600 to-slate-700 rounded-full border-2 border-slate-500" />
                    {/* Drumsticks */}
                    <div className="absolute -top-4 left-1/2 -translate-x-1/2 flex gap-2">
                        <div className="w-1 h-10 bg-amber-600 rounded-full rotate-[-20deg] origin-bottom" />
                        <div className="w-1 h-10 bg-amber-600 rounded-full rotate-[20deg] origin-bottom" />
                    </div>
                    {/* Beat waves */}
                    <div className="absolute inset-0 rounded-full border-2 border-cyan-400/30 animate-ping" />
                </div>
            </div>
        </div>
    ),
    search: (
        <div className="relative w-32 h-32">
            <div className="absolute inset-0 flex items-center justify-center">
                <svg className="w-20 h-20 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <circle cx="11" cy="11" r="8" />
                    <path d="M21 21l-4.35-4.35" strokeLinecap="round" />
                </svg>
                <div className="absolute top-4 right-4 text-slate-600">
                    <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M6 18L18 6M6 6l12 12" strokeLinecap="round" />
                    </svg>
                </div>
            </div>
        </div>
    ),
    error: (
        <div className="relative w-32 h-32">
            <div className="absolute inset-0 rounded-full bg-red-500/10 animate-pulse" />
            <svg className="absolute inset-0 w-full h-full p-6 text-red-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 8v4M12 16h.01" strokeLinecap="round" />
            </svg>
        </div>
    ),
    upload: (
        <div className="relative w-32 h-32">
            <div className="absolute inset-0 rounded-2xl border-2 border-dashed border-slate-600 flex items-center justify-center">
                <svg className="w-12 h-12 text-slate-500 animate-bounce" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
            </div>
        </div>
    ),
}

export const IllustratedEmptyState = forwardRef<HTMLDivElement, IllustratedEmptyStateProps>(
    ({ illustration = 'music', title, description, action, secondaryAction, className, ...props }, ref) => {
        return (
            <div
                ref={ref}
                className={cn('flex flex-col items-center justify-center text-center py-16 px-8', className)}
                {...props}
            >
                <div className="mb-6">
                    {illustrations[illustration]}
                </div>

                <h3 className="text-xl font-semibold text-slate-200 mb-2">{title}</h3>

                {description && (
                    <p className="text-slate-400 max-w-md mb-6">{description}</p>
                )}

                {(action || secondaryAction) && (
                    <div className="flex flex-col sm:flex-row items-center gap-3">
                        {action}
                        {secondaryAction}
                    </div>
                )}
            </div>
        )
    }
)
IllustratedEmptyState.displayName = 'IllustratedEmptyState'
