/**
 * Karma Breakdown Tooltip
 * 
 * Shows a detailed breakdown of karma sources when hovering over a karma score.
 * Displays where the user's karma comes from (maps, contributions, verification, etc.)
 */

import { useState, useRef, useEffect, useCallback, type ReactElement } from 'react'
import { createPortal } from 'react-dom'
import { useQuery } from '@tanstack/react-query'
import { API_CONFIG } from '@/lib/config'
import { getKarmaRank } from '@/pages/LeaderboardPage'

// =============================================================================
// Types
// =============================================================================

interface KarmaBreakdownData {
    current_score: number
    rank: number
    breakdown: Array<{
        reason: string
        total: number
        count: number
    }>
}

interface KarmaBreakdownTooltipProps {
    /** User ID to fetch breakdown for */
    userId: string
    /** Current karma score (for display while loading) */
    karmaScore: number
    /** The element that triggers the tooltip */
    children: ReactElement
    /** Placement relative to trigger */
    placement?: 'top' | 'bottom' | 'left' | 'right'
    /** Delay before showing (ms) */
    showDelay?: number
    /** Whether the tooltip is disabled */
    disabled?: boolean
}

// =============================================================================
// Position Calculation
// =============================================================================

type Placement = 'top' | 'bottom' | 'left' | 'right'

interface Position {
    top: number
    left: number
    actualPlacement: Placement
}

function calculatePosition(
    triggerRect: DOMRect,
    tooltipRect: DOMRect,
    placement: Placement,
    offset: number = 8
): Position {
    const viewportWidth = window.innerWidth
    const viewportHeight = window.innerHeight

    let top = 0
    let left = 0
    let actualPlacement = placement

    switch (placement) {
        case 'top':
            top = triggerRect.top - tooltipRect.height - offset
            left = triggerRect.left + triggerRect.width / 2 - tooltipRect.width / 2
            break
        case 'bottom':
            top = triggerRect.bottom + offset
            left = triggerRect.left + triggerRect.width / 2 - tooltipRect.width / 2
            break
        case 'left':
            top = triggerRect.top + triggerRect.height / 2 - tooltipRect.height / 2
            left = triggerRect.left - tooltipRect.width - offset
            break
        case 'right':
            top = triggerRect.top + triggerRect.height / 2 - tooltipRect.height / 2
            left = triggerRect.right + offset
            break
    }

    // Flip placement if out of viewport
    if (placement === 'top' && top < 0) {
        top = triggerRect.bottom + offset
        actualPlacement = 'bottom'
    } else if (placement === 'bottom' && top + tooltipRect.height > viewportHeight) {
        top = triggerRect.top - tooltipRect.height - offset
        actualPlacement = 'top'
    } else if (placement === 'left' && left < 0) {
        left = triggerRect.right + offset
        actualPlacement = 'right'
    } else if (placement === 'right' && left + tooltipRect.width > viewportWidth) {
        left = triggerRect.left - tooltipRect.width - offset
        actualPlacement = 'left'
    }

    // Ensure stays within horizontal bounds
    if (left < 8) left = 8
    if (left + tooltipRect.width > viewportWidth - 8) {
        left = viewportWidth - tooltipRect.width - 8
    }

    // Add scroll offset
    top += window.scrollY
    left += window.scrollX

    return { top, left, actualPlacement }
}

// =============================================================================
// Reason Display Mapping
// =============================================================================

interface ReasonDisplayConfig {
    label: string
    icon: string
    colorClass: string
}

