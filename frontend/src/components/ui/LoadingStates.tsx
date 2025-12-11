/**
 * Loading State Components
 * Beautiful, branded loading indicators and skeleton states.
 */

import { forwardRef, type HTMLAttributes } from 'react'
import { cn } from '../../lib/utils'

// ============================================================================
// BRAND LOADER (Logo Animation)
// ============================================================================

export interface BrandLoaderProps extends HTMLAttributes<HTMLDivElement> {
    size?: 'sm' | 'md' | 'lg' | 'xl'
    message?: string
}

const sizeClasses = {
    sm: 'w-8 h-8',
    md: 'w-12 h-12',
    lg: 'w-16 h-16',
    xl: 'w-24 h-24',
}

export const BrandLoader = forwardRef<HTMLDivElement, BrandLoaderProps>(
    ({ size = 'md', message, className, ...props }, ref) => {
        return (
            <div
                ref={ref}
                className={cn('flex flex-col items-center justify-center gap-4', className)}
                {...props}
            >
                {/* Animated drum icon */}
                <div className={cn('relative', sizeClasses[size])}>
                    {/* Outer ring pulse */}
                    <div className="absolute inset-0 rounded-full bg-primary-500/20 animate-ping" />

                    {/* Main drum body */}
                    <div className="relative w-full h-full rounded-full bg-gradient-to-br from-primary-500 to-fuchsia-500 flex items-center justify-center animate-pulse">
                        {/* Drumstick icons */}
                        <svg
                            className="w-1/2 h-1/2 text-white animate-bounce"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                        >
                            <path d="M2 2l6 6" strokeLinecap="round" />
                            <circle cx="12" cy="12" r="3" fill="currentColor" />
                        </svg>
                    </div>

                    {/* Beat wave rings */}
                    <div className="absolute inset-0 rounded-full border-2 border-primary-400/30 animate-[ping_1s_ease-out_infinite]" />
                    <div className="absolute inset-0 rounded-full border-2 border-fuchsia-400/20 animate-[ping_1s_ease-out_0.5s_infinite]" />
                </div>

                {message && (
                    <p className="text-gray-400 text-sm animate-pulse">{message}</p>
                )}
            </div>
        )
    }
)
BrandLoader.displayName = 'BrandLoader'

// ============================================================================
// WAVEFORM LOADER
// ============================================================================

export interface WaveformLoaderProps extends HTMLAttributes<HTMLDivElement> {
    barCount?: number
    color?: string
}

export const WaveformLoader = forwardRef<HTMLDivElement, WaveformLoaderProps>(
    ({ barCount = 5, color = 'bg-primary-500', className, ...props }, ref) => {
        return (
            <div
                ref={ref}
                className={cn('flex items-center justify-center gap-1 h-8', className)}
                {...props}
            >
                {Array.from({ length: barCount }).map((_, i) => (
                    <div
                        key={i}
                        className={cn('w-1 rounded-full', color)}
                        style={{
                            height: '100%',
                            animation: `waveform 1s ease-in-out infinite`,
                            animationDelay: `${i * 0.1}s`,
                        }}
                    />
                ))}
                <style>{`
          @keyframes waveform {
            0%, 100% { transform: scaleY(0.3); }
            50% { transform: scaleY(1); }
          }
        `}</style>
            </div>
        )
    }
)
WaveformLoader.displayName = 'WaveformLoader'

// ============================================================================
// BEAT PULSE LOADER
// ============================================================================

export interface BeatPulseLoaderProps extends HTMLAttributes<HTMLDivElement> {
    pulseCount?: number
}

export const BeatPulseLoader = forwardRef<HTMLDivElement, BeatPulseLoaderProps>(
    ({ pulseCount = 4, className, ...props }, ref) => {
        return (
            <div
                ref={ref}
                className={cn('flex items-center justify-center gap-2', className)}
                {...props}
            >
                {Array.from({ length: pulseCount }).map((_, i) => (
                    <div
                        key={i}
                        className="w-3 h-3 rounded-full bg-gradient-to-r from-primary-500 to-fuchsia-500"
                        style={{
                            animation: `beatPulse 1.2s ease-in-out infinite`,
                            animationDelay: `${i * 0.15}s`,
                        }}
                    />
                ))}
                <style>{`
          @keyframes beatPulse {
            0%, 100% { transform: scale(0.5); opacity: 0.5; }
            50% { transform: scale(1.2); opacity: 1; }
          }
        `}</style>
            </div>
        )
    }
)
BeatPulseLoader.displayName = 'BeatPulseLoader'

