/**
 * Loading skeleton components for content placeholders.
 * Provides visual loading indicators with proper accessibility.
 */

import clsx from 'clsx';

interface SkeletonProps {
    className?: string;
    /** Accessible label for screen readers */
    label?: string;
}

export function Skeleton({ className, label = 'Loading' }: SkeletonProps) {
    return (
        <div
            className={clsx(
                'animate-pulse bg-dark-300 rounded',
                className
            )}
            role="status"
            aria-label={label}
            aria-busy="true"
        >
            <span className="sr-only">{label}...</span>
        </div>
    );
}

export function SkeletonText({ className }: SkeletonProps) {
    return <Skeleton className={clsx('h-4 w-full', className)} />;
}

export function SkeletonTitle({ className }: SkeletonProps) {
    return <Skeleton className={clsx('h-6 w-3/4', className)} />;
}

export function SkeletonAvatar({ className }: SkeletonProps) {
    return <Skeleton className={clsx('h-10 w-10 rounded-full', className)} />;
}

export function SkeletonButton({ className }: SkeletonProps) {
    return <Skeleton className={clsx('h-10 w-24 rounded-lg', className)} />;
}

export function SkeletonImage({ className }: SkeletonProps) {
    return <Skeleton className={clsx('h-48 w-full rounded-lg', className)} />;
}

// Composite skeletons for common patterns

export function SongCardSkeleton() {
    return (
        <div className="bg-dark-400 rounded-lg p-4 border border-white/10">
            <SkeletonImage className="h-40 mb-4" />
            <SkeletonTitle className="mb-2" />
            <SkeletonText className="w-1/2 mb-2" />
            <div className="flex justify-between items-center mt-4">
                <SkeletonText className="w-16" />
                <SkeletonButton className="w-20" />
            </div>
        </div>
    );
}

export function SongListItemSkeleton() {
    return (
        <div className="flex items-center gap-4 p-4 bg-dark-400 rounded-lg border border-white/10">
            <Skeleton className="h-12 w-12 rounded" />
            <div className="flex-1">
                <SkeletonTitle className="mb-2 w-1/3" />
                <SkeletonText className="w-1/4" />
            </div>
            <SkeletonText className="w-12" />
            <SkeletonButton />
        </div>
    );
}

export function ProfileSkeleton() {
    return (
        <div className="space-y-6">
            <div className="flex items-center gap-6">
                <Skeleton className="h-24 w-24 rounded-full" />
                <div className="flex-1 space-y-3">
                    <SkeletonTitle className="w-1/3" />
                    <SkeletonText className="w-1/4" />
                </div>
            </div>
            <div className="grid grid-cols-3 gap-4">
                {[1, 2, 3].map((i) => (
                    <div key={i} className="bg-dark-400 rounded-lg p-4">
                        <SkeletonText className="w-1/2 mb-2" />
                        <Skeleton className="h-8 w-16" />
                    </div>
                ))}
            </div>
        </div>
    );
}

export function JobCardSkeleton() {
    return (
        <div className="bg-dark-400 rounded-lg p-4 border border-white/10">
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                    <Skeleton className="h-10 w-10 rounded" />
                    <div>
                        <SkeletonTitle className="w-32 mb-1" />
                        <SkeletonText className="w-20" />
                    </div>
                </div>
                <Skeleton className="h-6 w-20 rounded-full" />
            </div>
            <Skeleton className="h-2 w-full rounded-full" />
        </div>
    );
}

export function TableRowSkeleton({ columns = 5 }: { columns?: number }) {
    return (
        <tr className="border-b border-white/10">
            {Array.from({ length: columns }).map((_, i) => (
                <td key={i} className="p-4">
                    <SkeletonText className={i === 0 ? 'w-3/4' : 'w-1/2'} />
                </td>
            ))}
        </tr>
    );
}

export function LibraryGridSkeleton({ count = 8 }: { count?: number }) {
    return (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {Array.from({ length: count }).map((_, i) => (
                <SongCardSkeleton key={i} />
            ))}
        </div>
    );
}

export function LibraryListSkeleton({ count = 5 }: { count?: number }) {
    return (
        <div className="space-y-3">
            {Array.from({ length: count }).map((_, i) => (
                <SongListItemSkeleton key={i} />
            ))}
        </div>
    );
}
