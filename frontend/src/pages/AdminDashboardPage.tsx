/**
 * Admin Dashboard Page
 * Provides system overview, user management, and job monitoring.
 */

import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { API_CONFIG } from '@/lib/config'

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

interface ContributionStats {
    total_contributions: number
    pending_review: number
    approved: number
    rejected: number
    exported: number
    pending_export: number
    correction_types_approved: Record<string, number>
}

interface VerifierLeaderboard {
    verifier_id: string
    username: string
    total_reviews: number
    approved: number
    rejected: number
    avg_review_time_hours: number | null
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
    const [activeTab, setActiveTab] = useState<'overview' | 'users' | 'jobs' | 'contributions'>('overview')
    const [overview, setOverview] = useState<SystemOverview | null>(null)
    const [userStats, setUserStats] = useState<UserStats | null>(null)
    const [queueStats, setQueueStats] = useState<QueueStats | null>(null)
    const [contributionStats, setContributionStats] = useState<ContributionStats | null>(null)
    const [verifierLeaderboard, setVerifierLeaderboard] = useState<VerifierLeaderboard[]>([])
    const [users, setUsers] = useState<AdminUser[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [searchQuery, setSearchQuery] = useState('')
    const [updatingRoleUserId, setUpdatingRoleUserId] = useState<string | null>(null)
    const [successMessage, setSuccessMessage] = useState<string | null>(null)

    const fetchWithAuth = async (endpoint: string) => {
        const response = await fetch(`${API_CONFIG.baseUrl}${endpoint}`, {
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

    const loadContributions = async () => {
        try {
            const [statsData, leaderboardData] = await Promise.all([
                fetchWithAuth('/contributions/export-stats'),
                fetchWithAuth('/verifier/leaderboard').catch(() => ({ verifiers: [] })),
            ])
            setContributionStats(statsData)
            setVerifierLeaderboard(leaderboardData.verifiers || [])
        } catch (err) {
            // Don't set error, just leave stats empty
            console.warn('Failed to load contribution stats:', err)
        }
    }

    useEffect(() => {
        if (activeTab === 'contributions' && accessToken) {
            loadContributions()
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [activeTab, accessToken])

    // Update user role
    const handleUpdateRole = async (userId: string, newRole: string) => {
        if (!accessToken) return
        setUpdatingRoleUserId(userId)
        setError(null)
        try {
            const response = await fetch(`${API_CONFIG.baseUrl}/admin/users/${userId}/role`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ role: newRole }),
            })
            if (!response.ok) {
                const data = await response.json().catch(() => ({ detail: 'Failed to update role' }))
                throw new Error(data.detail || 'Failed to update role')
            }
            // Update local state
            setUsers(users.map(u => u.id === userId ? { ...u, role: newRole } : u))
            setSuccessMessage(`Role updated to ${newRole}`)
            setTimeout(() => setSuccessMessage(null), 3000)
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to update role')
        } finally {
            setUpdatingRoleUserId(null)
        }
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-[60vh]">
                <div className="animate-spin h-10 w-10 border-4 border-primary-500 border-t-transparent rounded-full" />
            </div>
        )
    }

    if (error && !overview) {
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
                {(['overview', 'users', 'jobs', 'contributions'] as const).map((tab) => (
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

            {/* Success/Error Messages */}
            {successMessage && (
                <div className="mb-4 p-4 bg-green-500/10 border border-green-500/30 rounded-lg flex items-center gap-2">
                    <svg className="w-5 h-5 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span className="text-green-400">{successMessage}</span>
                </div>
            )}
            {error && !loading && (
                <div className="mb-4 p-4 bg-red-500/10 border border-red-500/30 rounded-lg flex items-center gap-2">
                    <svg className="w-5 h-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span className="text-red-400">{error}</span>
                    <button onClick={() => setError(null)} className="ml-auto text-red-400 hover:text-red-300">
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
            )}

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
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Actions</th>
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
                                                user.role === 'verifier' ? 'bg-purple-500/10 text-purple-400' :
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
                                        <td className="px-6 py-4">
                                            <select
                                                value={user.role}
                                                onChange={(e) => handleUpdateRole(user.id, e.target.value)}
                                                disabled={updatingRoleUserId === user.id}
                                                className="bg-gray-700 border border-gray-600 text-white text-sm rounded-lg 
                                                         px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-primary-500
                                                         disabled:opacity-50 disabled:cursor-not-allowed"
                                            >
                                                <option value="user">User</option>
                                                <option value="verifier">Verifier</option>
                                                <option value="admin">Admin</option>
                                            </select>
                                            {updatingRoleUserId === user.id && (
                                                <span className="ml-2 text-gray-400 text-xs">Updating...</span>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                                {users.length === 0 && (
                                    <tr>
                                        <td colSpan={6} className="px-6 py-8 text-center text-gray-400">
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

            {/* Contributions Tab */}
            {activeTab === 'contributions' && (
                <div className="space-y-6">
                    {/* Contribution Stats Cards */}
                    {contributionStats && (
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <StatCard
                                title="Total Contributions"
                                value={contributionStats.total_contributions}
                                icon="📝"
                            />
                            <StatCard
                                title="Pending Review"
                                value={contributionStats.pending_review}
                                icon="⏳"
                            />
                            <StatCard
                                title="Approved"
                                value={contributionStats.approved}
                                icon="✅"
                            />
                            <StatCard
                                title="Exported for Training"
                                value={contributionStats.exported}
                                icon="🚀"
                            />
                        </div>
                    )}

                    {/* Approval Metrics */}
                    {contributionStats && (
                        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
                            <h3 className="text-lg font-semibold text-white mb-4">Approval Metrics</h3>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                <div className="bg-green-500/10 rounded-lg p-4 border border-green-500/30">
                                    <p className="text-2xl font-bold text-green-400">
                                        {contributionStats.total_contributions > 0
                                            ? ((contributionStats.approved + contributionStats.exported) / contributionStats.total_contributions * 100).toFixed(1)
                                            : 0}%
                                    </p>
                                    <p className="text-sm text-green-300/80">Approval Rate</p>
                                </div>
                                <div className="bg-yellow-500/10 rounded-lg p-4 border border-yellow-500/30">
                                    <p className="text-2xl font-bold text-yellow-400">{contributionStats.pending_export}</p>
                                    <p className="text-sm text-yellow-300/80">Ready for Export</p>
                                </div>
                                <div className="bg-red-500/10 rounded-lg p-4 border border-red-500/30">
                                    <p className="text-2xl font-bold text-red-400">{contributionStats.rejected}</p>
                                    <p className="text-sm text-red-300/80">Rejected</p>
                                </div>
                                <div className="bg-blue-500/10 rounded-lg p-4 border border-blue-500/30">
                                    <p className="text-2xl font-bold text-blue-400">
                                        {(contributionStats.approved + contributionStats.exported) * 15}
                                    </p>
                                    <p className="text-sm text-blue-300/80">Karma Distributed</p>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Correction Types Breakdown */}
                    {contributionStats && Object.keys(contributionStats.correction_types_approved).length > 0 && (
                        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
                            <h3 className="text-lg font-semibold text-white mb-4">Correction Types (Approved)</h3>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                                {Object.entries(contributionStats.correction_types_approved).map(([type, count]) => (
                                    <div key={type} className="bg-gray-700/50 rounded-lg p-3">
                                        <p className="text-lg font-bold text-white">{count}</p>
                                        <p className="text-sm text-gray-400 capitalize">{type.replace(/_/g, ' ')}</p>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Verifier Leaderboard */}
                    {verifierLeaderboard.length > 0 && (
                        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
                            <h3 className="text-lg font-semibold text-white mb-4">Top Verifiers</h3>
                            <div className="space-y-3">
                                {verifierLeaderboard.slice(0, 10).map((verifier, index) => (
                                    <div key={verifier.verifier_id} className="flex items-center justify-between bg-gray-700/50 rounded-lg p-3">
                                        <div className="flex items-center gap-3">
                                            <span className={`w-6 h-6 flex items-center justify-center rounded-full text-sm font-bold ${index === 0 ? 'bg-yellow-500 text-black' :
                                                index === 1 ? 'bg-gray-400 text-black' :
                                                    index === 2 ? 'bg-amber-600 text-white' :
                                                        'bg-gray-600 text-white'
                                                }`}>
                                                {index + 1}
                                            </span>
                                            <span className="text-white font-medium">@{verifier.username}</span>
                                        </div>
                                        <div className="flex items-center gap-4 text-sm">
                                            <span className="text-gray-400">{verifier.total_reviews} reviews</span>
                                            <span className="text-green-400">+{verifier.approved}</span>
                                            <span className="text-red-400">-{verifier.rejected}</span>
                                            {verifier.avg_review_time_hours && (
                                                <span className="text-gray-500">
                                                    ~{verifier.avg_review_time_hours.toFixed(1)}h avg
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {!contributionStats && (
                        <div className="bg-gray-800 rounded-xl p-8 border border-gray-700 text-center">
                            <p className="text-gray-400">Loading contribution statistics...</p>
                        </div>
                    )}
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