// ============================================================================
// PROGRESS LOADER
// ============================================================================

export interface ProgressLoaderProps extends HTMLAttributes<HTMLDivElement> {
    progress?: number
    showPercentage?: boolean
    label?: string
    indeterminate?: boolean
}

export const ProgressLoader = forwardRef<HTMLDivElement, ProgressLoaderProps>(
    ({ progress = 0, showPercentage = true, label, indeterminate = false, className, ...props }, ref) => {
        return (
            <div ref={ref} className={cn('w-full max-w-md', className)} {...props}>
                {(label || showPercentage) && (
                    <div className="flex justify-between items-center mb-2">
                        {label && <span className="text-sm text-gray-400">{label}</span>}
                        {showPercentage && !indeterminate && (
                            <span className="text-sm font-medium text-gray-300">{Math.round(progress)}%</span>
                        )}
                    </div>
                )}

                <div className="h-2 bg-dark-400 rounded-full overflow-hidden">
                    {indeterminate ? (
                        <div
                            className="h-full w-1/3 bg-gradient-to-r from-primary-500 to-fuchsia-500 rounded-full"
                            style={{
                                animation: 'indeterminate 1.5s ease-in-out infinite',
                            }}
                        />
                    ) : (
                        <div
                            className="h-full bg-gradient-to-r from-primary-500 to-fuchsia-500 rounded-full transition-all duration-300"
                            style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
                        />
                    )}
                </div>

                <style>{`
          @keyframes indeterminate {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(400%); }
          }
        `}</style>
            </div>
        )
    }
)
ProgressLoader.displayName = 'ProgressLoader'

// ============================================================================
// SKELETON VARIANTS
// ============================================================================

export interface SkeletonProps extends HTMLAttributes<HTMLDivElement> {
    variant?: 'text' | 'title' | 'avatar' | 'button' | 'card' | 'image'
    animated?: boolean
}

export const Skeleton = forwardRef<HTMLDivElement, SkeletonProps>(
    ({ variant = 'text', animated = true, className, ...props }, ref) => {
        const variantClasses = {
            text: 'h-4 w-full rounded',
            title: 'h-8 w-3/4 rounded',
            avatar: 'h-12 w-12 rounded-full',
            button: 'h-10 w-24 rounded-lg',
            card: 'h-48 w-full rounded-xl',
            image: 'h-40 w-full rounded-lg aspect-video',
        }

        return (
            <div
                ref={ref}
                className={cn(
                    'bg-dark-400',
                    animated && 'animate-pulse',
                    variantClasses[variant],
                    className
                )}
                {...props}
            />
        )
    }
)
Skeleton.displayName = 'Skeleton'

// ============================================================================
// COMPOSITE SKELETON PRESETS
// ============================================================================

export function SongCardSkeleton({ className }: { className?: string }) {
    return (
        <div className={cn('bg-dark-500 rounded-xl border border-white/10 p-4', className)}>
            <Skeleton variant="image" className="mb-4" />
            <Skeleton variant="title" className="mb-2" />
            <Skeleton variant="text" className="w-1/2 mb-4" />
            <div className="flex justify-between items-center">
                <Skeleton variant="text" className="w-20" />
                <Skeleton variant="button" />
            </div>
        </div>
    )
}

export function TableRowSkeleton({ columns = 5 }: { columns?: number }) {
    return (
        <div className="flex items-center gap-4 p-4 border-b border-white/10">
            {Array.from({ length: columns }).map((_, i) => (
                <Skeleton key={i} variant="text" className={i === 0 ? 'w-1/4' : 'flex-1'} />
            ))}
        </div>
    )
}

export function ProfileSkeleton({ className }: { className?: string }) {
    return (
        <div className={cn('space-y-6', className)}>
            <div className="flex items-center gap-6">
                <Skeleton variant="avatar" className="w-24 h-24" />
                <div className="flex-1 space-y-3">
                    <Skeleton variant="title" className="w-1/3" />
                    <Skeleton variant="text" className="w-1/4" />
                </div>
            </div>
            <div className="grid grid-cols-3 gap-4">
                {[1, 2, 3].map((i) => (
                    <div key={i} className="bg-dark-500 rounded-lg p-4">
                        <Skeleton variant="text" className="w-1/2 mb-2" />
                        <Skeleton variant="title" className="w-16" />
                    </div>
                ))}
            </div>
        </div>
    )
}

