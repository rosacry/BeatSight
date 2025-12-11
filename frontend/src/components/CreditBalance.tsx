/**
 * CreditBalance - displays user's credit balance in the nav bar.
 * Only shown when user has credits > 0 (unless showWhenZero is true).
 */

import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCreditCount } from '@/hooks/useCredits'
import { Tooltip } from '@/components/ui/Tooltip'

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
    const navigate = useNavigate()
    const { credits, isLoading, isError } = useCreditCount()
    const [lastKnownCredits, setLastKnownCredits] = useState<number | null>(null)
    const hasEverHadCredits = useRef(false)

    // Track last known credits to prevent disappearing during refetch or errors
    useEffect(() => {
        if (!isLoading && !isError && credits !== undefined && credits > 0) {
            setLastKnownCredits(credits)
            hasEverHadCredits.current = true
        }
    }, [credits, isLoading, isError])

    // Use last known value during loading/error to prevent flicker
    const displayCredits = (isLoading || isError) && lastKnownCredits !== null
        ? lastKnownCredits
        : credits

    // Don't show if no credits and showWhenZero is false
    // But keep showing during loading/error if we had credits before
    // Also show during errors if we've ever had credits (to prevent disappearing)
    const shouldHide = !showWhenZero &&
        displayCredits === 0 &&
        !isLoading &&
        !isError &&
        !hasEverHadCredits.current

    // Handle click - use custom handler or navigate to pricing
    const handleClick = useCallback(() => {
        if (onClick) {
            onClick()
        } else {
            navigate('/pricing')
        }
    }, [onClick, navigate])

    if (shouldHide) {
        return null
    }

    return (
        <Tooltip
            content={
                <div className="text-center">
                    <div className="font-medium">Credit Balance</div>
                    <div className="text-gray-400 text-xs mt-1">Click to buy more credits</div>
                </div>
            }
        >
            <button
                onClick={handleClick}
                data-tour="credits"
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full 
                      bg-primary-500/10 border border-primary-500/30 
                      hover:bg-primary-500/20 hover:border-primary-400/50
                      active:scale-95
                      transition-all duration-200 ${className}`}
                aria-label={`${displayCredits} credits available. Click to buy more.`}
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
                {isLoading && lastKnownCredits === null ? (
                    <span className="text-sm text-gray-400 animate-pulse">...</span>
                ) : (
                    <span className="text-sm font-medium text-primary-300 tabular-nums">
                        {displayCredits}
                    </span>
                )}
            </button>
        </Tooltip>
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
