/**
 * Admin Dashboard Page
 * Provides system overview, user management, and job monitoring.
 */

import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'

interface SystemOverview {
    total_users: number
    active_users_24h: number
    pro_subscribers: number
    total_jobs: number
    jobs_today: number
    processing_jobs: number
    failed_jobs_24h: number
}

interface UserStats {
    total_users: number
    verified_users: number
    pro_users: number
    users_today: number
    users_this_week: number
    users_this_month: number
}

interface QueueStats {
    total_jobs: number
    queued: number
    processing: number
    complete: number
    failed: number
    cancelled: number
    avg_processing_time_seconds: number | null
    jobs_today: number
    jobs_this_hour: number
}

interface AdminUser {
    id: string
    email: string
    display_name: string
    role: string
    email_verified: boolean
    karma_score: number
    created_at: string
    subscription_plan: string | null
    subscription_status: string | null
    job_count: number
    last_active: string | null
}

export function AdminDashboardPage() {
    const { accessToken } = useAuthStore()
    const [activeTab, setActiveTab] = useState<'overview' | 'users' | 'jobs'>('overview')
    const [overview, setOverview] = useState<SystemOverview | null>(null)
    const [userStats, setUserStats] = useState<UserStats | null>(null)
    const [queueStats, setQueueStats] = useState<QueueStats | null>(null)
    const [users, setUsers] = useState<AdminUser[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [searchQuery, setSearchQuery] = useState('')

    const fetchWithAuth = async (endpoint: string) => {
        const response = await fetch(`/api${endpoint}`, {
            headers: {
                'Authorization': `Bearer ${accessToken}`,
                'Content-Type': 'application/json',
            },
        })
        if (!response.ok) {
            if (response.status === 403) {
                throw new Error('Access denied. Admin permissions required.')
            }
            throw new Error('Failed to fetch data')
        }
        return response.json()
    }

    useEffect(() => {
        async function loadData() {
            try {
                setLoading(true)
                setError(null)

                const [overviewData, userStatsData, queueStatsData] = await Promise.all([
                    fetchWithAuth('/admin/overview'),
                    fetchWithAuth('/admin/users/stats'),
                    fetchWithAuth('/admin/ai-jobs/stats'),
                ])

                setOverview(overviewData)
                setUserStats(userStatsData)
                setQueueStats(queueStatsData)
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Failed to load admin data')
            } finally {
                setLoading(false)
            }
        }

        if (accessToken) {
            loadData()
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [accessToken])

    const loadUsers = async () => {
        try {
            const params = new URLSearchParams()
            if (searchQuery) params.set('search', searchQuery)
            const data = await fetchWithAuth(`/admin/users?${params}`)
            setUsers(data.users)
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to load users')
        }
    }

    useEffect(() => {
        if (activeTab === 'users' && accessToken) {
            loadUsers()
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [activeTab, accessToken, searchQuery])

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-[60vh]">
                <div className="animate-spin h-10 w-10 border-4 border-primary-500 border-t-transparent rounded-full" />
            </div>
        )
    }

    if (error) {
        return (
            <div className="flex items-center justify-center min-h-[60vh]">
                <div className="text-center">
                    <div className="w-16 h-16 bg-red-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
                        <svg className="w-8 h-8 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                    </div>
                    <h2 className="text-xl font-semibold text-white mb-2">Access Denied</h2>
                    <p className="text-gray-400 mb-4">{error}</p>
                    <Link to="/" className="text-primary-400 hover:text-primary-300">
                        Return to home
                    </Link>
                </div>
            </div>
        )
    }

    return (
        <div className="max-w-7xl mx-auto px-4 py-8">
            {/* Header */}
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className="text-3xl font-bold text-white">Admin Dashboard</h1>
                    <p className="text-gray-400 mt-1">System monitoring and management</p>
                </div>
                <div className="flex items-center gap-2 px-3 py-1.5 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                    <svg className="w-4 h-4 text-yellow-500" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M2.166 4.999A11.954 11.954 0 0010 1.944 11.954 11.954 0 0017.834 5c.11.65.166 1.32.166 2.001 0 5.225-3.34 9.67-8 11.317C5.34 16.67 2 12.225 2 7c0-.682.057-1.35.166-2.001zm11.541 3.708a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                    <span className="text-sm font-medium text-yellow-500">Admin Mode</span>
                </div>
            </div>

            {/* Tabs */}
            <div className="flex gap-1 p-1 bg-gray-800 rounded-lg w-fit mb-8">
                {(['overview', 'users', 'jobs'] as const).map((tab) => (
                    <button
                        key={tab}
                        onClick={() => setActiveTab(tab)}
                        className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${activeTab === tab
                            ? 'bg-primary-500 text-white'
                            : 'text-gray-400 hover:text-white'
                            }`}
                    >
                        {tab.charAt(0).toUpperCase() + tab.slice(1)}
                    </button>
                ))}
            </div>

            {/* Overview Tab */}
            {activeTab === 'overview' && overview && userStats && queueStats && (
                <div className="space-y-8">
                    {/* Key Metrics Grid */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <StatCard
                            title="Total Users"
                            value={overview.total_users}
                            icon="👥"
                            trend={`+${userStats.users_today} today`}
                        />
                        <StatCard
                            title="Active (24h)"
                            value={overview.active_users_24h}
                            icon="📈"
                        />
                        <StatCard
                            title="Pro Subscribers"
                            value={overview.pro_subscribers}
                            icon="⭐"
                            trend={`${((overview.pro_subscribers / overview.total_users) * 100).toFixed(1)}%`}
                        />
                        <StatCard
                            title="Jobs Today"
                            value={overview.jobs_today}
                            icon="🎵"
                            trend={`${queueStats.processing} processing`}
                        />
                    </div>

                    {/* Queue Status */}
                    <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
                        <h3 className="text-lg font-semibold text-white mb-4">Job Queue Status</h3>
                        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                            <QueueItem label="Queued" value={queueStats.queued} color="blue" />
                            <QueueItem label="Processing" value={queueStats.processing} color="yellow" />
                            <QueueItem label="Complete" value={queueStats.complete} color="green" />
                            <QueueItem label="Failed" value={queueStats.failed} color="red" />
                            <QueueItem label="Cancelled" value={queueStats.cancelled} color="gray" />
                        </div>
                        {queueStats.avg_processing_time_seconds && (
                            <p className="text-gray-400 text-sm mt-4">
                                Avg processing time: {Math.round(queueStats.avg_processing_time_seconds)}s
                            </p>
                        )}
                    </div>

                    {/* User Stats */}
                    <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
                        <h3 className="text-lg font-semibold text-white mb-4">User Growth</h3>
                        <div className="grid grid-cols-3 gap-6">
                            <div>
                                <p className="text-3xl font-bold text-white">{userStats.users_today}</p>
                                <p className="text-gray-400">Today</p>
                            </div>
                            <div>
                                <p className="text-3xl font-bold text-white">{userStats.users_this_week}</p>
                                <p className="text-gray-400">This Week</p>
                            </div>
                            <div>
                                <p className="text-3xl font-bold text-white">{userStats.users_this_month}</p>
                                <p className="text-gray-400">This Month</p>
                            </div>
                        </div>
                        <div className="mt-4 pt-4 border-t border-gray-700">
                            <p className="text-gray-400 text-sm">
                                {userStats.verified_users} verified ({((userStats.verified_users / userStats.total_users) * 100).toFixed(0)}%)
                            </p>
                        </div>
                    </div>
                </div>
            )}

            {/* Users Tab */}
            {activeTab === 'users' && (
                <div className="space-y-6">
                    {/* Search */}
                    <div className="flex gap-4">
                        <div className="flex-1 relative">
                            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                            </svg>
                            <input
                                type="text"
                                placeholder="Search by email or name..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="w-full pl-10 pr-4 py-2.5 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500"
                            />
                        </div>
                        <button
                            onClick={loadUsers}
                            className="px-4 py-2.5 bg-primary-500 hover:bg-primary-600 text-white rounded-lg font-medium transition-colors"
                        >
                            Search
                        </button>
                    </div>

                    {/* Users Table */}
                    <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
                        <table className="w-full">
                            <thead className="bg-gray-900">
                                <tr>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">User</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Role</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Plan</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Jobs</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Joined</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-700">
                                {users.map((user) => (
                                    <tr key={user.id} className="hover:bg-gray-700/50">
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-3">
                                                <div className="w-8 h-8 bg-primary-500/20 rounded-full flex items-center justify-center">
                                                    <span className="text-primary-400 font-medium text-sm">
                                                        {user.display_name.charAt(0).toUpperCase()}
                                                    </span>
                                                </div>
                                                <div>
                                                    <p className="text-white font-medium">{user.display_name}</p>
                                                    <p className="text-gray-400 text-sm">{user.email}</p>
                                                </div>
                                                {user.email_verified && (
                                                    <svg className="w-4 h-4 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                                                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                                                    </svg>
                                                )}
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <span className={`inline-flex px-2 py-1 text-xs rounded-full ${user.role === 'admin' ? 'bg-red-500/10 text-red-400' :
                                                user.role === 'moderator' ? 'bg-yellow-500/10 text-yellow-400' :
                                                    'bg-gray-500/10 text-gray-400'
                                                }`}>
                                                {user.role}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4">
                                            <span className={`inline-flex px-2 py-1 text-xs rounded-full ${user.subscription_plan === 'pro'
                                                ? 'bg-primary-500/10 text-primary-400'
                                                : 'bg-gray-500/10 text-gray-400'
                                                }`}>
                                                {user.subscription_plan || 'free'}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 text-gray-300">{user.job_count}</td>
                                        <td className="px-6 py-4 text-gray-400 text-sm">
                                            {new Date(user.created_at).toLocaleDateString()}
                                        </td>
                                    </tr>
                                ))}
                                {users.length === 0 && (
                                    <tr>
                                        <td colSpan={5} className="px-6 py-8 text-center text-gray-400">
                                            No users found
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* Jobs Tab */}
            {activeTab === 'jobs' && (
                <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
                    <div className="flex items-center justify-between mb-6">
                        <h3 className="text-lg font-semibold text-white">Job Management</h3>
                        <Link
                            to="/queue"
                            className="text-primary-400 hover:text-primary-300 text-sm"
                        >
                            View full queue →
                        </Link>
                    </div>
                    <p className="text-gray-400">
                        Detailed job management available in the queue page. Use this dashboard for overview statistics.
                    </p>
                </div>
            )}
        </div>
    )
}

function StatCard({ title, value, icon, trend }: { title: string; value: number; icon: string; trend?: string }) {
    return (
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
            <div className="flex items-center justify-between mb-3">
                <span className="text-2xl">{icon}</span>
                {trend && <span className="text-xs text-gray-400">{trend}</span>}
            </div>
            <p className="text-3xl font-bold text-white">{value.toLocaleString()}</p>
            <p className="text-gray-400 text-sm mt-1">{title}</p>
        </div>
    )
}

function QueueItem({ label, value, color }: { label: string; value: number; color: string }) {
    const colorClasses = {
        blue: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
        yellow: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30',
        green: 'bg-green-500/10 text-green-400 border-green-500/30',
        red: 'bg-red-500/10 text-red-400 border-red-500/30',
        gray: 'bg-gray-500/10 text-gray-400 border-gray-500/30',
    }

    return (
        <div className={`rounded-lg p-4 border ${colorClasses[color as keyof typeof colorClasses]}`}>
            <p className="text-2xl font-bold">{value}</p>
            <p className="text-sm opacity-80">{label}</p>
        </div>
    )
}
