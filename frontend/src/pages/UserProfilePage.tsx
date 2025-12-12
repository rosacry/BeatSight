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
import { useBlockUser, useUnblockUser, useReportUser } from '@/api/socialHooks'
import type { ReportType } from '@/api/social'
import {
    AnimatedTabContent,
    AnimatedTabButton,
    StaggerPageContent,
    StaggerSection,
    PageContentWrapper
} from '@/components/ui/UnifiedTransitions'
import { KarmaRankBadge } from './LeaderboardPage'
import { KarmaBreakdownTooltip } from '@/components/social'
import { BannerUpload } from '@/components/BannerUpload'

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
            {/* Profile Header / Banner */}
            <div className="relative">
                {/* Banner Image */}
                <div
                    className="h-48 md:h-64 bg-gradient-to-b from-primary-900/30 to-dark-600 bg-cover bg-center relative"
                    style={profile.banner_url ? { backgroundImage: `url(${profile.banner_url})` } : undefined}
                >
                    <div className="absolute inset-0 bg-gradient-to-t from-dark-600 via-dark-600/50 to-transparent" />

                    {/* Banner Upload overlay for own profile */}
                    {isOwnProfile && (
                        <BannerUpload
                            currentBannerUrl={profile.banner_url}
                            onUploadSuccess={() => {
                                // Refetch profile to get updated banner URL
                                window.location.reload()
                            }}
                            className="absolute inset-0 z-10"
                        />
                    )}
                </div>

                {/* Profile Info Overlay */}
                <div className="max-w-4xl mx-auto px-4 relative">
                    <div className="flex flex-col md:flex-row items-start md:items-end gap-4 -mt-20 relative z-10">
                        {/* Avatar */}
                        <div className="relative">
                            <div className="w-32 h-32 md:w-40 md:h-40 rounded-2xl overflow-hidden border-4 border-dark-600 bg-dark-500 shadow-xl">
                                {profile.avatar_url ? (
                                    <img
                                        src={profile.avatar_url}
                                        alt={profile.display_name}
                                        className="w-full h-full object-cover"
                                    />
                                ) : (
                                    <div className="w-full h-full bg-primary-600 flex items-center justify-center">
                                        <span className="text-4xl font-bold text-white">
                                            {profile.display_name?.charAt(0).toUpperCase()}
                                        </span>
                                    </div>
                                )}
                            </div>
                            {/* Online status indicator */}
                            {profile.last_active && (
                                <div className="absolute bottom-2 right-2 w-4 h-4 bg-green-500 rounded-full border-2 border-dark-600" />
                            )}
                        </div>

                        {/* User Info */}
                        <div className="flex-1 pb-4">
                            <div className="flex items-center gap-3 mb-2 flex-wrap">
                                <h1 className="text-2xl md:text-3xl font-bold text-white">
                                    {profile.display_name}
                                </h1>
                                {profile.is_verified && (
                                    <span className="flex items-center gap-1 px-2 py-1 text-xs bg-blue-500/20 text-blue-400 rounded-full">
                                        <VerifiedIcon className="w-3 h-3" />
                                        Verified
                                    </span>
                                )}
                                {profile.role && profile.role !== 'user' && (
                                    <span className={clsx(
                                        'px-2 py-1 text-xs font-bold rounded-full',
                                        profile.role === 'admin' ? 'bg-red-500/20 text-red-400' :
                                            profile.role === 'staff' ? 'bg-amber-500/20 text-amber-400' :
                                                profile.role === 'verifier' ? 'bg-accent-500/20 text-accent-400' :
                                                    'bg-gray-500/20 text-gray-400'
                                    )}>
                                        {profile.role.toUpperCase()}
                                    </span>
                                )}
                                {/* Custom profile tags (like osu!'s DEV, VIP, etc.) */}
                                {profile.tags?.map((tag) => (
                                    <span
                                        key={tag.id}
                                        className="px-2 py-1 text-xs font-bold rounded"
                                        style={{
                                            backgroundColor: tag.background_color,
                                            color: tag.text_color || '#ffffff',
                                        }}
                                    >
                                        {tag.name}
                                    </span>
                                ))}
                            </div>

                            <div className="flex flex-wrap items-center gap-4 text-sm text-gray-400">
                                {/* Karma Ranking */}
                                {profile.karma_rank && (
                                    <Link
                                        to="/leaderboard?tab=karma"
                                        className="flex items-center gap-1 text-yellow-400 hover:text-yellow-300 transition-colors"
                                    >
                                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                                            <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
                                        </svg>
                                        Karma #{profile.karma_rank.toLocaleString()}
                                    </Link>
                                )}
                                {/* Contribution Ranking */}
                                {profile.contribution_rank && (
                                    <Link
                                        to="/leaderboard?tab=contributors"
                                        className="flex items-center gap-1 text-green-400 hover:text-green-300 transition-colors"
                                    >
                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                        </svg>
                                        Contrib #{profile.contribution_rank.toLocaleString()}
                                    </Link>
                                )}
                                {profile.country_code && (
                                    <span className="flex items-center gap-1">
                                        <span className={`fi fi-${profile.country_code.toLowerCase()}`} />
                                        {profile.country_code}
                                    </span>
                                )}
                                <span className="flex items-center gap-1">
                                    <CalendarIcon className="w-4 h-4" />
                                    Joined {format(new Date(profile.created_at), 'MMM yyyy')}
                                </span>
                            </div>
                        </div>

                        {/* Karma Score + Rank */}
                        <div className="text-center md:text-right pb-4">
                            <KarmaBreakdownTooltip userId={profile.id} karmaScore={profile.karma_score} placement="left">
                                <div className="inline-block">
                                    <div className="flex items-center gap-2 justify-center md:justify-end">
                                        <StarIcon className="w-5 h-5 text-yellow-400" />
                                        <span className="text-3xl font-bold text-white">
                                            {profile.karma_score.toLocaleString()}
                                        </span>
                                    </div>
                                    <div className="flex items-center justify-center md:justify-end gap-2 mt-1">
                                        <p className="text-sm text-gray-400">Karma</p>
                                        <KarmaRankBadge karma={profile.karma_score} />
                                    </div>
                                </div>
                            </KarmaBreakdownTooltip>
                        </div>
                    </div>
                </div>
            </div>

            {/* Stats Row */}
            <div className="max-w-4xl mx-auto px-4 py-6">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="bg-dark-400 rounded-xl p-4 text-center border border-white/5">
                        <div className="text-2xl font-bold text-white">{profile.songs_uploaded}</div>
                        <div className="text-sm text-gray-400">Songs Uploaded</div>
                    </div>
                    <div className="bg-dark-400 rounded-xl p-4 text-center border border-white/5">
                        <div className="text-2xl font-bold text-white">{profile.maps_generated}</div>
                        <div className="text-sm text-gray-400">Maps Generated</div>
                    </div>
                    <div className="bg-dark-400 rounded-xl p-4 text-center border border-white/5">
                        <div className="text-2xl font-bold text-green-400">{profile.maps_verified}</div>
                        <div className="text-sm text-gray-400">Maps Verified</div>
                    </div>
                    <div className="bg-dark-400 rounded-xl p-4 text-center border border-white/5">
                        <div className="text-2xl font-bold text-primary-400">{profile.achievements_count}</div>
                        <div className="text-sm text-gray-400">Achievements</div>
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
