import { clsx } from 'clsx'

interface ProgressBarProps {
    percent: number
    message?: string | null
    stage?: string | null
    className?: string
    showLabel?: boolean
}

export function ProgressBar({
    percent,
    message,
    stage,
    className,
    showLabel = true,
}: ProgressBarProps) {
    const clampedPercent = Math.max(0, Math.min(100, percent))

    return (
        <div className={clsx('w-full', className)}>
            {showLabel && (
                <div className="flex justify-between items-center mb-1">
                    <span className="text-sm text-gray-400">
                        {stage && <span className="text-primary-400">{stage}: </span>}
                        {message || 'Processing...'}
                    </span>
                    <span className="text-sm font-medium text-white">{clampedPercent}%</span>
                </div>
            )}

            <div className="w-full bg-dark-300 rounded-full h-2 overflow-hidden">
                <div
                    className={clsx(
                        'h-full rounded-full transition-all duration-300 ease-out',
                        clampedPercent < 100 ? 'bg-primary-500' : 'bg-green-500'
                    )}
                    style={{ width: `${clampedPercent}%` }}
                />
            </div>
        </div>
    )
}

interface IndeterminateProgressBarProps {
    message?: string
    className?: string
}

export function IndeterminateProgressBar({
    message = 'Loading...',
    className,
}: IndeterminateProgressBarProps) {
    return (
        <div className={clsx('w-full', className)}>
            <div className="flex justify-between items-center mb-1">
                <span className="text-sm text-gray-400">{message}</span>
            </div>

            <div className="w-full bg-dark-300 rounded-full h-2 overflow-hidden relative">
                <div className="absolute inset-0 bg-primary-500/50 animate-progress" />
            </div>
        </div>
    )
}
