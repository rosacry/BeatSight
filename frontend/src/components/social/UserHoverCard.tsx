/**
 * User Hover Card - osu!-style user popup tooltip
 * 
 * Shows a popup card when hovering over a username with:
 * - Avatar and cover image
 * - Display name and online status
 * - Karma score and rank badge
 * - Quick action buttons (message, add friend)
 * 
 * Similar to osu!'s user card tooltip system.
 */

import { useState, useRef, useEffect, useCallback, type ReactElement } from 'react'
import { createPortal } from 'react-dom'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { API_CONFIG } from '@/lib/config'
import { Avatar } from '@/components/ui/Avatar'
import { KarmaRankBadge, getKarmaRank } from '@/pages/LeaderboardPage'

// =============================================================================
// Types
// =============================================================================

interface UserHoverCardData {
    id: string
    user_number: number
    display_name: string
    avatar_url: string | null
    banner_url: string | null
    karma_score: number
    is_online: boolean
    last_active: string | null
    role: string
    country_code: string | null
}

interface UserHoverCardProps {
    /** User ID or user number to fetch data for */
    userId: string | number
    /** The element that triggers the hover card */
    children: ReactElement
    /** Placement relative to trigger */
    placement?: 'top' | 'bottom' | 'left' | 'right'
    /** Delay before showing (ms) */
    showDelay?: number
    /** Delay before hiding (ms) */
    hideDelay?: number
    /** Whether the hover card is disabled */
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
    cardRect: DOMRect,
    placement: Placement,
    offset: number = 8
): Position {
    const viewportWidth = window.innerWidth
    const viewportHeight = window.innerHeight

    let top = 0
    let left = 0
    let actualPlacement = placement

    // Calculate initial position based on placement
    switch (placement) {
        case 'top':
            top = triggerRect.top - cardRect.height - offset
            left = triggerRect.left + triggerRect.width / 2 - cardRect.width / 2
            break
        case 'bottom':
            top = triggerRect.bottom + offset
            left = triggerRect.left + triggerRect.width / 2 - cardRect.width / 2
            break
        case 'left':
            top = triggerRect.top + triggerRect.height / 2 - cardRect.height / 2
            left = triggerRect.left - cardRect.width - offset
            break
        case 'right':
            top = triggerRect.top + triggerRect.height / 2 - cardRect.height / 2
            left = triggerRect.right + offset
            break
    }

    // Flip placement if out of viewport
    if (placement === 'top' && top < 0) {
        top = triggerRect.bottom + offset
        actualPlacement = 'bottom'
    } else if (placement === 'bottom' && top + cardRect.height > viewportHeight) {
        top = triggerRect.top - cardRect.height - offset
        actualPlacement = 'top'
    } else if (placement === 'left' && left < 0) {
        left = triggerRect.right + offset
        actualPlacement = 'right'
    } else if (placement === 'right' && left + cardRect.width > viewportWidth) {
        left = triggerRect.left - cardRect.width - offset
        actualPlacement = 'left'
    }

    // Ensure card stays within horizontal bounds
    if (left < 8) left = 8
    if (left + cardRect.width > viewportWidth - 8) {
        left = viewportWidth - cardRect.width - 8
    }

    // Add scroll offset
    top += window.scrollY
    left += window.scrollX

    return { top, left, actualPlacement }
}

// =============================================================================
// Icons
// =============================================================================

function MessageIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
        </svg>
    )
}

function UserPlusIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
        </svg>
    )
}

function BellIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>
    )
}

// =============================================================================
// User Hover Card Component
// =============================================================================

