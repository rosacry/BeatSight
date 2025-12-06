/**
 * Skeleton - Premium loading placeholder components
 * 
 * Shimmer animations and smart skeleton layouts for a polished loading experience.
 * Supports BeatSight-specific skeletons for common UI patterns.
 */

import { motion } from 'framer-motion'
import { cn } from '../../lib/utils'

// ============================================================================
// Base Skeleton
// ============================================================================

interface SkeletonProps {
    className?: string
    variant?: 'default' | 'circular' | 'rounded'
    animation?: 'shimmer' | 'pulse' | 'wave' | 'none'
    width?: number | string
    height?: number | string
}

export function Skeleton({
    className,
    variant = 'default',
    animation = 'shimmer',
    width,
    height,
}: SkeletonProps) {
    const baseStyles = cn(
        'bg-gradient-to-r from-gray-800 via-gray-700 to-gray-800',
        variant === 'circular' && 'rounded-full',
        variant === 'rounded' && 'rounded-lg',
        variant === 'default' && 'rounded',
        animation === 'shimmer' && 'animate-shimmer bg-[length:200%_100%]',
        animation === 'pulse' && 'animate-pulse',
        animation === 'wave' && 'animate-wave',
        className
    )

    const style = {
        width: typeof width === 'number' ? `${width}px` : width,
        height: typeof height === 'number' ? `${height}px` : height,
    }

    return <div className={baseStyles} style={style} />
}

// ============================================================================
// Skeleton Text
// ============================================================================

interface SkeletonTextProps {
    lines?: number
    lastLineWidth?: string
    className?: string
    lineHeight?: number
    gap?: number
}

export function SkeletonText({
    lines = 3,
    lastLineWidth = '60%',
    className,
    lineHeight = 16,
    gap = 8,
}: SkeletonTextProps) {
    return (
        <div className={cn('space-y-2', className)} style={{ gap: `${gap}px` }}>
            {Array.from({ length: lines }).map((_, i) => (
                <Skeleton
                    key={i}
                    height={lineHeight}
                    width={i === lines - 1 ? lastLineWidth : '100%'}
                />
            ))}
        </div>
    )
}

// ============================================================================
// Skeleton Avatar
// ============================================================================

interface SkeletonAvatarProps {
    size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl'
    className?: string
}

const avatarSizes = {
    xs: 24,
    sm: 32,
    md: 40,
    lg: 48,
    xl: 64,
}

export function SkeletonAvatar({ size = 'md', className }: SkeletonAvatarProps) {
    const dimension = avatarSizes[size]
    return (
        <Skeleton
            variant="circular"
            width={dimension}
            height={dimension}
            className={className}
        />
    )
}

// ============================================================================
// Skeleton Card
// ============================================================================

interface SkeletonCardProps {
    className?: string
    showImage?: boolean
    showAvatar?: boolean
    imageHeight?: number
    lines?: number
}

export function SkeletonCard({
    className,
    showImage = true,
    showAvatar = true,
    imageHeight = 160,
    lines = 2,
}: SkeletonCardProps) {
    return (
        <div
            className={cn(
                'rounded-xl bg-gray-900/50 border border-gray-800 overflow-hidden',
                className
            )}
        >
            {showImage && (
                <Skeleton height={imageHeight} className="rounded-none" />
            )}
            <div className="p-4 space-y-3">
                {showAvatar && (
                    <div className="flex items-center gap-3">
                        <SkeletonAvatar size="sm" />
                        <div className="flex-1 space-y-2">
                            <Skeleton height={14} width="40%" />
                            <Skeleton height={12} width="20%" />
                        </div>
                    </div>
                )}
                <SkeletonText lines={lines} />
            </div>
        </div>
    )
}

// ============================================================================
// Skeleton Table
// ============================================================================

interface SkeletonTableProps {
    rows?: number
    columns?: number
    className?: string
    showHeader?: boolean
}

export function SkeletonTable({
    rows = 5,
    columns = 4,
    className,
    showHeader = true,
}: SkeletonTableProps) {
    return (
        <div className={cn('w-full', className)}>
            {showHeader && (
                <div className="flex gap-4 p-4 border-b border-gray-800 bg-gray-900/30">
                    {Array.from({ length: columns }).map((_, i) => (
                        <Skeleton
                            key={i}
                            height={14}
                            width={`${100 / columns - 2}%`}
                        />
                    ))}
                </div>
            )}
            {Array.from({ length: rows }).map((_, rowIndex) => (
                <div
                    key={rowIndex}
                    className="flex gap-4 p-4 border-b border-gray-800/50"
                >
                    {Array.from({ length: columns }).map((_, colIndex) => (
                        <Skeleton
                            key={colIndex}
                            height={16}
                            width={colIndex === 0 ? '30%' : `${100 / columns - 2}%`}
                        />
                    ))}
                </div>
            ))}
        </div>
    )
}

// ============================================================================
// BeatSight-specific Skeletons
// ============================================================================

// Track Card Skeleton
export function SkeletonTrackCard({ className }: { className?: string }) {
    return (
        <div
            className={cn(
                'flex gap-4 p-4 rounded-xl bg-gray-900/50 border border-gray-800',
                className
            )}
        >
            {/* Album art */}
            <Skeleton variant="rounded" width={80} height={80} />

            {/* Track info */}
            <div className="flex-1 space-y-2">
                <Skeleton height={18} width="60%" />
                <Skeleton height={14} width="40%" />
                <div className="flex items-center gap-4 mt-3">
                    <Skeleton height={12} width={60} />
                    <Skeleton height={12} width={40} />
                    <Skeleton height={12} width={50} />
                </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2">
                <Skeleton variant="circular" width={32} height={32} />
                <Skeleton variant="circular" width={32} height={32} />
            </div>
        </div>
    )
}