const REASON_DISPLAY: Record<string, ReasonDisplayConfig> = {
    // Map-related
    map_upvote: { label: 'Map Upvotes', icon: '👍', colorClass: 'text-green-400' },
    map_downvote: { label: 'Map Downvotes', icon: '👎', colorClass: 'text-red-400' },

    // Contribution-related
    contribution_approved: { label: 'Contributions Approved', icon: '✓', colorClass: 'text-green-400' },
    contribution_rejected: { label: 'Contributions Rejected', icon: '✗', colorClass: 'text-red-400' },
    fix_accepted: { label: 'Fixes Accepted', icon: '🔧', colorClass: 'text-green-400' },
    fix_rejected: { label: 'Fixes Rejected', icon: '🔧', colorClass: 'text-red-400' },

    // Verification
    verification_vote: { label: 'Verification Votes', icon: '🗳️', colorClass: 'text-blue-400' },
    verification_consensus: { label: 'Consensus Matches', icon: '🎯', colorClass: 'text-cyan-400' },
    verification_complete: { label: 'Verifications Completed', icon: '✅', colorClass: 'text-green-400' },
    verification_rejected: { label: 'Verifications Rejected', icon: '❌', colorClass: 'text-red-400' },

    // Forum
    forum_post_upvote: { label: 'Forum Post Upvotes', icon: '💬', colorClass: 'text-purple-400' },
    forum_post_downvote: { label: 'Forum Post Downvotes', icon: '💬', colorClass: 'text-red-400' },
    helpful_post: { label: 'Helpful Posts', icon: '💡', colorClass: 'text-yellow-400' },

    // Bonuses
    email_verified: { label: 'Email Verified', icon: '📧', colorClass: 'text-green-400' },
    phone_verified: { label: 'Phone Verified', icon: '📱', colorClass: 'text-green-400' },
    full_verification_bonus: { label: 'Full Verification Bonus', icon: '🎁', colorClass: 'text-yellow-400' },
    subscription_bonus: { label: 'Subscription Bonus', icon: '⭐', colorClass: 'text-amber-400' },

    // Admin
    admin_adjustment: { label: 'Admin Adjustment', icon: '⚙️', colorClass: 'text-gray-400' },

    // Other
    spam_penalty: { label: 'Spam Penalty', icon: '🚫', colorClass: 'text-red-400' },
    other: { label: 'Other', icon: '•', colorClass: 'text-gray-400' },
}

function getReasonDisplay(reason: string): ReasonDisplayConfig {
    return REASON_DISPLAY[reason] || {
        label: reason.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' '),
        icon: '•',
        colorClass: 'text-gray-400',
    }
}

// =============================================================================
// Karma Breakdown Tooltip Component
// =============================================================================