export function UserHoverCard({
    userId,
    children,
    placement = 'right',
    showDelay = 300,
    hideDelay = 200,
    disabled = false,
}: UserHoverCardProps) {
    const [isVisible, setIsVisible] = useState(false)
    const [position, setPosition] = useState<Position>({ top: 0, left: 0, actualPlacement: placement })
    const triggerRef = useRef<HTMLElement | null>(null)
    const cardRef = useRef<HTMLDivElement>(null)
    const showTimeoutRef = useRef<ReturnType<typeof setTimeout>>()
    const hideTimeoutRef = useRef<ReturnType<typeof setTimeout>>()
    const isHoveringCardRef = useRef(false)

    // Fetch user data on hover
    const { data: userData, isLoading } = useQuery({
        queryKey: ['user-hover-card', userId],
        queryFn: async () => {
            const response = await fetch(`${API_CONFIG.baseUrl}/api/users/${userId}/hover-card`)
            if (!response.ok) {
                // Fallback to basic profile endpoint
                const fallbackResponse = await fetch(`${API_CONFIG.baseUrl}/api/users/${userId}/profile`)
                if (!fallbackResponse.ok) throw new Error('Failed to fetch user')
                const data = await fallbackResponse.json()
                return {
                    ...data,
                    is_online: false,
                } as UserHoverCardData
            }
            return response.json() as Promise<UserHoverCardData>
        },
        enabled: isVisible, // Only fetch when visible
        staleTime: 60000, // Cache for 1 minute
    })

    const show = useCallback(() => {
        if (disabled) return
        // Cancel any pending hide
        if (hideTimeoutRef.current) {
            clearTimeout(hideTimeoutRef.current)
            hideTimeoutRef.current = undefined
        }
        showTimeoutRef.current = setTimeout(() => setIsVisible(true), showDelay)
    }, [disabled, showDelay])

    const hide = useCallback(() => {
        // Cancel any pending show
        if (showTimeoutRef.current) {
            clearTimeout(showTimeoutRef.current)
            showTimeoutRef.current = undefined
        }
        // Only hide if not hovering the card
        hideTimeoutRef.current = setTimeout(() => {
            if (!isHoveringCardRef.current) {
                setIsVisible(false)
            }
        }, hideDelay)
    }, [hideDelay])

    const handleCardMouseEnter = useCallback(() => {
        isHoveringCardRef.current = true
        if (hideTimeoutRef.current) {
            clearTimeout(hideTimeoutRef.current)
            hideTimeoutRef.current = undefined
        }
    }, [])

    const handleCardMouseLeave = useCallback(() => {
        isHoveringCardRef.current = false
        hide()
    }, [hide])

    // Update position when visible
    useEffect(() => {
        if (!isVisible || !triggerRef.current || !cardRef.current) return

        const updatePosition = () => {
            if (triggerRef.current && cardRef.current) {
                const triggerRect = triggerRef.current.getBoundingClientRect()
                const cardRect = cardRef.current.getBoundingClientRect()
                const newPosition = calculatePosition(triggerRect, cardRect, placement)
                setPosition(newPosition)
            }
        }

        // Initial position
        updatePosition()

        // Update on scroll/resize
        window.addEventListener('scroll', updatePosition, true)
        window.addEventListener('resize', updatePosition)

        return () => {
            window.removeEventListener('scroll', updatePosition, true)
            window.removeEventListener('resize', updatePosition)
        }
    }, [isVisible, placement, userData])

    // Cleanup timeouts
    useEffect(() => {
        return () => {
            if (showTimeoutRef.current) clearTimeout(showTimeoutRef.current)
            if (hideTimeoutRef.current) clearTimeout(hideTimeoutRef.current)
        }
    }, [])

    // Clone children to add event handlers
    const trigger = (
        <span
            ref={(el) => { triggerRef.current = el }}
            onMouseEnter={show}
            onMouseLeave={hide}
            onFocus={show}
            onBlur={hide}
            style={{ display: 'inline' }}
        >
            {children}
        </span>
    )

    const karmaRank = userData ? getKarmaRank(userData.karma_score) : null

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

    const card = isVisible && createPortal(
        <div
            ref={cardRef}
            onMouseEnter={handleCardMouseEnter}
            onMouseLeave={handleCardMouseLeave}
            className="fixed z-[9999] w-[320px]"
            style={{
                top: position.top,
                left: position.left,
                ...getAnimationStyles(),
            }}
        >
            <div className="relative overflow-hidden rounded-xl bg-dark-500 border border-white/10 shadow-2xl shadow-black/50">
                {/* Cover/Banner */}
                <div
                    className="h-20 bg-gradient-to-br from-primary-600/40 to-accent-600/40"
                    style={userData?.banner_url ? {
                        backgroundImage: `url(${userData.banner_url})`,
                        backgroundSize: 'cover',
                        backgroundPosition: 'center',
                    } : undefined}
                />

                {/* Main Content */}
                <div className="relative px-4 pb-4">
                    {/* Avatar - positioned to overlap banner */}
                    <div className="absolute -top-8 left-4">
                        <div className="relative">
                            {isLoading ? (
                                <div className="w-16 h-16 rounded-full bg-dark-400 animate-pulse ring-4 ring-dark-500" />
                            ) : (
                                <Avatar
                                    src={userData?.avatar_url || undefined}
                                    alt={userData?.display_name || 'User'}
                                    size="lg"
                                    className="ring-4 ring-dark-500"
                                />
                            )}
                            {/* Online indicator */}
                            {userData?.is_online && (
                                <div className="absolute bottom-0 right-0 w-4 h-4 bg-green-500 rounded-full ring-2 ring-dark-500" />
                            )}
                        </div>
                    </div>

                    {/* User Info */}
                    <div className="pt-10">
                        {isLoading ? (
                            <div className="space-y-2">
                                <div className="h-5 w-24 bg-dark-400 animate-pulse rounded" />
                                <div className="h-4 w-16 bg-dark-400 animate-pulse rounded" />
                            </div>
                        ) : userData ? (
                            <>
                                {/* Name and flags */}
                                <div className="flex items-center gap-2 mb-1">
                                    <Link
                                        to={`/user/${userData.user_number || userData.id}`}
                                        className="text-lg font-bold text-white hover:text-primary-400 transition-colors"
                                    >
                                        {userData.display_name}
                                    </Link>
                                    {userData.country_code && (
                                        <span className={`fi fi-${userData.country_code.toLowerCase()}`} />
                                    )}
                                </div>

                                {/* Online status */}
                                <div className="flex items-center gap-2 text-sm mb-3">
                                    <span className={`flex items-center gap-1.5 ${userData.is_online ? 'text-green-400' : 'text-gray-500'}`}>
                                        <span className={`w-2 h-2 rounded-full ${userData.is_online ? 'bg-green-400' : 'bg-gray-500'}`} />
                                        {userData.is_online ? 'Online' : 'Offline'}
                                    </span>
                                </div>

                                {/* Karma and Rank */}
                                <div className="flex items-center gap-3 py-2 px-3 bg-dark-400/50 rounded-lg mb-3">
                                    <div className="flex items-center gap-2">
                                        <svg className="w-4 h-4 text-yellow-400" fill="currentColor" viewBox="0 0 24 24">
                                            <path d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                                        </svg>
                                        <span className="font-bold text-white">{userData.karma_score.toLocaleString()}</span>
                                    </div>
                                    <KarmaRankBadge karma={userData.karma_score} />
                                </div>

                                {/* Action Buttons */}
                                <div className="flex items-center gap-2">
                                    <Link
                                        to={`/messages/${userData.id}`}
                                        className="flex items-center justify-center w-9 h-9 rounded-lg bg-dark-400 hover:bg-primary-500/20 text-gray-400 hover:text-primary-400 transition-colors"
                                        title="Send Message"
                                    >
                                        <MessageIcon className="w-5 h-5" />
                                    </Link>
                                    <button
                                        className="flex items-center justify-center w-9 h-9 rounded-lg bg-dark-400 hover:bg-green-500/20 text-gray-400 hover:text-green-400 transition-colors"
                                        title="Add Friend"
                                    >
                                        <UserPlusIcon className="w-5 h-5" />
                                    </button>
                                    <button
                                        className="flex items-center justify-center w-9 h-9 rounded-lg bg-dark-400 hover:bg-yellow-500/20 text-gray-400 hover:text-yellow-400 transition-colors"
                                        title="Subscribe to Updates"
                                    >
                                        <BellIcon className="w-5 h-5" />
                                    </button>
                                </div>
                            </>
                        ) : (
                            <div className="text-center py-4 text-gray-400">
                                User not found
                            </div>
                        )}
                    </div>
                </div>

                {/* Bottom accent bar based on karma rank */}
                {karmaRank && karmaRank.name !== 'Unranked' && (
                    <div className={`h-1 ${karmaRank.bgColor.replace('/20', '/60')}`} />
                )}
            </div>
        </div>,
        document.body
    )

    return (
        <>
            {trigger}
            {card}
        </>
    )
}