// Waveform Skeleton
export function SkeletonWaveform({ className }: { className?: string }) {
    return (
        <div className={cn('flex items-end gap-0.5 h-16', className)}>
            {Array.from({ length: 100 }).map((_, i) => {
                // Create a wave-like pattern
                const height = Math.sin((i / 100) * Math.PI * 4) * 30 + 35 + Math.random() * 10
                return (
                    <motion.div
                        key={i}
                        className="flex-1 bg-gradient-to-t from-cyan-500/20 to-cyan-500/40 rounded-t"
                        style={{ height: `${height}%` }}
                        animate={{
                            opacity: [0.5, 0.8, 0.5],
                        }}
                        transition={{
                            duration: 1.5,
                            repeat: Infinity,
                            delay: i * 0.01,
                        }}
                    />
                )
            })}
        </div>
    )
}

// Stats Card Skeleton
export function SkeletonStatsCard({ className }: { className?: string }) {
    return (
        <div
            className={cn(
                'p-6 rounded-xl bg-gray-900/50 border border-gray-800',
                className
            )}
        >
            <div className="flex items-start justify-between">
                <div className="space-y-2">
                    <Skeleton height={12} width={80} />
                    <Skeleton height={32} width={120} />
                    <Skeleton height={14} width={100} />
                </div>
                <Skeleton variant="circular" width={48} height={48} />
            </div>
        </div>
    )
}

// Profile Skeleton
export function SkeletonProfile({ className }: { className?: string }) {
    return (
        <div className={cn('space-y-6', className)}>
            {/* Header */}
            <div className="flex items-center gap-6">
                <SkeletonAvatar size="xl" />
                <div className="space-y-2">
                    <Skeleton height={24} width={180} />
                    <Skeleton height={14} width={120} />
                </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-3 gap-4">
                {Array.from({ length: 3 }).map((_, i) => (
                    <SkeletonStatsCard key={i} />
                ))}
            </div>

            {/* Content */}
            <SkeletonText lines={4} />
        </div>
    )
}

// Job Progress Skeleton
export function SkeletonJobProgress({ className }: { className?: string }) {
    return (
        <div
            className={cn(
                'p-4 rounded-xl bg-gray-900/50 border border-gray-800',
                className
            )}
        >
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                    <Skeleton variant="circular" width={40} height={40} />
                    <div className="space-y-1">
                        <Skeleton height={16} width={140} />
                        <Skeleton height={12} width={80} />
                    </div>
                </div>
                <Skeleton variant="rounded" height={24} width={70} />
            </div>

            {/* Progress bar */}
            <Skeleton height={8} variant="rounded" className="mb-2" />

            {/* Steps */}
            <div className="flex gap-2">
                {Array.from({ length: 4 }).map((_, i) => (
                    <Skeleton key={i} height={6} variant="rounded" className="flex-1" />
                ))}
            </div>
        </div>
    )
}

// Beatmap Card Skeleton
export function SkeletonBeatmapCard({ className }: { className?: string }) {
    return (
        <div
            className={cn(
                'rounded-xl bg-gray-900/50 border border-gray-800 overflow-hidden',
                className
            )}
        >
            {/* Cover image with gradient overlay */}
            <div className="relative">
                <Skeleton height={140} className="rounded-none" />
                <div className="absolute bottom-0 left-0 right-0 p-3 bg-gradient-to-t from-gray-900">
                    <div className="flex gap-2">
                        {Array.from({ length: 3 }).map((_, i) => (
                            <Skeleton key={i} height={18} width={50} variant="rounded" />
                        ))}
                    </div>
                </div>
            </div>

            {/* Info */}
            <div className="p-4 space-y-3">
                <Skeleton height={18} width="80%" />
                <Skeleton height={14} width="50%" />

                <div className="flex items-center justify-between pt-2">
                    <div className="flex items-center gap-2">
                        <SkeletonAvatar size="xs" />
                        <Skeleton height={12} width={60} />
                    </div>
                    <div className="flex gap-2">
                        <Skeleton height={12} width={40} />
                        <Skeleton height={12} width={40} />
                    </div>
                </div>
            </div>
        </div>
    )
}

// Dashboard Grid Skeleton
export function SkeletonDashboard({ className }: { className?: string }) {
    return (
        <div className={cn('space-y-6', className)}>
            {/* Stats row */}
            <div className="grid grid-cols-4 gap-4">
                {Array.from({ length: 4 }).map((_, i) => (
                    <SkeletonStatsCard key={i} />
                ))}
            </div>

            {/* Main content */}
            <div className="grid grid-cols-3 gap-6">
                <div className="col-span-2 space-y-4">
                    <Skeleton height={20} width={150} />
                    {Array.from({ length: 3 }).map((_, i) => (
                        <SkeletonTrackCard key={i} />
                    ))}
                </div>

                <div className="space-y-4">
                    <Skeleton height={20} width={120} />
                    {Array.from({ length: 2 }).map((_, i) => (
                        <SkeletonBeatmapCard key={i} />
                    ))}
                </div>
            </div>
        </div>
    )
}

// Export types
export type {
    SkeletonProps,
    SkeletonTextProps,
    SkeletonAvatarProps,
    SkeletonCardProps,
    SkeletonTableProps,
}
