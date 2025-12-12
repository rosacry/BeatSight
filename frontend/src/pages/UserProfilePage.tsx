/**
 * Public User Profile Page - osu! inspired profile display
 * 
 * Shows detailed user information when viewing another user's profile.
 * Features:
 * - Profile banner/cover
 * - Avatar and user info
 * - Stats display (karma, maps, achievements)
 * - Tabs for different sections
 * - Action buttons (message, block, report)
 */

import { useState } from 'react'
import { useParams, Link, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { clsx } from 'clsx'
import { format } from 'date-fns'
import { useAuthStore } from '@/stores/authStore'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { API_CONFIG } from '@/lib/config'
import { Button } from '@/components/ui/Button'
import { Modal, ModalHeader, ModalBody, ModalFooter } from '@/components/ui/Modal'
import { useBlockUser, useUnblockUser, useReportUser, useFriendshipStatus, useSubscriptionStatus, useAddFriend, useRemoveFriend, useSubscribeToUser, useUnsubscribeFromUser } from '@/api/socialHooks'
import type { ReportType } from '@/api/social'
import {
    AnimatedTabContent,
    AnimatedTabButton,
    StaggerPageContent,
    StaggerSection,
    PageContentWrapper
} from '@/components/ui/UnifiedTransitions'
import { KarmaBreakdownTooltip } from '@/components/social'
import { BannerUpload } from '@/components/BannerUpload'
import { AvatarUpload } from '@/components/AvatarUpload'

// =============================================================================
// Types
// =============================================================================

// Profile tag (like osu!'s DEV, VIP, etc.)
interface ProfileTag {
    id: number
    name: string
    background_color: string
    text_color: string | null
}

interface PublicUserProfile {
    id: string
    user_number: number  // Human-friendly ID like osu! (e.g., 1)
    display_name: string
    avatar_url: string | null
    banner_url: string | null
    karma_score: number
    created_at: string
    role: string
    is_verified: boolean
    country_code: string | null
    bio: string | null
    // Custom profile tags (like osu!'s DEV, VIP, etc.)
    tags: ProfileTag[]
    // Leaderboard rankings (null if hidden)
    karma_rank: number | null
    contribution_rank: number | null
    // Stats
    songs_uploaded: number
    maps_generated: number
    maps_verified: number
    achievements_count: number
    forum_posts: number
    contribution_count: number
    // Recent activity
    last_active: string | null
}

interface UserMap {
    id: string
    song_id: string
    title: string
    artist: string
    cover_url: string | null
    is_verified: boolean
    created_at: string
    play_count: number
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

function BlockIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
        </svg>
    )
}

function FlagIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 21v-4m0 0V5a2 2 0 012-2h6.5l1 1H21l-3 6 3 6h-8.5l-1-1H5a2 2 0 00-2 2zm9-13.5V9" />
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

function UserCheckIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 11l2 2 4-4" />
        </svg>
    )
}

function UsersIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
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

function BellFilledIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 22c1.1 0 2-.9 2-2h-4a2 2 0 002 2zm6-6v-5c0-3.07-1.64-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z" />
        </svg>
    )
}

function StarIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
        </svg>
    )
}

function VerifiedIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="currentColor" viewBox="0 0 24 24">
            <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z" />
        </svg>
    )
}

function CalendarIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
    )
}

function MapIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
        </svg>
    )
}

function TrophyIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
        </svg>
    )
}

// =============================================================================
// Stat Item Component (osu!-style)
// =============================================================================

interface StatItemProps {
    value: number
    label: string
    color?: string
}

function StatItem({ value, label, color = 'text-white' }: StatItemProps) {
    return (
        <div className="text-center">
            <div className={clsx('text-2xl font-bold', color)}>
                {value.toLocaleString()}
            </div>
            <div className="text-sm text-gray-400 mt-0.5">{label}</div>
        </div>
    )
}

// =============================================================================
// Profile Page Component
// =============================================================================