export function KarmaBreakdownTooltip({
    userId,
    karmaScore,
    children,
    placement = 'bottom',
    showDelay = 300,
    disabled = false,
}: KarmaBreakdownTooltipProps) {
    const [isVisible, setIsVisible] = useState(false)
    const [position, setPosition] = useState<Position>({ top: 0, left: 0, actualPlacement: placement })
    const triggerRef = useRef<HTMLElement | null>(null)
    const tooltipRef = useRef<HTMLDivElement>(null)
    const showTimeoutRef = useRef<ReturnType<typeof setTimeout>>()
    const hideTimeoutRef = useRef<ReturnType<typeof setTimeout>>()
    const isHoveringTooltipRef = useRef(false)

    // Fetch karma breakdown on hover
    const { data: breakdown, isLoading } = useQuery({
        queryKey: ['karma-breakdown', userId],
        queryFn: async () => {
            const response = await fetch(`${API_CONFIG.baseUrl}/api/karma/users/${userId}/stats`, {
                credentials: 'include',
            })
            if (!response.ok) throw new Error('Failed to fetch karma breakdown')
            return response.json() as Promise<KarmaBreakdownData>
        },
        enabled: isVisible, // Only fetch when visible
        staleTime: 60000, // Cache for 1 minute
    })

    const show = useCallback(() => {
        if (disabled) return
        if (hideTimeoutRef.current) {
            clearTimeout(hideTimeoutRef.current)
            hideTimeoutRef.current = undefined
        }
        showTimeoutRef.current = setTimeout(() => setIsVisible(true), showDelay)
    }, [disabled, showDelay])

    const hide = useCallback(() => {
        if (showTimeoutRef.current) {
            clearTimeout(showTimeoutRef.current)
            showTimeoutRef.current = undefined
        }
        hideTimeoutRef.current = setTimeout(() => {
            if (!isHoveringTooltipRef.current) {
                setIsVisible(false)
            }
        }, 150)
    }, [])

    const handleTooltipMouseEnter = useCallback(() => {
        isHoveringTooltipRef.current = true
        if (hideTimeoutRef.current) {
            clearTimeout(hideTimeoutRef.current)
            hideTimeoutRef.current = undefined
        }
    }, [])

    const handleTooltipMouseLeave = useCallback(() => {
        isHoveringTooltipRef.current = false
        hide()
    }, [hide])

    // Update position when visible
    useEffect(() => {
        if (!isVisible || !triggerRef.current || !tooltipRef.current) return

        const updatePosition = () => {
            if (triggerRef.current && tooltipRef.current) {
                const triggerRect = triggerRef.current.getBoundingClientRect()
                const tooltipRect = tooltipRef.current.getBoundingClientRect()
                const newPosition = calculatePosition(triggerRect, tooltipRect, placement)
                setPosition(newPosition)
            }
        }

        updatePosition()

        window.addEventListener('scroll', updatePosition, true)
        window.addEventListener('resize', updatePosition)

        return () => {
            window.removeEventListener('scroll', updatePosition, true)
            window.removeEventListener('resize', updatePosition)
        }
    }, [isVisible, placement, breakdown])

    // Cleanup timeouts
    useEffect(() => {
        return () => {
            if (showTimeoutRef.current) clearTimeout(showTimeoutRef.current)
            if (hideTimeoutRef.current) clearTimeout(hideTimeoutRef.current)
        }
    }, [])

    const karmaRank = getKarmaRank(karmaScore)

    // Filter and sort breakdown items
    const sortedBreakdown = breakdown?.breakdown
        .filter(item => item.total !== 0)
        .sort((a, b) => Math.abs(b.total) - Math.abs(a.total)) || []

    // Track if positioning is ready to avoid flash from initial render position
    const [isPositioned, setIsPositioned] = useState(false)

    // Reset positioning state when visibility changes
    useEffect(() => {
        if (!isVisible) {
            setIsPositioned(false)
        }
    }, [isVisible])

    // Mark as positioned after position is calculated
    useEffect(() => {
        if (isVisible && position.top !== 0) {
            // Small delay to ensure position is applied before animation
            const timer = setTimeout(() => setIsPositioned(true), 10)
            return () => clearTimeout(timer)
        }
    }, [isVisible, position.top])

    // Get animation styles
    const getAnimationStyles = () => ({
        opacity: isPositioned ? 1 : 0,
        transform: isPositioned ? 'scale(1)' : 'scale(0.98)',
        transition: 'opacity 0.2s ease-out, transform 0.2s ease-out',
    })

    const trigger = (
        <span
            ref={(el) => { triggerRef.current = el }}
            onMouseEnter={show}
            onMouseLeave={hide}
            onFocus={show}
            onBlur={hide}
            className="cursor-help"
            style={{ display: 'inline' }}
        >
            {children}
        </span>
    )

    const tooltip = isVisible && createPortal(
        <div
            ref={tooltipRef}
            onMouseEnter={handleTooltipMouseEnter}
            onMouseLeave={handleTooltipMouseLeave}
            className="fixed z-[9999] w-[280px]"
            style={{
                top: position.top,
                left: position.left,
                ...getAnimationStyles(),
            }}
        >
            <div className="rounded-xl bg-dark-500 border border-white/10 shadow-2xl shadow-black/50 overflow-hidden">
                {/* Header */}
                <div className={`px-4 py-3 ${karmaRank.bgColor} border-b border-white/10`}>
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <span className="text-lg">{karmaRank.icon}</span>
                            <span className={`font-bold ${karmaRank.color}`}>{karmaRank.name}</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                            <svg className="w-4 h-4 text-yellow-400" fill="currentColor" viewBox="0 0 24 24">
                                <path d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                            </svg>
                            <span className="font-bold text-white">{karmaScore.toLocaleString()}</span>
                        </div>
                    </div>
                </div>

                {/* Breakdown List */}
                <div className="px-4 py-3 max-h-[300px] overflow-y-auto">
                    {isLoading ? (
                        <div className="space-y-2">
                            {[1, 2, 3, 4].map(i => (
                                <div key={i} className="flex justify-between items-center">
                                    <div className="h-4 w-24 bg-dark-400 animate-pulse rounded" />
                                    <div className="h-4 w-12 bg-dark-400 animate-pulse rounded" />
                                </div>
                            ))}
                        </div>
                    ) : sortedBreakdown.length > 0 ? (
                        <div className="space-y-2">
                            {sortedBreakdown.map((item, idx) => {
                                const display = getReasonDisplay(item.reason)
                                const isPositive = item.total > 0
                                return (
                                    <div key={idx} className="flex justify-between items-center text-sm">
                                        <div className="flex items-center gap-2">
                                            <span className="w-5 text-center">{display.icon}</span>
                                            <span className="text-gray-300">{display.label}</span>
                                            {item.count > 1 && (
                                                <span className="text-xs text-gray-500">×{item.count}</span>
                                            )}
                                        </div>
                                        <span className={`font-medium tabular-nums ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
                                            {isPositive && '+'}{item.total.toLocaleString()}
                                        </span>
                                    </div>
                                )
                            })}
                        </div>
                    ) : (
                        <div className="text-center py-4 text-gray-500 text-sm">
                            No karma breakdown available
                        </div>
                    )}
                </div>

                {/* Footer */}
                {breakdown && breakdown.rank > 0 && (
                    <div className="px-4 py-2 bg-dark-400/50 border-t border-white/5 text-center">
                        <span className="text-xs text-gray-400">
                            Karma Ranking: <span className="text-white font-medium">#{breakdown.rank.toLocaleString()}</span>
                        </span>
                    </div>
                )}
            </div>
        </div>,
        document.body
    )

    return (
        <>
            {trigger}
            {tooltip}
        </>
    )
}

// =============================================================================
// Simple Karma Breakdown Display (for inline use without fetch)
// =============================================================================

interface KarmaSourceBreakdown {
    map_upvotes: number
    map_downvotes: number
    contributions_approved: number
    contributions_rejected: number
    verification_votes: number
    verification_consensus: number
    forum_activity: number
    verification_bonuses: number
    subscription_bonuses: number
    admin_adjustments: number
    other: number
}

interface StaticKarmaBreakdownTooltipProps {
    /** Pre-loaded breakdown data */
    breakdown: KarmaSourceBreakdown
    /** Total karma score */
    karmaScore: number
    /** The element that triggers the tooltip */
    children: ReactElement
    /** Placement relative to trigger */
    placement?: 'top' | 'bottom' | 'left' | 'right'
    /** Delay before showing (ms) */
    showDelay?: number
}

// Map static breakdown fields to display config
const STATIC_BREAKDOWN_DISPLAY: Array<{ key: keyof KarmaSourceBreakdown; label: string; icon: string }> = [
    { key: 'map_upvotes', label: 'Map Upvotes', icon: '👍' },
    { key: 'map_downvotes', label: 'Map Downvotes', icon: '👎' },
    { key: 'contributions_approved', label: 'Contributions Approved', icon: '✓' },
    { key: 'contributions_rejected', label: 'Contributions Rejected', icon: '✗' },
    { key: 'verification_votes', label: 'Verification Votes', icon: '🗳️' },
    { key: 'verification_consensus', label: 'Consensus Matches', icon: '🎯' },
    { key: 'forum_activity', label: 'Forum Activity', icon: '💬' },
    { key: 'verification_bonuses', label: 'Verification Bonuses', icon: '📧' },
    { key: 'subscription_bonuses', label: 'Subscription Bonus', icon: '⭐' },
    { key: 'admin_adjustments', label: 'Admin Adjustments', icon: '⚙️' },
    { key: 'other', label: 'Other', icon: '•' },
]

export function StaticKarmaBreakdownTooltip({
    breakdown,
    karmaScore,
    children,
    placement = 'bottom',
    showDelay = 200,
}: StaticKarmaBreakdownTooltipProps) {
    const [isVisible, setIsVisible] = useState(false)
    const [position, setPosition] = useState<Position>({ top: 0, left: 0, actualPlacement: placement })
    const triggerRef = useRef<HTMLElement | null>(null)
    const tooltipRef = useRef<HTMLDivElement>(null)
    const showTimeoutRef = useRef<ReturnType<typeof setTimeout>>()
    const hideTimeoutRef = useRef<ReturnType<typeof setTimeout>>()
    const isHoveringTooltipRef = useRef(false)

    const show = useCallback(() => {
        if (hideTimeoutRef.current) {
            clearTimeout(hideTimeoutRef.current)
            hideTimeoutRef.current = undefined
        }
        showTimeoutRef.current = setTimeout(() => setIsVisible(true), showDelay)
    }, [showDelay])

    const hide = useCallback(() => {
        if (showTimeoutRef.current) {
            clearTimeout(showTimeoutRef.current)
            showTimeoutRef.current = undefined
        }
        hideTimeoutRef.current = setTimeout(() => {
            if (!isHoveringTooltipRef.current) {
                setIsVisible(false)
            }
        }, 150)
    }, [])

    const handleTooltipMouseEnter = useCallback(() => {
        isHoveringTooltipRef.current = true
        if (hideTimeoutRef.current) {
            clearTimeout(hideTimeoutRef.current)
            hideTimeoutRef.current = undefined
        }
    }, [])

    const handleTooltipMouseLeave = useCallback(() => {
        isHoveringTooltipRef.current = false
        hide()
    }, [hide])

    useEffect(() => {
        if (!isVisible || !triggerRef.current || !tooltipRef.current) return

        const updatePosition = () => {
            if (triggerRef.current && tooltipRef.current) {
                const triggerRect = triggerRef.current.getBoundingClientRect()
                const tooltipRect = tooltipRef.current.getBoundingClientRect()
                const newPosition = calculatePosition(triggerRect, tooltipRect, placement)
                setPosition(newPosition)
            }
        }

        updatePosition()

        window.addEventListener('scroll', updatePosition, true)
        window.addEventListener('resize', updatePosition)

        return () => {
            window.removeEventListener('scroll', updatePosition, true)
            window.removeEventListener('resize', updatePosition)
        }
    }, [isVisible, placement])

    useEffect(() => {
        return () => {
            if (showTimeoutRef.current) clearTimeout(showTimeoutRef.current)
            if (hideTimeoutRef.current) clearTimeout(hideTimeoutRef.current)
        }
    }, [])

    const karmaRank = getKarmaRank(karmaScore)

    // Filter non-zero items and sort by absolute value
    const items = STATIC_BREAKDOWN_DISPLAY
        .map(config => ({ ...config, value: breakdown[config.key] }))
        .filter(item => item.value !== 0)
        .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))

    // Track if positioning is ready to avoid flash from initial render position
    const [isPositioned, setIsPositioned] = useState(false)

    // Reset positioning state when visibility changes
    useEffect(() => {
        if (!isVisible) {
            setIsPositioned(false)
        }
    }, [isVisible])

    // Mark as positioned after position is calculated
    useEffect(() => {
        if (isVisible && position.top !== 0) {
            const timer = setTimeout(() => setIsPositioned(true), 10)
            return () => clearTimeout(timer)
        }
    }, [isVisible, position.top])

    // Get animation styles
    const getAnimationStyles = () => ({
        opacity: isPositioned ? 1 : 0,
        transform: isPositioned ? 'scale(1)' : 'scale(0.98)',
        transition: 'opacity 0.2s ease-out, transform 0.2s ease-out',
    })

    const trigger = (
        <span
            ref={(el) => { triggerRef.current = el }}
            onMouseEnter={show}
            onMouseLeave={hide}
            onFocus={show}
            onBlur={hide}
            className="cursor-help"
            style={{ display: 'inline' }}
        >
            {children}
        </span>
    )

    const tooltip = isVisible && createPortal(
        <div
            ref={tooltipRef}
            onMouseEnter={handleTooltipMouseEnter}
            onMouseLeave={handleTooltipMouseLeave}
            className="fixed z-[9999] w-[260px]"
            style={{
                top: position.top,
                left: position.left,
                ...getAnimationStyles(),
            }}
        >
            <div className="rounded-xl bg-dark-500 border border-white/10 shadow-2xl shadow-black/50 overflow-hidden">
                {/* Header */}
                <div className={`px-3 py-2 ${karmaRank.bgColor} border-b border-white/10`}>
                    <div className="flex items-center justify-between">
                        <span className={`text-sm font-medium ${karmaRank.color}`}>
                            {karmaRank.icon} {karmaRank.name}
                        </span>
                        <span className="font-bold text-white">{karmaScore.toLocaleString()}</span>
                    </div>
                </div>

                {/* Breakdown List */}
                <div className="px-3 py-2">
                    {items.length > 0 ? (
                        <div className="space-y-1.5">
                            {items.map((item, idx) => {
                                const isPositive = item.value > 0
                                return (
                                    <div key={idx} className="flex justify-between items-center text-xs">
                                        <div className="flex items-center gap-1.5">
                                            <span className="w-4 text-center">{item.icon}</span>
                                            <span className="text-gray-400">{item.label}</span>
                                        </div>
                                        <span className={`font-medium tabular-nums ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
                                            {isPositive && '+'}{item.value.toLocaleString()}
                                        </span>
                                    </div>
                                )
                            })}
                        </div>
                    ) : (
                        <div className="text-center py-2 text-gray-500 text-xs">
                            No karma activity yet
                        </div>
                    )}
                </div>
            </div>
        </div>,
        document.body
    )

    return (
        <>
            {trigger}
            {tooltip}
        </>
    )
}
