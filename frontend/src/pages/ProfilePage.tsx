/**
 * User profile page (own profile).
 * Shows user info, stats, achievements, and account details.
 * Design matches UserProfilePage for consistency (osu!-style).
 */

import { useMemo } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { useQuery } from '@tanstack/react-query'
import { listJobs, listSongs, listAchievements, getMyVerificationStats } from '@/api/client'
import { format } from 'date-fns'
import { AchievementGrid } from '@/components/AchievementBadge'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { Avatar } from '@/components/ui/Avatar'
import {
    AnimatedTabContent,
    AnimatedTabButton,
    StaggerPageContent,
    StaggerSection,
    PageContentWrapper
} from '@/components/ui/UnifiedTransitions'

const VALID_TABS = ['overview', 'achievements', 'activity'] as const
type ProfileTab = typeof VALID_TABS[number]

// Helper to get valid tab from URL
function getTabFromUrl(searchParams: URLSearchParams): ProfileTab {
    const tab = searchParams.get('tab')
    if (tab && (VALID_TABS as readonly string[]).includes(tab)) {
        return tab as ProfileTab
    }
    return 'overview'
}

export function ProfilePage() {
    useDocumentTitle('profile')
    const user = useAuthStore((state) => state.user)
    const [searchParams, setSearchParams] = useSearchParams()

    // Use URL as source of truth - derive tab from URL on every render
    const activeTab = getTabFromUrl(searchParams)

    // Update URL when tab changes
    const handleTabChange = (tab: ProfileTab) => {
        setSearchParams({ tab }, { replace: true })
    }

    const { data: jobs, isLoading: jobsLoading } = useQuery({
        queryKey: ['jobs'],
        queryFn: () => listJobs({ pageSize: 100 }),
    })

    const { data: songs, isLoading: songsLoading } = useQuery({
        queryKey: ['songs'],
        queryFn: () => listSongs({ pageSize: 100 }),
    })

    const { data: achievementsData, isLoading: achievementsLoading } = useQuery({
        queryKey: ['achievements'],
        queryFn: listAchievements,
        enabled: !!user,
    })

    const { data: verificationStats } = useQuery({
        queryKey: ['verification-stats'],
        queryFn: getMyVerificationStats,
        enabled: !!user,
    })

    const isLoading = jobsLoading || songsLoading

    // PERF: Memoize computed stats
    const { totalSongs, completedJobs, initials } = useMemo(() => {
        const total = songs?.length || 0
        const completed = jobs?.filter((j) => j.state === 'complete').length || 0
        const userInitials = user?.display_name
            ?.split(' ')
            .map((n) => n[0])
            .join('')
            .toUpperCase()
            .slice(0, 2) || ''

        return {
            totalSongs: total,
            completedJobs: completed,
            initials: userInitials,
        }
    }, [songs, jobs, user?.display_name])

    if (!user) {
        return (
            <PageContentWrapper className="flex items-center justify-center min-h-[60vh]">
                <p className="text-gray-400">Please log in to view your profile.</p>
            </PageContentWrapper>
        )
    }

    if (isLoading) {
        return (
            <PageContentWrapper isLoading={true} className="max-w-5xl mx-auto">
                {/* Banner Skeleton */}
                <div className="relative h-48 bg-dark-300 animate-pulse rounded-t-lg" />
                {/* Profile Header Skeleton */}
                <div className="relative -mt-16 px-6">
                    <div className="flex flex-col sm:flex-row items-start gap-4">
                        <div className="w-32 h-32 bg-dark-400 rounded-lg animate-pulse border-4 border-dark-200" />
                        <div className="flex-1 pt-16 sm:pt-4 space-y-3">
                            <div className="h-8 bg-dark-300 rounded w-48" />
                            <div className="h-4 bg-dark-300 rounded w-32" />
                        </div>
                    </div>
                </div>
                {/* Stats Skeleton */}
                <div className="mt-8 px-6 grid grid-cols-2 sm:grid-cols-4 gap-4">
                    {[1, 2, 3, 4].map((i) => (
                        <div key={i} className="bg-dark-300 rounded-lg p-4 animate-pulse">
                            <div className="h-8 bg-dark-400 rounded w-16 mx-auto mb-2" />
                            <div className="h-4 bg-dark-400 rounded w-20 mx-auto" />
                        </div>
                    ))}
                </div>
            </PageContentWrapper>
        )
    }

    return (
        <PageContentWrapper className="max-w-5xl mx-auto">
            {/* Banner - osu! style gradient */}
            <div className="relative h-48 bg-gradient-to-r from-primary-600/80 via-primary-500/60 to-accent-500/40 rounded-t-lg overflow-hidden">
                {/* Decorative pattern overlay */}
                <div
                    className="absolute inset-0 opacity-10"
                    style={{
                        backgroundImage: 'url("data:image/svg+xml,%3Csvg width=\'60\' height=\'60\' viewBox=\'0 0 60 60\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cg fill=\'none\' fill-rule=\'evenodd\'%3E%3Cg fill=\'%23ffffff\' fill-opacity=\'0.4\'%3E%3Cpath d=\'M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z\'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")',
                    }}
                />
                {/* Username watermark */}
                <div className="absolute bottom-4 right-6 text-white/20 text-6xl font-bold tracking-wider select-none">
                    {user.display_name?.toUpperCase()}
                </div>
            </div>

            {/* Profile Header - overlapping banner */}
            <div className="relative -mt-16 px-4 sm:px-6">
                <div className="flex flex-col sm:flex-row items-center sm:items-end gap-4">
                    {/* Avatar - rounded square like osu! */}
                    <Avatar
                        src={user.avatar_url ?? undefined}
                        fallback={initials}
                        alt={user.display_name}
                        size="4xl"
                        shape="square"
                        gradient
                        className="border-4 border-dark-200 shadow-xl"
                    />

                    {/* User Info */}
                    <div className="flex-1 text-center sm:text-left pb-2">
                        <div className="flex flex-col sm:flex-row sm:items-center gap-2 flex-wrap">
                            <h1 className="text-2xl sm:text-3xl font-bold text-white">{user.display_name}</h1>
                            {/* Profile Tags - like osu!'s DEV, VIP, etc. */}
                            {user.tags && user.tags.length > 0 && (
                                <div className="flex flex-wrap items-center gap-1">
                                    {user.tags.map((tag) => (
                                        <span
                                            key={tag.id}
                                            className="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold uppercase tracking-wider"
                                            style={{
                                                backgroundColor: tag.background_color,
                                                color: tag.text_color || '#ffffff',
                                            }}
                                        >
                                            {tag.name}
                                        </span>
                                    ))}
                                </div>
                            )}
                            {user.email_verified && (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-500/20 text-green-400 text-xs font-medium">
                                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                                    </svg>
                                    Verified
                                </span>
                            )}
                        </div>
                        <div className="flex flex-wrap items-center justify-center sm:justify-start gap-3 mt-1 text-sm text-gray-400">
                            <span>Joined {format(new Date(user.created_at), 'MMMM yyyy')}</span>
                        </div>
                    </div>

                    {/* Karma Score - prominent display */}
                    <div className="text-center bg-dark-300/80 backdrop-blur-sm rounded-lg px-6 py-3">
                        <div className="text-3xl font-bold text-primary-400">{user.karma_score}</div>
                        <div className="text-xs text-gray-500 uppercase tracking-wider">Karma</div>
                    </div>
                </div>
            </div>

            {/* Stats Row - osu! style cards */}
            <div className="mt-6 px-4 sm:px-6">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="bg-dark-300/50 backdrop-blur-sm rounded-lg p-4 text-center border border-white/5 hover:border-primary-500/30 transition-colors">
                        <div className="text-2xl sm:text-3xl font-bold text-white">{totalSongs}</div>
                        <div className="text-xs text-gray-500 uppercase tracking-wider mt-1">Songs</div>
                    </div>
                    <div className="bg-dark-300/50 backdrop-blur-sm rounded-lg p-4 text-center border border-white/5 hover:border-primary-500/30 transition-colors">
                        <div className="text-2xl sm:text-3xl font-bold text-white">{completedJobs}</div>
                        <div className="text-xs text-gray-500 uppercase tracking-wider mt-1">Maps Generated</div>
                    </div>
                    <div className="bg-dark-300/50 backdrop-blur-sm rounded-lg p-4 text-center border border-white/5 hover:border-green-500/30 transition-colors">
                        <div className="text-2xl sm:text-3xl font-bold text-green-400">{verificationStats?.consensus_matches || 0}</div>
                        <div className="text-xs text-gray-500 uppercase tracking-wider mt-1">Maps Verified</div>
                    </div>
                    <div className="bg-dark-300/50 backdrop-blur-sm rounded-lg p-4 text-center border border-white/5 hover:border-primary-500/30 transition-colors">
                        <div className="text-2xl sm:text-3xl font-bold text-primary-400">{achievementsData?.total_earned || 0}</div>
                        <div className="text-xs text-gray-500 uppercase tracking-wider mt-1">Achievements</div>
                    </div>
                </div>
            </div>

            {/* Quick Actions */}
            <div className="mt-6 px-4 sm:px-6">
                <div className="flex flex-wrap gap-3">
                    <Link to="/upload" className="btn btn-primary">
                        <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                        </svg>
                        Upload Song
                    </Link>
                    <Link to="/library" className="btn btn-secondary">
                        <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                        </svg>
                        My Library
                    </Link>
                    <Link to="/settings" className="btn btn-secondary">
                        <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        </svg>
                        Settings
                    </Link>
                </div>
            </div>

            {/* Tabs */}
            <div className="mt-8 px-4 sm:px-6 border-b border-white/10 overflow-x-auto">
                <nav className="flex gap-4 sm:gap-8 min-w-max">
                    <AnimatedTabButton
                        isActive={activeTab === 'overview'}
                        onClick={() => handleTabChange('overview')}
                        label="Overview"
                        variant="underline"
                    />
                    <AnimatedTabButton
                        isActive={activeTab === 'achievements'}
                        onClick={() => handleTabChange('achievements')}
                        label="Achievements"
                        variant="underline"
                        badge={achievementsData ? (
                            <span className="ml-2 px-2 py-0.5 text-xs rounded-full bg-primary-500/20 text-primary-400">
                                {achievementsData.total_earned}
                            </span>
                        ) : undefined}
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
            <div className="px-4 sm:px-6 py-6">
                <AnimatedTabContent activeTab={activeTab}>
                    {activeTab === 'overview' ? (
                        <StaggerPageContent className="space-y-6">
                            {/* Account Info Card */}
                            <StaggerSection>
                                <div className="card">
                                    <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                                        <svg className="w-5 h-5 text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                                        </svg>
                                        Account Information
                                    </h2>
                                    <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                        <div className="bg-dark-300/30 rounded-lg p-3">
                                            <dt className="text-xs text-gray-500 uppercase tracking-wider">Display Name</dt>
                                            <dd className="text-white mt-1">{user.display_name}</dd>
                                        </div>
                                        <div className="bg-dark-300/30 rounded-lg p-3">
                                            <dt className="text-xs text-gray-500 uppercase tracking-wider">Email</dt>
                                            <dd className="text-white mt-1">{user.email}</dd>
                                        </div>
                                        <div className="bg-dark-300/30 rounded-lg p-3">
                                            <dt className="text-xs text-gray-500 uppercase tracking-wider">User ID</dt>
                                            <dd className="text-white mt-1 font-mono text-sm">
                                                {user.user_number ?? user.id}
                                            </dd>
                                        </div>
                                        <div className="bg-dark-300/30 rounded-lg p-3">
                                            <dt className="text-xs text-gray-500 uppercase tracking-wider">Member Since</dt>
                                            <dd className="text-white mt-1">
                                                {format(new Date(user.created_at), 'MMMM d, yyyy')}
                                            </dd>
                                        </div>
                                    </dl>
                                </div>
                            </StaggerSection>

                            {/* Verification Stats */}
                            {verificationStats && (
                                <StaggerSection>
                                    <div className="card">
                                        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                                            <svg className="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                            </svg>
                                            Verification Activity
                                        </h2>
                                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                                            <div className="bg-dark-300/30 rounded-lg p-3 text-center">
                                                <div className="text-xl font-bold text-white">{verificationStats.total_votes}</div>
                                                <div className="text-xs text-gray-500">Total Votes</div>
                                            </div>
                                            <div className="bg-dark-300/30 rounded-lg p-3 text-center">
                                                <div className="text-xl font-bold text-green-400">{verificationStats.consensus_matches}</div>
                                                <div className="text-xs text-gray-500">Consensus Matches</div>
                                            </div>
                                            <div className="bg-dark-300/30 rounded-lg p-3 text-center">
                                                <div className="text-xl font-bold text-primary-400">
                                                    {verificationStats.total_votes > 0
                                                        ? Math.round((verificationStats.consensus_matches / verificationStats.total_votes) * 100)
                                                        : 0}%
                                                </div>
                                                <div className="text-xs text-gray-500">Accuracy</div>
                                            </div>
                                            <div className="bg-dark-300/30 rounded-lg p-3 text-center">
                                                <div className="text-xl font-bold text-yellow-400">{user.karma_score}</div>
                                                <div className="text-xs text-gray-500">Karma Score</div>
                                            </div>
                                        </div>
                                    </div>
                                </StaggerSection>
                            )}
                        </StaggerPageContent>
                    ) : activeTab === 'achievements' ? (
                        <StaggerPageContent className="space-y-6">
                            {achievementsData && (
                                <StaggerSection>
                                    <div className="card">
                                        <div className="flex items-center justify-between mb-6">
                                            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                                                <svg className="w-5 h-5 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
                                                </svg>
                                                Your Achievements
                                            </h2>
                                            <div className="text-right">
                                                <div className="text-2xl font-bold text-primary-400">
                                                    {achievementsData.total_points} pts
                                                </div>
                                                <div className="text-sm text-gray-400">
                                                    {achievementsData.total_earned} of {achievementsData.achievements.length} earned
                                                </div>
                                            </div>
                                        </div>
                                        {achievementsLoading ? (
                                            <div className="space-y-3">
                                                {[1, 2, 3].map((i) => (
                                                    <div key={i} className="h-16 bg-dark-300 rounded animate-pulse" />
                                                ))}
                                            </div>
                                        ) : (
                                            <AchievementGrid achievements={achievementsData.achievements} />
                                        )}
                                    </div>
                                </StaggerSection>
                            )}
                        </StaggerPageContent>
                    ) : (
                        <StaggerPageContent className="space-y-4">
                            {jobs && jobs.length > 0 ? (
                                jobs.slice(0, 10).map((job) => (
                                    <StaggerSection key={job.id}>
                                        <div className="card hover:border-primary-500/30 transition-colors">
                                            <div className="flex items-center justify-between">
                                                <div>
                                                    <p className="text-white font-medium">
                                                        {job.state === 'complete'
                                                            ? '✅ Beatmap generated'
                                                            : job.state === 'processing'
                                                                ? '⏳ Processing...'
                                                                : job.state === 'queued'
                                                                    ? '��� Queued for processing'
                                                                    : job.state === 'failed'
                                                                        ? '❌ Generation failed'
                                                                        : '��� Job created'}
                                                    </p>
                                                    <p className="text-gray-500 text-sm">
                                                        {format(new Date(job.created_at), 'MMM d, yyyy h:mm a')}
                                                    </p>
                                                </div>
                                                <Link
                                                    to={`/jobs/${job.id}`}
                                                    className="text-primary-400 hover:text-primary-300 text-sm font-medium"
                                                >
                                                    View Details →
                                                </Link>
                                            </div>
                                        </div>
                                    </StaggerSection>
                                ))
                            ) : (
                                <StaggerSection>
                                    <div className="card text-center py-12">
                                        <svg className="w-12 h-12 text-gray-600 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                                        </svg>
                                        <p className="text-gray-400">No recent activity</p>
                                        <Link to="/upload" className="text-primary-400 hover:text-primary-300 text-sm mt-2 inline-block">
                                            Upload your first song →
                                        </Link>
                                    </div>
                                </StaggerSection>
                            )}
                        </StaggerPageContent>
                    )}
                </AnimatedTabContent>
            </div>
        </PageContentWrapper>
    )
}
