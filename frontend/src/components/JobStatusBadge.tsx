import { clsx } from 'clsx'
import type { AIJobState } from '@/types/api'

interface JobStatusBadgeProps {
    state: AIJobState
    className?: string
}

const stateConfig: Record<AIJobState, { label: string; color: string }> = {
    queued: { label: 'Queued', color: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30' },
    processing: { label: 'Processing', color: 'bg-blue-500/20 text-blue-400 border-blue-500/30' },
    complete: { label: 'Complete', color: 'bg-green-500/20 text-green-400 border-green-500/30' },
    failed: { label: 'Failed', color: 'bg-red-500/20 text-red-400 border-red-500/30' },
    cancelled: { label: 'Cancelled', color: 'bg-gray-500/20 text-gray-400 border-gray-500/30' },
}

export function JobStatusBadge({ state, className }: JobStatusBadgeProps) {
    const config = stateConfig[state]

    return (
        <span
            className={clsx(
                'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border',
                config.color,
                className
            )}
        >
            {state === 'processing' && (
                <span className="w-2 h-2 bg-blue-400 rounded-full mr-1.5 animate-pulse" />
            )}
            {config.label}
        </span>
    )
}
