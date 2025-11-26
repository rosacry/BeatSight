/**
 * User profile page.
 * Shows user info, stats, and account details.
 */

import { useState } from 'react'
import { useAuthStore } from '@/stores/authStore'
import { useQuery } from '@tanstack/react-query'
import { listJobs, listSongs } from '@/api/client'
import { format } from 'date-fns'

export function ProfilePage() {
    const user = useAuthStore((state) => state.user)
    const [activeTab, setActiveTab] = useState<'overview' | 'activity'>('overview')

    const { data: jobs } = useQuery({
        queryKey: ['jobs'],
        queryFn: () => listJobs(),
    })

    const { data: songs } = useQuery({
        queryKey: ['songs'],
        queryFn: listSongs,
    })

    if (!user) {
        return (
            <div className="flex items-center justify-center min-h-[60vh]">
                <p className="text-gray-400">Please log in to view your profile.</p>
            </div>
        )
    }

    // Calculate stats
    const totalSongs = songs?.length || 0
    const completedJobs = jobs?.filter((j) => j.state === 'complete').length || 0
    const totalJobs = jobs?.length || 0

    // Get initials for avatar
    const initials = user.display_name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)

    return (
        <div className="max-w-4xl mx-auto space-y-8">
            {/* Profile Header */}
            <div className="card">
                <div className="flex flex-col sm:flex-row items-center gap-6">
                    {/* Avatar */}
                    <div className="w-24 h-24 bg-primary-600 rounded-full flex items-center justify-center">
                        <span className="text-white text-3xl font-bold">{initials}</span>
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
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
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
            </div>

            {/* Tabs */}
            <div className="border-b border-gray-700">
                <nav className="flex gap-8">
                    <button
                        onClick={() => setActiveTab('overview')}
                        className={`pb-4 text-sm font-medium border-b-2 transition-colors ${activeTab === 'overview'
                                ? 'border-primary-500 text-primary-400'
                                : 'border-transparent text-gray-400 hover:text-white'
                            }`}
                    >
                        Overview
                    </button>
                    <button
                        onClick={() => setActiveTab('activity')}
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
