/**
 * CreditBalance - displays user's credit balance in the nav bar.
 * Only shown when user has credits > 0.
 */

import { useCreditCount } from '@/hooks/useCredits'

interface CreditBalanceProps {
    onClick?: () => void
    className?: string
    showWhenZero?: boolean
}

export function CreditBalance({
    onClick,
    className = '',
    showWhenZero = false,
}: CreditBalanceProps) {
    const { credits, isLoading } = useCreditCount()

    // Don't show if no credits and showWhenZero is false
    if (!showWhenZero && credits === 0 && !isLoading) {
        return null
    }

    return (
        <button
            onClick={onClick}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full 
                  bg-primary-500/10 border border-primary-500/30 
                  hover:bg-primary-500/20 transition-colors ${className}`}
            title="Credit balance - click to buy more"
        >
            {/* Credit coin icon */}
            <svg
                className="w-4 h-4 text-primary-400"
                fill="currentColor"
                viewBox="0 0 20 20"
            >
                <path d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" />
            </svg>

            {/* Balance */}
            {isLoading ? (
                <span className="text-sm text-gray-400">...</span>
            ) : (
                <span className="text-sm font-medium text-primary-300">
                    {credits}
                </span>
            )}
        </button>
    )
}

/**
 * Compact credit badge for inline use.
 */
export function CreditBadge({ credits }: { credits: number }) {
    if (credits === 0) return null

    return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium 
                     bg-primary-500/20 text-primary-300 rounded-full">
            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                <path d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" />
            </svg>
            {credits}
        </span>
    )
}