const VALID_TABS = ['overview', 'beatmaps', 'achievements', 'activity'] as const
type ProfileTab = typeof VALID_TABS[number]

function getTabFromUrl(searchParams: URLSearchParams): ProfileTab {
    const tab = searchParams.get('tab')
    if (tab && (VALID_TABS as readonly string[]).includes(tab)) {
        return tab as ProfileTab
    }
    return 'overview'
}

export function UserProfilePage() {
    const { userId } = useParams<{ userId: string }>()
    const [searchParams, setSearchParams] = useSearchParams()
    const currentUser = useAuthStore((s) => s.user)
    const accessToken = useAuthStore((s) => s.accessToken)
    const isAuthenticated = useAuthStore((s) => s.isAuthenticated())

    const activeTab = getTabFromUrl(searchParams)
    const [showReportModal, setShowReportModal] = useState(false)
    const [isBlocked, setIsBlocked] = useState(false)

    const blockUser = useBlockUser()
    const unblockUser = useUnblockUser()

    // Is viewing own profile? (check both UUID and user_number)
    const isOwnProfile = currentUser?.id === userId ||
        (currentUser?.user_number !== undefined && String(currentUser.user_number) === userId)

    // Fetch user profile
    const { data: profile, isLoading, error } = useQuery<PublicUserProfile>({
        queryKey: ['user-profile', userId],
        queryFn: async () => {
            const headers: Record<string, string> = {}
            if (accessToken) {
                headers['Authorization'] = `Bearer ${accessToken}`
            }
            const response = await fetch(
                `${API_CONFIG.baseUrl}/api/users/${userId}/profile`,
                { headers }
            )
            if (!response.ok) {
                throw new Error('User not found')
            }
            return response.json()
        },
        enabled: !!userId,
    })

    // Friend/subscription hooks - enabled only when profile is loaded and viewing other user
    const { data: friendshipStatus } = useFriendshipStatus(
        profile && !isOwnProfile && isAuthenticated ? profile.id : undefined
    )
    const { data: subscriptionStatus } = useSubscriptionStatus(
        profile && !isOwnProfile && isAuthenticated ? profile.id : undefined
    )
    const addFriend = useAddFriend()
    const removeFriend = useRemoveFriend()
    const subscribeToUser = useSubscribeToUser()
    const unsubscribeFromUser = useUnsubscribeFromUser()

    // Fetch user's beatmaps
    const { data: userMaps } = useQuery<UserMap[]>({
        queryKey: ['user-maps', userId],
        queryFn: async () => {
            const response = await fetch(
                `${API_CONFIG.baseUrl}/api/users/${userId}/maps`
            )
            if (!response.ok) return []
            const data = await response.json()
            return data.items || []
        },
        enabled: !!userId && activeTab === 'beatmaps',
    })

    // Set document title
    useDocumentTitle(
        isOwnProfile
            ? 'My Profile'
            : profile?.display_name
                ? `${profile.display_name}'s Profile`
                : 'User Profile'
    )

    const handleTabChange = (tab: ProfileTab) => {
        setSearchParams({ tab }, { replace: true })
    }

    const handleFriendClick = async () => {
        if (!profile) return
        try {
            if (friendshipStatus?.is_following) {
                await removeFriend.mutateAsync(profile.id)
            } else {
                await addFriend.mutateAsync(profile.id)
            }
        } catch (err) {
            console.error('Failed to update friend status:', err)
        }
    }

    const handleSubscribeClick = async () => {
        if (!profile) return
        try {
            if (subscriptionStatus?.is_subscribed) {
                await unsubscribeFromUser.mutateAsync(profile.id)
            } else {
                await subscribeToUser.mutateAsync({ userId: profile.id })
            }
        } catch (err) {
            console.error('Failed to update subscription:', err)
        }
    }

    const handleBlock = async () => {
        if (!userId) return
        try {
            await blockUser.mutateAsync({ userId })
            setIsBlocked(true)
        } catch (err) {
            console.error('Failed to block user:', err)
        }
    }

    const handleUnblock = async () => {
        if (!userId) return
        try {
            await unblockUser.mutateAsync(userId)
            setIsBlocked(false)
        } catch (err) {
            console.error('Failed to unblock user:', err)
        }
    }

    if (isLoading) {
        return (
            <PageContentWrapper isLoading className="min-h-screen">
                <div className="flex items-center justify-center h-96">
                    <div className="w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
                </div>
            </PageContentWrapper>
        )
    }

    if (error || !profile) {
        return (
            <PageContentWrapper className="min-h-screen">
                <div className="max-w-4xl mx-auto px-4 py-16 text-center">
                    <div className="w-24 h-24 mx-auto mb-6 rounded-full bg-dark-400 flex items-center justify-center">
                        <svg className="w-12 h-12 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                        </svg>
                    </div>
                    <h1 className="text-2xl font-bold text-white mb-2">User Not Found</h1>
                    <p className="text-gray-400 mb-6">
                        This user doesn't exist or has been removed.
                    </p>
                    <Link to="/" className="btn btn-primary">
                        Go Home
                    </Link>
                </div>
            </PageContentWrapper>
        )
    }

    return (
        <PageContentWrapper className="min-h-screen bg-dark-600">
            {/* osu!-style Profile Header with Banner */}
            <div className="relative">
                {/* Banner Image - Larger, more prominent like osu! */}
                <div
                    className="h-56 md:h-72 lg:h-80 bg-cover bg-center relative overflow-hidden"
                    style={profile.banner_url ? { backgroundImage: `url(${profile.banner_url})` } : undefined}
                >
                    {/* Default gradient background if no banner */}
                    {!profile.banner_url && (
                        <div className="absolute inset-0 bg-gradient-to-br from-primary-900/60 via-dark-500 to-dark-600" />
                    )}

                    {/* Overlay gradient for readability */}
                    <div className="absolute inset-0 bg-gradient-to-t from-dark-600 via-dark-600/60 to-transparent" />
                    <div className="absolute inset-0 bg-gradient-to-r from-dark-600/40 to-transparent" />

                    {/* Banner Upload overlay for own profile - positioned in corner like osu! */}
                    {isOwnProfile && (
                        <BannerUpload
                            currentBannerUrl={profile.banner_url}
                            onUploadSuccess={() => {
                                window.location.reload()
                            }}
                            className="absolute inset-0 z-10"
                        />
                    )}
                </div>

                {/* Profile Info Card - Overlapping banner like osu! */}
                <div className="max-w-5xl mx-auto px-4 sm:px-6 relative">
                    <div className="relative -mt-32 md:-mt-36 z-20">
                        <div className="bg-dark-500/90 backdrop-blur-sm rounded-2xl border border-white/5 shadow-2xl overflow-hidden">
                            <div className="p-6 md:p-8">
                                <div className="flex flex-col md:flex-row gap-6">
                                    {/* Avatar Section */}
                                    <div className="flex-shrink-0">
                                        {isOwnProfile ? (
                                            <AvatarUpload
                                                currentAvatarUrl={profile.avatar_url}
                                                size="lg"
                                                hoverHint="change your avatar!"
                                                showUploadHint={false}
                                                onUploadSuccess={() => {
                                                    window.location.reload()
                                                }}
                                            />
                                        ) : (
                                            <div className="w-28 h-28 md:w-32 md:h-32 rounded-2xl overflow-hidden bg-dark-400 shadow-xl ring-4 ring-dark-500">
                                                {profile.avatar_url ? (
                                                    <img
                                                        src={profile.avatar_url}
                                                        alt={profile.display_name}
                                                        className="w-full h-full object-cover"
                                                    />
                                                ) : (
                                                    <div className="w-full h-full bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center">
                                                        <span className="text-4xl font-bold text-white">
                                                            {profile.display_name?.charAt(0).toUpperCase()}
                                                        </span>
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>

                                    {/* User Info */}
                                    <div className="flex-1 min-w-0">
                                        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
                                            {/* Name and badges */}
                                            <div>
                                                <div className="flex items-center gap-3 flex-wrap">
                                                    <h1 className="text-2xl md:text-3xl font-bold text-white truncate">
                                                        {profile.display_name}
                                                    </h1>
                                                    {profile.role && profile.role !== 'user' && (
                                                        <span className={clsx(
                                                            'px-2.5 py-1 text-xs font-bold rounded uppercase',
                                                            profile.role === 'admin' ? 'bg-red-500 text-white' :
                                                                profile.role === 'staff' ? 'bg-amber-500 text-dark-600' :
                                                                    profile.role === 'verifier' ? 'bg-green-500 text-dark-600' :
                                                                        'bg-gray-500 text-white'
                                                        )}>
                                                            {profile.role}
                                                        </span>
                                                    )}
                                                    {/* Custom profile tags (like osu!'s DEV, VIP, etc.) */}
                                                    {profile.tags?.map((tag) => (
                                                        <span
                                                            key={tag.id}
                                                            className="px-2.5 py-1 text-xs font-bold rounded"
                                                            style={{
                                                                backgroundColor: tag.background_color,
                                                                color: tag.text_color || '#ffffff',
                                                            }}
                                                        >
                                                            {tag.name}
                                                        </span>
                                                    ))}
                                                </div>

                                                {/* Meta info line */}
                                                <div className="flex items-center gap-4 mt-2 text-sm text-gray-400 flex-wrap">
                                                    {profile.country_code && (
                                                        <span className="flex items-center gap-1.5">
                                                            <span className={`fi fi-${profile.country_code.toLowerCase()}`} />
                                                            {profile.country_code}
                                                        </span>
                                                    )}
                                                    <span className="flex items-center gap-1.5">
                                                        <CalendarIcon className="w-4 h-4" />
                                                        Joined {format(new Date(profile.created_at), 'MMM yyyy')}
                                                    </span>
                                                    {profile.last_active && (
                                                        <span className="flex items-center gap-1.5 text-green-400">
                                                            <div className="w-2 h-2 bg-green-400 rounded-full" />
                                                            Online
                                                        </span>
                                                    )}
                                                </div>
                                            </div>

                                            {/* Karma Score - Large and prominent like osu!'s pp/rank display */}
                                            <div className="flex-shrink-0">
                                                <KarmaBreakdownTooltip userId={profile.id} karmaScore={profile.karma_score} placement="left">
                                                    <div className="text-right">
                                                        <div className="flex items-center gap-2 justify-end">
                                                            <StarIcon className="w-6 h-6 text-yellow-400" />
                                                            <span className="text-4xl font-bold text-white">
                                                                {profile.karma_score.toLocaleString()}
                                                            </span>
                                                        </div>
                                                        <p className="text-sm text-gray-400 mt-1">Karma</p>
                                                        {profile.karma_rank && (
                                                            <Link
                                                                to="/leaderboard?tab=karma"
                                                                className="inline-flex items-center gap-1 mt-2 px-3 py-1.5 bg-yellow-500/20 text-yellow-400 rounded-full text-sm font-bold hover:bg-yellow-500/30 transition-colors"
                                                            >
                                                                #{profile.karma_rank.toLocaleString()}
                                                            </Link>
                                                        )}
                                                    </div>
                                                </KarmaBreakdownTooltip>
                                            </div>
                                        </div>

                                        {/* Stats Row - Clean grid like osu! */}
                                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6 pt-6 border-t border-white/10">
                                            <StatItem
                                                value={profile.songs_uploaded}
                                                label="Songs"
                                                color="text-white"
                                            />
                                            <StatItem
                                                value={profile.maps_generated}
                                                label="Maps"
                                                color="text-primary-400"
                                            />
                                            <StatItem
                                                value={profile.maps_verified}
                                                label="Verified"
                                                color="text-green-400"
                                            />
                                            <StatItem
                                                value={profile.achievements_count}
                                                label="Achievements"
                                                color="text-yellow-400"
                                            />
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Action Buttons */}
            {isAuthenticated && (
                <div className="max-w-4xl mx-auto px-4 pb-6">
                    <div className="flex flex-wrap gap-3">
                        {isOwnProfile ? (
                            <>
                                {/* Own Profile Actions */}
                                <Link to="/upload">
                                    <Button variant="primary" size="md">
                                        <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                                        </svg>
                                        Upload Song
                                    </Button>
                                </Link>
                                <Link to="/library">
                                    <Button variant="secondary" size="md">
                                        <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                                        </svg>
                                        My Library
                                    </Button>
                                </Link>
                                <Link to="/settings">
                                    <Button variant="outline" size="md">
                                        <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                        </svg>
                                        Settings
                                    </Button>
                                </Link>
                            </>
                        ) : (
                            <>
                                {/* Other User Actions */}
                                <Link to={`/messages/${userId}`}>
                                    <Button variant="primary" size="md">
                                        <MessageIcon className="w-4 h-4 mr-2" />
                                        Message
                                    </Button>
                                </Link>

                                {/* Add Friend / Mutual Button */}
                                <Button
                                    variant={friendshipStatus?.is_mutual ? 'primary' : friendshipStatus?.is_following ? 'secondary' : 'outline'}
                                    size="md"
                                    onClick={handleFriendClick}
                                    disabled={addFriend.isPending || removeFriend.isPending}
                                    className={
                                        friendshipStatus?.is_mutual
                                            ? 'bg-purple-600 hover:bg-purple-700'
                                            : friendshipStatus?.is_following
                                                ? 'bg-green-600 hover:bg-green-700 hover:bg-red-600'
                                                : ''
                                    }
                                >
                                    {friendshipStatus?.is_mutual ? (
                                        <>
                                            <UsersIcon className="w-4 h-4 mr-2" />
                                            Mutual
                                        </>
                                    ) : friendshipStatus?.is_following ? (
                                        <>
                                            <UserCheckIcon className="w-4 h-4 mr-2" />
                                            Added
                                        </>
                                    ) : (
                                        <>
                                            <UserPlusIcon className="w-4 h-4 mr-2" />
                                            Add Friend
                                        </>
                                    )}
                                </Button>

                                {/* Subscribe Button */}
                                <Button
                                    variant={subscriptionStatus?.is_subscribed ? 'secondary' : 'outline'}
                                    size="md"
                                    onClick={handleSubscribeClick}
                                    disabled={subscribeToUser.isPending || unsubscribeFromUser.isPending}
                                    className={subscriptionStatus?.is_subscribed ? 'bg-yellow-600 hover:bg-yellow-700' : ''}
                                    title={subscriptionStatus?.is_subscribed ? 'Subscribed - Click to Unsubscribe' : 'Subscribe to get notified when this user uploads'}
                                >
                                    {subscriptionStatus?.is_subscribed ? (
                                        <>
                                            <BellFilledIcon className="w-4 h-4 mr-2" />
                                            Subscribed
                                        </>
                                    ) : (
                                        <>
                                            <BellIcon className="w-4 h-4 mr-2" />
                                            Subscribe
                                        </>
                                    )}
                                </Button>

                                {isBlocked ? (
                                    <Button
                                        variant="outline"
                                        size="md"
                                        onClick={handleUnblock}
                                        disabled={unblockUser.isPending}
                                    >
                                        <BlockIcon className="w-4 h-4 mr-2" />
                                        Unblock
                                    </Button>
                                ) : (
                                    <Button
                                        variant="outline"
                                        size="md"
                                        onClick={handleBlock}
                                        disabled={blockUser.isPending}
                                        className="hover:text-red-400 hover:border-red-400/50"
                                    >
                                        <BlockIcon className="w-4 h-4 mr-2" />
                                        Block
                                    </Button>
                                )}

                                <Button
                                    variant="outline"
                                    size="md"
                                    onClick={() => setShowReportModal(true)}
                                    className="hover:text-red-400 hover:border-red-400/50"
                                >
                                    <FlagIcon className="w-4 h-4 mr-2" />
                                    Report
                                </Button>
                            </>
                        )}
                    </div>
                </div>
            )}

            {/* Bio */}
            {profile.bio && (
                <div className="max-w-4xl mx-auto px-4 pb-6">
                    <div className="bg-dark-400 rounded-xl p-4 border border-white/5">
                        <p className="text-gray-300 whitespace-pre-wrap">{profile.bio}</p>
                    </div>
                </div>
            )}

            {/* Tabs */}
            <div className="max-w-4xl mx-auto px-4">
                <div className="border-b border-white/10">
                    <nav className="flex gap-6">
                        <AnimatedTabButton
                            isActive={activeTab === 'overview'}
                            onClick={() => handleTabChange('overview')}
                            label="Overview"
                            variant="underline"
                        />
                        <AnimatedTabButton
                            isActive={activeTab === 'beatmaps'}
                            onClick={() => handleTabChange('beatmaps')}
                            label="Beatmaps"
                            variant="underline"
                            badge={<span className="ml-2 px-1.5 py-0.5 text-xs bg-dark-400 rounded">{profile.maps_generated}</span>}
                        />
                        <AnimatedTabButton
                            isActive={activeTab === 'achievements'}
                            onClick={() => handleTabChange('achievements')}
                            label="Achievements"
                            variant="underline"
                            badge={<span className="ml-2 px-1.5 py-0.5 text-xs bg-dark-400 rounded">{profile.achievements_count}</span>}
                        />
                        <AnimatedTabButton
                            isActive={activeTab === 'activity'}
                            onClick={() => handleTabChange('activity')}
                            label="Recent Activity"
                            variant="underline"
                        />
                    </nav>
                </div>

                {/* Tab Content */}
                <div className="py-6">
                    <AnimatedTabContent activeTab={activeTab}>
                        {activeTab === 'overview' && (
                            <StaggerPageContent className="space-y-6">
                                <StaggerSection>
                                    <div className="bg-dark-400 rounded-xl p-6 border border-white/5">
                                        <h3 className="text-lg font-semibold text-white mb-4">About</h3>
                                        <p className="text-gray-400">
                                            {profile.bio || `${profile.display_name} hasn't written anything about themselves yet.`}
                                        </p>
                                    </div>
                                </StaggerSection>

                                <StaggerSection>
                                    <div className="bg-dark-400 rounded-xl p-6 border border-white/5">
                                        <h3 className="text-lg font-semibold text-white mb-4">Community Activity</h3>
                                        <div className="grid grid-cols-2 gap-4">
                                            <div className="flex items-center gap-3">
                                                <div className="w-10 h-10 rounded-lg bg-primary-500/20 flex items-center justify-center">
                                                    <MapIcon className="w-5 h-5 text-primary-400" />
                                                </div>
                                                <div>
                                                    <div className="text-lg font-semibold text-white">{profile.maps_generated}</div>
                                                    <div className="text-sm text-gray-400">Maps Created</div>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-3">
                                                <div className="w-10 h-10 rounded-lg bg-green-500/20 flex items-center justify-center">
                                                    <VerifiedIcon className="w-5 h-5 text-green-400" />
                                                </div>
                                                <div>
                                                    <div className="text-lg font-semibold text-white">{profile.maps_verified}</div>
                                                    <div className="text-sm text-gray-400">Verifications</div>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-3">
                                                <div className="w-10 h-10 rounded-lg bg-accent-500/20 flex items-center justify-center">
                                                    <MessageIcon className="w-5 h-5 text-accent-400" />
                                                </div>
                                                <div>
                                                    <div className="text-lg font-semibold text-white">{profile.forum_posts}</div>
                                                    <div className="text-sm text-gray-400">Forum Posts</div>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-3">
                                                <div className="w-10 h-10 rounded-lg bg-yellow-500/20 flex items-center justify-center">
                                                    <TrophyIcon className="w-5 h-5 text-yellow-400" />
                                                </div>
                                                <div>
                                                    <div className="text-lg font-semibold text-white">{profile.achievements_count}</div>
                                                    <div className="text-sm text-gray-400">Achievements</div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </StaggerSection>
                            </StaggerPageContent>
                        )}

                        {activeTab === 'beatmaps' && (
                            <StaggerPageContent className="space-y-4">
                                {userMaps && userMaps.length > 0 ? (
                                    userMaps.map((map) => (
                                        <StaggerSection key={map.id}>
                                            <Link
                                                to={`/songs/${map.song_id}`}
                                                className="flex items-center gap-4 p-4 bg-dark-400 rounded-xl border border-white/5 hover:border-primary-500/30 transition-colors"
                                            >
                                                <div className="w-16 h-16 rounded-lg bg-dark-500 overflow-hidden flex-shrink-0">
                                                    {map.cover_url ? (
                                                        <img src={map.cover_url} alt={map.title} className="w-full h-full object-cover" />
                                                    ) : (
                                                        <div className="w-full h-full flex items-center justify-center">
                                                            <MapIcon className="w-6 h-6 text-gray-600" />
                                                        </div>
                                                    )}
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center gap-2">
                                                        <h4 className="font-medium text-white truncate">{map.title}</h4>
                                                        {map.is_verified && (
                                                            <span className="text-green-400">
                                                                <VerifiedIcon className="w-4 h-4" />
                                                            </span>
                                                        )}
                                                    </div>
                                                    <p className="text-sm text-gray-400 truncate">{map.artist}</p>
                                                </div>
                                                <div className="text-right text-sm text-gray-500">
                                                    {format(new Date(map.created_at), 'MMM d, yyyy')}
                                                </div>
                                            </Link>
                                        </StaggerSection>
                                    ))
                                ) : (
                                    <StaggerSection>
                                        <div className="text-center py-12 text-gray-400">
                                            <MapIcon className="w-12 h-12 mx-auto mb-4 opacity-50" />
                                            <p>No beatmaps yet</p>
                                        </div>
                                    </StaggerSection>
                                )}
                            </StaggerPageContent>
                        )}

                        {activeTab === 'achievements' && (
                            <StaggerPageContent>
                                <StaggerSection>
                                    <div className="text-center py-12 text-gray-400">
                                        <TrophyIcon className="w-12 h-12 mx-auto mb-4 opacity-50" />
                                        <p>Achievements coming soon</p>
                                    </div>
                                </StaggerSection>
                            </StaggerPageContent>
                        )}

                        {activeTab === 'activity' && (
                            <StaggerPageContent>
                                <StaggerSection>
                                    <div className="text-center py-12 text-gray-400">
                                        <CalendarIcon className="w-12 h-12 mx-auto mb-4 opacity-50" />
                                        <p>No recent activity</p>
                                    </div>
                                </StaggerSection>
                            </StaggerPageContent>
                        )}
                    </AnimatedTabContent>
                </div>
            </div>

            {/* Report Modal */}
            <ReportUserModal
                userId={userId || ''}
                username={profile.display_name}
                open={showReportModal}
                onClose={() => setShowReportModal(false)}
            />
        </PageContentWrapper>
    )
}

// =============================================================================
// Report User Modal
// =============================================================================

interface ReportUserModalProps {
    userId: string
    username: string
    open: boolean
    onClose: () => void
}

const REPORT_TYPES: { value: ReportType; label: string; description: string }[] = [
    { value: 'spam', label: 'Spam', description: 'Repetitive or unwanted content' },
    { value: 'harassment', label: 'Harassment', description: 'Bullying or threatening behavior' },
    { value: 'inappropriate_content', label: 'Inappropriate Content', description: 'Offensive or inappropriate material' },
    { value: 'cheating', label: 'Cheating', description: 'Exploiting or gaming the system' },
    { value: 'impersonation', label: 'Impersonation', description: 'Pretending to be someone else' },
    { value: 'copyright', label: 'Copyright', description: 'Unauthorized use of copyrighted material' },
    { value: 'other', label: 'Other', description: 'Something else not listed above' },
]

function ReportUserModal({ userId, username, open, onClose }: ReportUserModalProps) {
    const [reportType, setReportType] = useState<ReportType>('other')
    const [description, setDescription] = useState('')
    const [submitted, setSubmitted] = useState(false)
    const reportUser = useReportUser()

    const handleSubmit = async () => {
        if (description.length < 10) return

        try {
            await reportUser.mutateAsync({ userId, reportType, description })
            setSubmitted(true)
        } catch (err) {
            console.error('Failed to submit report:', err)
        }
    }

    const handleClose = () => {
        setReportType('other')
        setDescription('')
        setSubmitted(false)
        onClose()
    }

    if (!open) return null

    return (
        <Modal open={open} onClose={handleClose} size="md">
            <ModalHeader title={`Report @${username}`} />
            <ModalBody>
                {submitted ? (
                    <div className="text-center py-6">
                        <div className="w-12 h-12 rounded-full bg-green-500/20 flex items-center justify-center mx-auto mb-4">
                            <VerifiedIcon className="w-6 h-6 text-green-500" />
                        </div>
                        <h3 className="text-lg font-medium text-white mb-2">Report Submitted</h3>
                        <p className="text-gray-400">
                            Thank you for your report. Our team will review it.
                        </p>
                    </div>
                ) : (
                    <div className="space-y-4">
                        <p className="text-sm text-gray-400">
                            Please select the reason for reporting this user and provide details.
                        </p>

                        <div className="space-y-2">
                            <label className="block text-sm font-medium text-gray-300">
                                Reason for Report
                            </label>
                            <div className="grid gap-2">
                                {REPORT_TYPES.map((type) => (
                                    <label
                                        key={type.value}
                                        className={clsx(
                                            'flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors',
                                            reportType === type.value
                                                ? 'border-primary-500 bg-primary-500/10'
                                                : 'border-white/10 hover:border-white/20'
                                        )}
                                    >
                                        <input
                                            type="radio"
                                            name="reportType"
                                            value={type.value}
                                            checked={reportType === type.value}
                                            onChange={(e) => setReportType(e.target.value as ReportType)}
                                            className="mt-1"
                                        />
                                        <div>
                                            <div className="font-medium text-white">{type.label}</div>
                                            <div className="text-sm text-gray-400">{type.description}</div>
                                        </div>
                                    </label>
                                ))}
                            </div>
                        </div>

                        <div className="space-y-2">
                            <label className="block text-sm font-medium text-gray-300">
                                Description <span className="text-red-400">*</span>
                            </label>
                            <textarea
                                value={description}
                                onChange={(e) => setDescription(e.target.value)}
                                placeholder="Please describe the issue in detail (minimum 10 characters)..."
                                rows={4}
                                className="w-full px-3 py-2 bg-dark-500 border border-white/10 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500 resize-none"
                            />
                            <p className="text-xs text-gray-500">{description.length}/2000</p>
                        </div>
                    </div>
                )}
            </ModalBody>
            {!submitted && (
                <ModalFooter>
                    <Button variant="ghost" onClick={handleClose}>
                        Cancel
                    </Button>
                    <Button
                        variant="danger"
                        onClick={handleSubmit}
                        disabled={description.length < 10 || reportUser.isPending}
                    >
                        {reportUser.isPending ? 'Submitting...' : 'Submit Report'}
                    </Button>
                </ModalFooter>
            )}
        </Modal>
    )
}

export default UserProfilePage