export function TimelineSkeleton({ className }: { className?: string }) {
    return (
        <div className={cn('space-y-4', className)}>
            {/* Controls */}
            <div className="flex items-center gap-4 p-4 bg-dark-500 rounded-lg">
                <Skeleton variant="button" />
                <Skeleton variant="text" className="flex-1 h-2" />
                <Skeleton variant="text" className="w-16" />
            </div>

            {/* Waveform area */}
            <div className="bg-dark-500 rounded-lg p-4">
                <div className="flex items-end gap-0.5 h-32">
                    {Array.from({ length: 60 }).map((_, i) => (
                        <div
                            key={i}
                            className="flex-1 bg-dark-400 rounded-t animate-pulse"
                            style={{
                                height: `${20 + Math.random() * 80}%`,
                                animationDelay: `${i * 0.02}s`,
                            }}
                        />
                    ))}
                </div>
            </div>

            {/* Lanes */}
            <div className="space-y-2">
                {[1, 2, 3, 4].map((i) => (
                    <div key={i} className="flex items-center gap-2 p-2 bg-dark-500/50 rounded">
                        <Skeleton variant="text" className="w-20 h-6" />
                        <Skeleton variant="text" className="flex-1 h-8" />
                    </div>
                ))}
            </div>
        </div>
    )
}

// ============================================================================
// FULL PAGE LOADING SCREEN
// ============================================================================

interface FullPageLoaderProps {
    message?: string
    progress?: number
    showProgress?: boolean
}

export function FullPageLoader({
    message = 'Loading...',
    progress,
    showProgress = false,
}: FullPageLoaderProps) {
    return (
        <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-dark-500">
            {/* Ambient background */}
            <div className="absolute inset-0 bg-gradient-to-br from-primary-900/10 via-dark-500 to-fuchsia-900/10" />

            <div className="relative z-10 flex flex-col items-center gap-8 p-8">
                <BrandLoader size="xl" />

                <div className="text-center space-y-2">
                    <h2 className="text-xl font-semibold text-white">{message}</h2>
                    {showProgress && progress !== undefined && (
                        <p className="text-sm text-gray-400">
                            {Math.round(progress)}% complete
                        </p>
                    )}
                </div>

                {showProgress && (
                    <ProgressLoader
                        progress={progress ?? 0}
                        showPercentage={false}
                        className="w-64"
                    />
                )}
            </div>
        </div>
    )
}

// ============================================================================
// INLINE LOADING INDICATOR
// ============================================================================

interface InlineLoaderProps extends HTMLAttributes<HTMLSpanElement> {
    size?: 'sm' | 'md' | 'lg'
    label?: string
}

export const InlineLoader = forwardRef<HTMLSpanElement, InlineLoaderProps>(
    ({ size = 'md', label, className, ...props }, ref) => {
        const sizeClasses = {
            sm: 'w-4 h-4',
            md: 'w-5 h-5',
            lg: 'w-6 h-6',
        }

        return (
            <span
                ref={ref}
                className={cn('inline-flex items-center gap-2', className)}
                {...props}
            >
                <svg
                    className={cn('animate-spin text-current', sizeClasses[size])}
                    fill="none"
                    viewBox="0 0 24 24"
                >
                    <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                    />
                    <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    />
                </svg>
                {label && <span>{label}</span>}
            </span>
        )
    }
)
InlineLoader.displayName = 'InlineLoader'

// ============================================================================
// SHIMMER EFFECT
// ============================================================================

interface ShimmerProps extends HTMLAttributes<HTMLDivElement> {
    width?: string | number
    height?: string | number
}

export const Shimmer = forwardRef<HTMLDivElement, ShimmerProps>(
    ({ width = '100%', height = '1rem', className, style, ...props }, ref) => {
        return (
            <div
                ref={ref}
                className={cn(
                    'relative overflow-hidden bg-dark-400 rounded',
                    className
                )}
                style={{
                    width,
                    height,
                    ...style,
                }}
                {...props}
            >
                <div
                    className="absolute inset-0"
                    style={{
                        background: 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.05) 50%, transparent 100%)',
                        animation: 'shimmer 1.5s infinite',
                    }}
                />
                <style>{`
          @keyframes shimmer {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
          }
        `}</style>
            </div>
        )
    }
)
Shimmer.displayName = 'Shimmer'
