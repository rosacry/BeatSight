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
            <PageContentWrapper isLoading className="min-h-screen bg-dark-600">
                {/* Skeleton Banner */}
                <div className="relative h-64 md:h-80 lg:h-96 bg-dark-500 animate-pulse">
                    <div className="absolute inset-0 bg-gradient-to-t from-dark-600 via-dark-600/50 to-transparent" />
                </div>

                {/* Skeleton Profile Card */}
                <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="relative -mt-40 md:-mt-44 lg:-mt-52 z-20">
                        <div className="bg-dark-500/95 backdrop-blur-xl rounded-3xl border border-white/10 p-8">
                            <div className="flex flex-col lg:flex-row gap-6 lg:gap-10">
                                {/* Avatar skeleton */}
                                <div className="w-32 h-32 rounded-2xl bg-dark-400 animate-pulse" />

                                {/* Content skeleton */}
                                <div className="flex-1 space-y-4">
                                    <div className="h-8 w-48 bg-dark-400 rounded-lg animate-pulse" />
                                    <div className="h-4 w-32 bg-dark-400 rounded animate-pulse" />
                                    <div className="flex gap-6 mt-6">
                                        {[1, 2, 3, 4].map((i) => (
                                            <div key={i} className="space-y-2">
                                                <div className="h-8 w-12 bg-dark-400 rounded animate-pulse" />
                                                <div className="h-3 w-16 bg-dark-400 rounded animate-pulse" />
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                {/* Karma skeleton */}
                                <div className="w-48 h-32 bg-dark-400 rounded-2xl animate-pulse" />
                            </div>
                        </div>
                    </div>
                </div>
            </PageContentWrapper>
        )
    }

    if (error || !profile) {
        return (
            <PageContentWrapper className="min-h-screen bg-dark-600">
                {/* Subtle gradient background */}
                <div className="absolute inset-0 bg-gradient-to-b from-primary-900/10 via-transparent to-transparent pointer-events-none" />

                <div className="max-w-4xl mx-auto px-4 py-24 text-center relative">
                    <div className="w-28 h-28 mx-auto mb-8 rounded-3xl bg-dark-400/80 flex items-center justify-center border border-white/10">
                        <svg className="w-14 h-14 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                        </svg>
                    </div>
                    <h1 className="text-3xl font-bold text-white mb-3">User Not Found</h1>
                    <p className="text-gray-400 mb-8 max-w-md mx-auto">
                        This user doesn't exist, has been removed, or you don't have permission to view their profile.
                    </p>
                    <div className="flex gap-3 justify-center">
                        <Link
                            to="/"
                            className="px-6 py-2.5 bg-primary-500 hover:bg-primary-400 text-white font-medium rounded-xl transition-colors"
                        >
                            Go Home
                        </Link>
                        <button
                            onClick={() => window.history.back()}
                            className="px-6 py-2.5 bg-dark-400 hover:bg-dark-300 text-white font-medium rounded-xl transition-colors border border-white/10"
                        >
                            Go Back
                        </button>
                    </div>
                </div>
            </PageContentWrapper>
        )
    }

    return (
        <PageContentWrapper className="min-h-screen bg-dark-600">
            {/* osu!-style Profile Header with Full Banner */}
            <div className="relative">
                {/* Full-width Banner Image - Larger and more immersive like osu! */}
                <div className="relative h-64 md:h-80 lg:h-96 overflow-hidden">
                    {/* Banner Image */}
                    {profile.banner_url ? (
                        <img
                            src={profile.banner_url}
                            alt="Profile banner"
                            className="absolute inset-0 w-full h-full object-cover"
                        />
                    ) : (
                        /* Default animated gradient background if no banner */
                        <div className="absolute inset-0 bg-gradient-to-br from-primary-900/80 via-dark-500 to-accent-900/60">
                            {/* Decorative pattern overlay */}
                            <div className="absolute inset-0 opacity-10" style={{
                                backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.4'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
                            }} />
                        </div>
                    )}

                    {/* Multiple gradient overlays for depth and readability */}
                    <div className="absolute inset-0 bg-gradient-to-t from-dark-600 via-dark-600/50 to-transparent" />
                    <div className="absolute inset-0 bg-gradient-to-r from-dark-600/60 via-transparent to-dark-600/60" />

                    {/* Banner Upload overlay for own profile - positioned in corner */}
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

                {/* Profile Card - Floating over banner with glassmorphism */}
                <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="relative -mt-40 md:-mt-44 lg:-mt-52 z-20">
                        <div className="bg-dark-500/95 backdrop-blur-xl rounded-3xl border border-white/10 shadow-2xl overflow-hidden">
                            {/* Main Profile Content */}
                            <div className="p-6 md:p-8 lg:p-10">
                                <div className="flex flex-col lg:flex-row gap-6 lg:gap-10">
                                    {/* Left: Avatar and Quick Actions */}
                                    <div className="flex flex-col items-center lg:items-start gap-4">
                                        {/* Avatar with border ring */}
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
                                            <div className="relative">
                                                <div className="w-32 h-32 md:w-36 md:h-36 rounded-2xl overflow-hidden bg-dark-400 shadow-xl ring-4 ring-dark-400/50">
                                                    {profile.avatar_url ? (
                                                        <img
                                                            src={profile.avatar_url}
                                                            alt={profile.display_name}
                                                            className="w-full h-full object-cover"
                                                        />
                                                    ) : (
                                                        <div className="w-full h-full bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center">
                                                            <span className="text-5xl font-bold text-white">
                                                                {profile.display_name?.charAt(0).toUpperCase()}
                                                            </span>
                                                        </div>
                                                    )}
                                                </div>
                                                {/* Online indicator */}
                                                {profile.last_active && (
                                                    <div className="absolute -bottom-1 -right-1 w-6 h-6 bg-green-500 rounded-full border-4 border-dark-500" />
                                                )}
                                            </div>
                                        )}

                                        {/* User Number Badge */}
                                        <div className="flex items-center gap-2 px-3 py-1.5 bg-dark-400/80 rounded-lg">
                                            <span className="text-xs text-gray-400">User</span>
                                            <span className="text-sm font-bold text-white">#{profile.user_number}</span>
                                        </div>
                                    </div>

                                    {/* Center: User Info */}
                                    <div className="flex-1 min-w-0 text-center lg:text-left">
                                        {/* Name and Badges Row */}
                                        <div className="flex flex-col lg:flex-row items-center lg:items-start gap-3">
                                            <h1 className="text-3xl md:text-4xl font-bold text-white truncate">
                                                {profile.display_name}
                                            </h1>
                                            <div className="flex flex-wrap items-center gap-2 justify-center lg:justify-start">
                                                {/* Role Badge */}
                                                {profile.role && profile.role !== 'user' && (
                                                    <span className={clsx(
                                                        'px-3 py-1 text-xs font-bold rounded-full uppercase tracking-wide',
                                                        profile.role === 'admin' ? 'bg-gradient-to-r from-red-500 to-pink-500 text-white' :
                                                            profile.role === 'staff' ? 'bg-gradient-to-r from-amber-500 to-orange-500 text-dark-600' :
                                                                profile.role === 'verifier' ? 'bg-gradient-to-r from-green-500 to-emerald-500 text-dark-600' :
                                                                    'bg-gray-500 text-white'
                                                    )}>
                                                        {profile.role}
                                                    </span>
                                                )}
                                                {/* Custom Tags */}
                                                {profile.tags?.map((tag) => (
                                                    <span
                                                        key={tag.id}
                                                        className="px-3 py-1 text-xs font-bold rounded-full"
                                                        style={{
                                                            backgroundColor: tag.background_color,
                                                            color: tag.text_color || '#ffffff',
                                                        }}
                                                    >
                                                        {tag.name}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>

                                        {/* Meta Info Row */}
                                        <div className="flex flex-wrap items-center gap-4 mt-3 justify-center lg:justify-start text-sm text-gray-400">
                                            {profile.country_code && (
                                                <span className="flex items-center gap-1.5">
                                                    <span className={`fi fi-${profile.country_code.toLowerCase()}`} />
                                                    {profile.country_code}
                                                </span>
                                            )}
                                            <span className="flex items-center gap-1.5">
                                                <CalendarIcon className="w-4 h-4" />
                                                Joined {format(new Date(profile.created_at), 'MMMM yyyy')}
                                            </span>
                                            {profile.last_active && (
                                                <span className="flex items-center gap-1.5 text-green-400">
                                                    <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
                                                    Online Now
                                                </span>
                                            )}
                                        </div>

                                        {/* Bio Preview */}
                                        {profile.bio && (
                                            <p className="mt-4 text-gray-300 text-sm line-clamp-2 max-w-2xl">
                                                {profile.bio}
                                            </p>
                                        )}

                                        {/* Quick Stats Row */}
                                        <div className="flex flex-wrap items-center gap-6 mt-6 justify-center lg:justify-start">
                                            <div className="text-center">
                                                <div className="text-2xl font-bold text-white">{profile.songs_uploaded.toLocaleString()}</div>
                                                <div className="text-xs text-gray-400 uppercase tracking-wide">Songs</div>
                                            </div>
                                            <div className="w-px h-10 bg-white/10 hidden sm:block" />
                                            <div className="text-center">
                                                <div className="text-2xl font-bold text-primary-400">{profile.maps_generated.toLocaleString()}</div>
                                                <div className="text-xs text-gray-400 uppercase tracking-wide">Maps</div>
                                            </div>
                                            <div className="w-px h-10 bg-white/10 hidden sm:block" />
                                            <div className="text-center">
                                                <div className="text-2xl font-bold text-green-400">{profile.maps_verified.toLocaleString()}</div>
                                                <div className="text-xs text-gray-400 uppercase tracking-wide">Verified</div>
                                            </div>
                                            <div className="w-px h-10 bg-white/10 hidden sm:block" />
                                            <div className="text-center">
                                                <div className="text-2xl font-bold text-yellow-400">{profile.achievements_count.toLocaleString()}</div>
                                                <div className="text-xs text-gray-400 uppercase tracking-wide">Achievements</div>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Right: Karma Score Display - Large and Prominent */}
                                    <div className="flex-shrink-0 flex flex-col items-center lg:items-end gap-4">
                                        <KarmaBreakdownTooltip userId={profile.id} karmaScore={profile.karma_score} placement="left">
                                            <div className="bg-gradient-to-br from-yellow-500/20 to-amber-600/10 rounded-2xl p-6 border border-yellow-500/20">
                                                <div className="flex items-center gap-3 justify-center">
                                                    <StarIcon className="w-8 h-8 text-yellow-400" />
                                                    <span className="text-5xl md:text-6xl font-bold text-white">
                                                        {profile.karma_score.toLocaleString()}
                                                    </span>
                                                </div>
                                                <p className="text-center text-sm text-yellow-400/80 mt-2 font-medium">Karma Score</p>
                                                {profile.karma_rank && (
                                                    <Link
                                                        to="/leaderboard?tab=karma"
                                                        className="mt-3 flex items-center justify-center gap-2 px-4 py-2 bg-yellow-500/20 hover:bg-yellow-500/30 text-yellow-300 rounded-xl text-lg font-bold transition-all border border-yellow-500/30"
                                                    >
                                                        <span className="text-yellow-400">#</span>
                                                        <span>{profile.karma_rank.toLocaleString()}</span>
                                                    </Link>
                                                )}
                                            </div>
                                        </KarmaBreakdownTooltip>
                                    </div>
                                </div>
                            </div>

                            {/* Action Buttons Row - Integrated into card */}
                            {isAuthenticated && (
                                <div className="px-6 md:px-8 lg:px-10 pb-6 md:pb-8 lg:pb-10">
                                    <div className="flex flex-wrap gap-3 justify-center lg:justify-start pt-6 border-t border-white/10">
                                        {isOwnProfile ? (
                                            <>
                                                <Link to="/upload">
                                                    <Button variant="primary" size="md" className="gap-2">
                                                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                                                        </svg>
                                                        Upload Song
                                                    </Button>
                                                </Link>
                                                <Link to="/library">
                                                    <Button variant="secondary" size="md" className="gap-2">
                                                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                                                        </svg>
                                                        My Library
                                                    </Button>
                                                </Link>
                                                <Link to="/settings">
                                                    <Button variant="outline" size="md" className="gap-2">
                                                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                                        </svg>
                                                        Settings
                                                    </Button>
                                                </Link>
                                            </>
                                        ) : (
                                            <>
                                                <Link to={`/messages/${userId}`}>
                                                    <Button variant="primary" size="md" className="gap-2">
                                                        <MessageIcon className="w-4 h-4" />
                                                        Message
                                                    </Button>
                                                </Link>

                                                <Button
                                                    variant={friendshipStatus?.is_mutual ? 'primary' : friendshipStatus?.is_following ? 'secondary' : 'outline'}
                                                    size="md"
                                                    onClick={handleFriendClick}
                                                    disabled={addFriend.isPending || removeFriend.isPending}
                                                    className={clsx(
                                                        'gap-2',
                                                        friendshipStatus?.is_mutual && 'bg-purple-600 hover:bg-purple-700 border-purple-600',
                                                        friendshipStatus?.is_following && !friendshipStatus?.is_mutual && 'bg-green-600 hover:bg-red-600 border-green-600'
                                                    )}
                                                >
                                                    {friendshipStatus?.is_mutual ? (
                                                        <>
                                                            <UsersIcon className="w-4 h-4" />
                                                            Mutual
                                                        </>
                                                    ) : friendshipStatus?.is_following ? (
                                                        <>
                                                            <UserCheckIcon className="w-4 h-4" />
                                                            Added
                                                        </>
                                                    ) : (
                                                        <>
                                                            <UserPlusIcon className="w-4 h-4" />
                                                            Add Friend
                                                        </>
                                                    )}
                                                </Button>

                                                <Button
                                                    variant={subscriptionStatus?.is_subscribed ? 'secondary' : 'outline'}
                                                    size="md"
                                                    onClick={handleSubscribeClick}
                                                    disabled={subscribeToUser.isPending || unsubscribeFromUser.isPending}
                                                    className={clsx(
                                                        'gap-2',
                                                        subscriptionStatus?.is_subscribed && 'bg-yellow-600 hover:bg-yellow-700 border-yellow-600'
                                                    )}
                                                    title={subscriptionStatus?.is_subscribed ? 'Subscribed - Click to Unsubscribe' : 'Subscribe to get notified'}
                                                >
                                                    {subscriptionStatus?.is_subscribed ? (
                                                        <>
                                                            <BellFilledIcon className="w-4 h-4" />
                                                            Subscribed
                                                        </>
                                                    ) : (
                                                        <>
                                                            <BellIcon className="w-4 h-4" />
                                                            Subscribe
                                                        </>
                                                    )}
                                                </Button>

                                                <div className="flex gap-2">
                                                    {isBlocked ? (
                                                        <Button
                                                            variant="outline"
                                                            size="md"
                                                            onClick={handleUnblock}
                                                            disabled={unblockUser.isPending}
                                                            className="gap-2"
                                                        >
                                                            <BlockIcon className="w-4 h-4" />
                                                            Unblock
                                                        </Button>
                                                    ) : (
                                                        <Button
                                                            variant="outline"
                                                            size="md"
                                                            onClick={handleBlock}
                                                            disabled={blockUser.isPending}
                                                            className="gap-2 hover:text-red-400 hover:border-red-400/50"
                                                        >
                                                            <BlockIcon className="w-4 h-4" />
                                                            Block
                                                        </Button>
                                                    )}

                                                    <Button
                                                        variant="outline"
                                                        size="md"
                                                        onClick={() => setShowReportModal(true)}
                                                        className="gap-2 hover:text-red-400 hover:border-red-400/50"
                                                    >
                                                        <FlagIcon className="w-4 h-4" />
                                                        Report
                                                    </Button>
                                                </div>
                                            </>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* Tabs Section - Clean osu! style */}
            <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 mt-8">
                <div className="bg-dark-500/50 rounded-2xl border border-white/5 overflow-hidden">
                    {/* Tab Navigation */}
                    <div className="border-b border-white/10 px-4 md:px-6">
                        <nav className="flex gap-1 -mb-px overflow-x-auto">
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
                                badge={
                                    <span className="ml-2 px-2 py-0.5 text-xs bg-primary-500/20 text-primary-400 rounded-full font-medium">
                                        {profile.maps_generated}
                                    </span>
                                }
                            />
                            <AnimatedTabButton
                                isActive={activeTab === 'achievements'}
                                onClick={() => handleTabChange('achievements')}
                                label="Achievements"
                                variant="underline"
                                badge={
                                    <span className="ml-2 px-2 py-0.5 text-xs bg-yellow-500/20 text-yellow-400 rounded-full font-medium">
                                        {profile.achievements_count}
                                    </span>
                                }
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
                    <div className="p-4 md:p-6">
                        <AnimatedTabContent activeTab={activeTab}>
                            {activeTab === 'overview' && (
                                <StaggerPageContent className="grid md:grid-cols-2 gap-6">
                                    {/* About Section */}
                                    <StaggerSection>
                                        <div className="bg-dark-400/50 rounded-xl p-5 border border-white/5 h-full">
                                            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                                                <svg className="w-5 h-5 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                                                </svg>
                                                About
                                            </h3>
                                            <p className="text-gray-400 leading-relaxed">
                                                {profile.bio || `${profile.display_name} hasn't written anything about themselves yet.`}
                                            </p>
                                        </div>
                                    </StaggerSection>

                                    {/* Contributions Section */}
                                    <StaggerSection>
                                        <div className="bg-dark-400/50 rounded-xl p-5 border border-white/5 h-full">
                                            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                                                <svg className="w-5 h-5 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                                </svg>
                                                Contributions
                                            </h3>
                                            <div className="grid grid-cols-2 gap-4">
                                                <div className="flex items-center gap-4 p-3 bg-dark-500/50 rounded-lg">
                                                    <div className="w-10 h-10 rounded-lg bg-accent-500/20 flex items-center justify-center">
                                                        <MessageIcon className="w-5 h-5 text-accent-400" />
                                                    </div>
                                                    <div>
                                                        <div className="text-xl font-bold text-white">{profile.forum_posts}</div>
                                                        <div className="text-xs text-gray-400">Forum Posts</div>
                                                    </div>
                                                </div>
                                                <div className="flex items-center gap-4 p-3 bg-dark-500/50 rounded-lg">
                                                    <div className="w-10 h-10 rounded-lg bg-green-500/20 flex items-center justify-center">
                                                        <VerifiedIcon className="w-5 h-5 text-green-400" />
                                                    </div>
                                                    <div>
                                                        <div className="text-xl font-bold text-white">{profile.contribution_count}</div>
                                                        <div className="text-xs text-gray-400">Contributions</div>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </StaggerSection>
                                </StaggerPageContent>
                            )}

                            {activeTab === 'beatmaps' && (
                                <StaggerPageContent className="space-y-3">
                                    {userMaps && userMaps.length > 0 ? (
                                        userMaps.map((map) => (
                                            <StaggerSection key={map.id}>
                                                <Link
                                                    to={`/songs/${map.song_id}`}
                                                    className="flex items-center gap-4 p-4 bg-dark-400/50 rounded-xl border border-white/5 hover:border-primary-500/30 hover:bg-dark-400 transition-all group"
                                                >
                                                    <div className="w-14 h-14 rounded-lg bg-dark-500 overflow-hidden flex-shrink-0 shadow-lg">
                                                        {map.cover_url ? (
                                                            <img src={map.cover_url} alt={map.title} className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-300" />
                                                        ) : (
                                                            <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-dark-400 to-dark-500">
                                                                <MapIcon className="w-6 h-6 text-gray-600" />
                                                            </div>
                                                        )}
                                                    </div>
                                                    <div className="flex-1 min-w-0">
                                                        <div className="flex items-center gap-2">
                                                            <h4 className="font-medium text-white truncate group-hover:text-primary-400 transition-colors">{map.title}</h4>
                                                            {map.is_verified && (
                                                                <span className="text-green-400 flex-shrink-0">
                                                                    <VerifiedIcon className="w-4 h-4" />
                                                                </span>
                                                            )}
                                                        </div>
                                                        <p className="text-sm text-gray-400 truncate">{map.artist}</p>
                                                    </div>
                                                    <div className="text-right text-sm text-gray-500 hidden sm:block">
                                                        <div className="text-gray-400">{map.play_count?.toLocaleString() || 0} plays</div>
                                                        <div>{format(new Date(map.created_at), 'MMM d, yyyy')}</div>
                                                    </div>
                                                    <svg className="w-5 h-5 text-gray-600 group-hover:text-primary-400 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                                    </svg>
                                                </Link>
                                            </StaggerSection>
                                        ))
                                    ) : (
                                        <StaggerSection>
                                            <div className="text-center py-16 text-gray-400">
                                                <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-dark-400/50 flex items-center justify-center">
                                                    <MapIcon className="w-8 h-8 text-gray-600" />
                                                </div>
                                                <p className="text-lg font-medium text-gray-300">No beatmaps yet</p>
                                                <p className="text-sm mt-1">When {profile.display_name} creates beatmaps, they'll appear here.</p>
                                            </div>
                                        </StaggerSection>
                                    )}
                                </StaggerPageContent>
                            )}

                            {activeTab === 'achievements' && (
                                <StaggerPageContent>
                                    <StaggerSection>
                                        <div className="text-center py-16 text-gray-400">
                                            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-yellow-500/10 flex items-center justify-center">
                                                <TrophyIcon className="w-8 h-8 text-yellow-500/50" />
                                            </div>
                                            <p className="text-lg font-medium text-gray-300">Achievements Coming Soon</p>
                                            <p className="text-sm mt-1">Earn badges and unlock achievements as you contribute to the community.</p>
                                        </div>
                                    </StaggerSection>
                                </StaggerPageContent>
                            )}

                            {activeTab === 'activity' && (
                                <StaggerPageContent>
                                    <StaggerSection>
                                        <div className="text-center py-16 text-gray-400">
                                            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-dark-400/50 flex items-center justify-center">
                                                <CalendarIcon className="w-8 h-8 text-gray-600" />
                                            </div>
                                            <p className="text-lg font-medium text-gray-300">No Recent Activity</p>
                                            <p className="text-sm mt-1">Activity like uploads, map creations, and more will appear here.</p>
                                        </div>
                                    </StaggerSection>
                                </StaggerPageContent>
                            )}
                        </AnimatedTabContent>
                    </div>
                </div>
            </div>

            {/* Spacer at bottom */}
            <div className="h-12" />

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
