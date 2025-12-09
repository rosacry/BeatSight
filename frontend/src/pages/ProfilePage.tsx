/**
 * User profile page.
 * Shows user info, stats, achievements, and account details.
 */

import { useState, useMemo, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { useQuery } from '@tanstack/react-query'
import { listJobs, listSongs, listAchievements } from '@/api/client'
import { format } from 'date-fns'
import { AchievementGrid } from '@/components/AchievementBadge'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'

const VALID_TABS = ['overview', 'achievements', 'activity'] as const
type ProfileTab = typeof VALID_TABS[number]

export function ProfilePage() {
    useDocumentTitle('profile')
    const user = useAuthStore((state) => state.user)
    const [searchParams, setSearchParams] = useSearchParams()

    // Get tab from URL or default to 'overview'
    const tabFromUrl = searchParams.get('tab') as ProfileTab | null
    const initialTab: ProfileTab = tabFromUrl && VALID_TABS.includes(tabFromUrl) ? tabFromUrl : 'overview'
    const [activeTab, setActiveTab] = useState<ProfileTab>(initialTab)

    // Update URL when tab changes
    const handleTabChange = (tab: ProfileTab) => {
        setActiveTab(tab)
        setSearchParams({ tab }, { replace: true })
    }

    // Sync tab state with URL on mount and URL changes
    useEffect(() => {
        const tabFromUrl = searchParams.get('tab')
        if (tabFromUrl && (VALID_TABS as readonly string[]).includes(tabFromUrl)) {
            setActiveTab(tabFromUrl as ProfileTab)
        }
    }, [searchParams])

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

    const isLoading = jobsLoading || songsLoading

    // PERF: Memoize computed stats to avoid re-calculation on every render
    const { totalSongs, completedJobs, totalJobs, initials } = useMemo(() => {
        const total = songs?.length || 0
        const completed = jobs?.filter((j) => j.state === 'complete').length || 0
        const jobCount = jobs?.length || 0
        const userInitials = user?.display_name
            ?.split(' ')
            .map((n) => n[0])
            .join('')
            .toUpperCase()
            .slice(0, 2) || ''

        return {
            totalSongs: total,
            completedJobs: completed,
            totalJobs: jobCount,
            initials: userInitials,
        }
    }, [songs, jobs, user?.display_name])

    if (!user) {
        return (
            <div className="flex items-center justify-center min-h-[60vh]">
                <p className="text-gray-400">Please log in to view your profile.</p>
            </div>
        )
    }

    if (isLoading) {
        return (
            <div className="max-w-4xl mx-auto space-y-8">
                {/* Profile Header Skeleton */}
                <div className="card animate-pulse">
                    <div className="flex flex-col sm:flex-row items-center gap-6">
                        <div className="w-24 h-24 bg-gray-700 rounded-full" />
                        <div className="flex-1 text-center sm:text-left space-y-3">
                            <div className="h-8 bg-gray-700 rounded w-48" />
                            <div className="h-4 bg-gray-700 rounded w-32" />
                            <div className="h-4 bg-gray-700 rounded w-24" />
                        </div>
                        <div className="text-center space-y-2">
                            <div className="h-10 bg-gray-700 rounded w-16 mx-auto" />
                            <div className="h-4 bg-gray-700 rounded w-12 mx-auto" />
                        </div>
                    </div>
                </div>

                {/* Stats Skeleton */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    {[1, 2, 3].map((i) => (
                        <div key={i} className="card animate-pulse text-center">
                            <div className="h-10 bg-gray-700 rounded w-16 mx-auto mb-2" />
                            <div className="h-4 bg-gray-700 rounded w-24 mx-auto" />
                        </div>
                    ))}
                </div>

                {/* Tabs Skeleton */}
                <div className="card animate-pulse">
                    <div className="flex gap-4 mb-6">
                        <div className="h-8 bg-gray-700 rounded w-24" />
                        <div className="h-8 bg-gray-700 rounded w-24" />
                    </div>
                    <div className="space-y-4">
                        {[1, 2, 3].map((i) => (
                            <div key={i} className="h-16 bg-gray-700 rounded" />
                        ))}
                    </div>
                </div>
            </div>
        )
    }

    return (
        <div className="max-w-4xl mx-auto space-y-8">
            {/* Profile Header */}
            <div className="card">
                <div className="flex flex-col sm:flex-row items-center gap-6">
                    {/* Avatar */}
                    <div className="w-24 h-24 bg-primary-600 rounded-full flex items-center justify-center overflow-hidden">
                        {user.avatar_url ? (
                            <img
                                src={user.avatar_url}
                                alt={user.display_name}
                                className="w-full h-full object-cover"
                            />
                        ) : (
                            <span className="text-white text-3xl font-bold">{initials}</span>
                        )}
                    </div>

                    {/* User Info */}
                    <div className="flex-1 text-center sm:text-left">
                        <h1 className="text-2xl font-bold text-white">{user.display_name}</h1>
                        <p className="text-gray-400">{user.email}</p>
                        <div className="flex items-center justify-center sm:justify-start gap-4 mt-3">
                            <span className="text-sm text-gray-500">
                                Joined {format(new Date(user.created_at), 'MMMM yyyy')}
                            </span>
                            {user.email_verified ? (
                                <span className="flex items-center gap-1 text-sm text-green-400">
                                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                                    </svg>
                                    Verified
                                </span>
                            ) : (
                                <span className="text-sm text-yellow-400">Email not verified</span>
                            )}
                        </div>
                    </div>

                    {/* Karma */}
                    <div className="text-center">
                        <div className="text-3xl font-bold text-primary-400">{user.karma_score}</div>
                        <div className="text-sm text-gray-500">Karma</div>
                    </div>
                </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
                <div className="card text-center">
                    <div className="text-3xl font-bold text-white">{totalSongs}</div>
                    <div className="text-gray-400 text-sm">Songs Uploaded</div>
                </div>
                <div className="card text-center">
                    <div className="text-3xl font-bold text-white">{completedJobs}</div>
                    <div className="text-gray-400 text-sm">Beatmaps Generated</div>
                </div>
                <div className="card text-center">
                    <div className="text-3xl font-bold text-white">
                        {totalJobs > 0 ? Math.round((completedJobs / totalJobs) * 100) : 0}%
                    </div>
                    <div className="text-gray-400 text-sm">Success Rate</div>
                </div>
                <div className="card text-center">
                    <div className="text-3xl font-bold text-primary-400">
                        {achievementsData?.total_earned || 0}
                    </div>
                    <div className="text-gray-400 text-sm">Achievements</div>
                </div>
            </div>

            {/* Tabs */}
            <div className="border-b border-gray-700">
                <nav className="flex gap-8">
                    <button
                        onClick={() => handleTabChange('overview')}
                        className={`pb-4 text-sm font-medium border-b-2 transition-colors ${activeTab === 'overview'
                            ? 'border-primary-500 text-primary-400'
                            : 'border-transparent text-gray-400 hover:text-white'
                            }`}
                    >
                        Overview
                    </button>
                    <button
                        onClick={() => handleTabChange('achievements')}
                        className={`pb-4 text-sm font-medium border-b-2 transition-colors ${activeTab === 'achievements'
                            ? 'border-primary-500 text-primary-400'
                            : 'border-transparent text-gray-400 hover:text-white'
                            }`}
                    >
                        Achievements
                        {achievementsData && (
                            <span className="ml-2 px-2 py-0.5 text-xs rounded-full bg-primary-500/20 text-primary-400">
                                {achievementsData.total_earned}
                            </span>
                        )}
                    </button>
                    <button
                        onClick={() => handleTabChange('activity')}
                        className={`pb-4 text-sm font-medium border-b-2 transition-colors ${activeTab === 'activity'
                            ? 'border-primary-500 text-primary-400'
                            : 'border-transparent text-gray-400 hover:text-white'
                            }`}
                    >
                        Recent Activity
                    </button>
                </nav>
            </div>

            {/* Tab Content */}
            {activeTab === 'overview' ? (
                <div className="space-y-6">
                    {/* Account Info */}
                    <div className="card">
                        <h2 className="text-lg font-semibold text-white mb-4">Account Information</h2>
                        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div>
                                <dt className="text-sm text-gray-500">Display Name</dt>
                                <dd className="text-white">{user.display_name}</dd>
                            </div>
                            <div>
                                <dt className="text-sm text-gray-500">Email</dt>
                                <dd className="text-white">{user.email}</dd>
                            </div>
                            <div>
                                <dt className="text-sm text-gray-500">User ID</dt>
                                <dd className="text-white font-mono text-sm">{user.id}</dd>
                            </div>
                            <div>
                                <dt className="text-sm text-gray-500">Member Since</dt>
                                <dd className="text-white">
                                    {format(new Date(user.created_at), 'MMMM d, yyyy')}
                                </dd>
                            </div>
                        </dl>
                    </div>

                    {/* Quick Actions */}
                    <div className="card">
                        <h2 className="text-lg font-semibold text-white mb-4">Quick Actions</h2>
                        <div className="flex flex-wrap gap-3">
                            <a href="/upload" className="btn btn-primary">
                                Upload New Song
                            </a>
                            <a href="/library" className="btn btn-secondary">
                                View Library
                            </a>
                            <a href="/settings" className="btn btn-secondary">
                                Edit Settings
                            </a>
                        </div>
                    </div>
                </div>
            ) : activeTab === 'achievements' ? (
                <div className="space-y-6">
                    {/* Achievement Points Summary */}
                    {achievementsData && (
                        <div className="card">
                            <div className="flex items-center justify-between mb-4">
                                <h2 className="text-lg font-semibold text-white">Your Achievements</h2>
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
                                        <div key={i} className="h-16 bg-gray-700 rounded animate-pulse" />
                                    ))}
                                </div>
                            ) : (
                                <AchievementGrid achievements={achievementsData.achievements} />
                            )}
                        </div>
                    )}
                </div>
            ) : (
                <div className="space-y-4">
                    {jobs && jobs.length > 0 ? (
                        jobs.slice(0, 10).map((job) => (
                            <div key={job.id} className="card">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <p className="text-white font-medium">
                                            {job.state === 'complete'
                                                ? 'Beatmap generated'
                                                : job.state === 'processing'
                                                    ? 'Processing...'
                                                    : job.state === 'queued'
                                                        ? 'Queued for processing'
                                                        : job.state === 'failed'
                                                            ? 'Generation failed'
                                                            : 'Job created'}
                                        </p>
                                        <p className="text-gray-500 text-sm">
                                            {format(new Date(job.created_at), 'MMM d, yyyy h:mm a')}
                                        </p>
                                    </div>
                                    <a
                                        href={`/jobs/${job.id}`}
                                        className="text-primary-400 hover:text-primary-300 text-sm"
                                    >
                                        View Details →
                                    </a>
                                </div>
                            </div>
                        ))
                    ) : (
                        <div className="card text-center py-8">
                            <p className="text-gray-400">No recent activity</p>
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}
