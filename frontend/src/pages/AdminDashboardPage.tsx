/**
 * Admin Dashboard Page
 * Provides system overview, user management, moderation, and job monitoring.
 */

import { useState, useEffect, useMemo, useRef } from 'react'
import { createPortal } from 'react-dom'
import { Link, useSearchParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuthStore } from '@/stores/authStore'
import { API_CONFIG } from '@/lib/config'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { Select } from '@/components/ui/Dropdown'
import {
    AnimatedTabContent,
    AnimatedTabButton,
    StaggerPageContent,
    StaggerSection,
    PageContentWrapper,
    TRANSITION_DURATION,
    EASE_CURVE
} from '@/components/ui/UnifiedTransitions'
import { useAdminReports, useUpdateReportStatus } from '@/api/socialHooks'
import type { ReportStatus, AdminReport } from '@/api/social'
import { Avatar } from '@/components/ui/Avatar'

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
    display_name: string
    total_reviews: number
    approved: number
    rejected: number
    avg_review_time_hours: number | null
}

interface AdminUser {
    id: string
    user_number: number | null  // Human-friendly ID
    email: string
    display_name: string
    role: string
    email_verified: boolean
    phone_verified: boolean
    karma_score: number
    created_at: string
    subscription_plan: string | null
    subscription_status: string | null
    job_count: number
    last_active: string | null
    restriction_level: string
    is_restricted: boolean
    is_banned: boolean
    user_warnings: number
}

// User tag type (like osu!'s DEV, VIP, etc.)
interface UserTag {
    id: number
    name: string
    background_color: string
    text_color: string | null
    description: string | null
    display_order: number
    created_at: string
}

// Sorting types
type SortField = 'display_name' | 'email' | 'role' | 'created_at' | 'karma_score' | 'job_count' | 'restriction_level'
type SortDirection = 'asc' | 'desc'

const VALID_TABS = ['overview', 'users', 'jobs', 'contributions', 'reports'] as const
type TabType = typeof VALID_TABS[number]

// Helper to get valid tab from URL
function getTabFromUrl(searchParams: URLSearchParams): TabType {
    const tab = searchParams.get('tab')
    if (tab && (VALID_TABS as readonly string[]).includes(tab)) {
        return tab as TabType
    }
    return 'overview'
}

export function AdminDashboardPage() {
    useDocumentTitle('admin')
    const { accessToken } = useAuthStore()
    const [searchParams, setSearchParams] = useSearchParams()

    // Use URL as source of truth - derive tab from URL on every render
    // This ensures tab persists on refresh and browser navigation
    const activeTab = getTabFromUrl(searchParams)

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
    const [contributionsLoading, setContributionsLoading] = useState(false)
    const [contributionsError, setContributionsError] = useState<string | null>(null)

    // Sorting state for users table
    const [sortField, setSortField] = useState<SortField>('created_at')
    const [sortDirection, setSortDirection] = useState<SortDirection>('desc')

    // Filter state for users table
    const [roleFilter, setRoleFilter] = useState<string>('all')
    const [statusFilter, setStatusFilter] = useState<string>('all')

    // Moderation modal state
    const [moderationModalUser, setModerationModalUser] = useState<AdminUser | null>(null)
    const [moderationAction, setModerationAction] = useState<'silence' | 'restrict' | 'ban' | 'note' | null>(null)
    const [moderationReason, setModerationReason] = useState('')
    const [moderationDuration, setModerationDuration] = useState(24)
    const [moderationPermanent, setModerationPermanent] = useState(false)
    const [moderationSubmitting, setModerationSubmitting] = useState(false)

    // Tags modal state (like osu!'s DEV, VIP tags)
    const [tagsModalUser, setTagsModalUser] = useState<AdminUser | null>(null)
    const [userTags, setUserTags] = useState<UserTag[]>([])
    const [tagsLoading, setTagsLoading] = useState(false)
    const [newTagName, setNewTagName] = useState('')
    const [newTagBgColor, setNewTagBgColor] = useState('#ec4899')  // Pink (primary)
    const [newTagTextColor, setNewTagTextColor] = useState('#ffffff')
    const [useCustomColors, setUseCustomColors] = useState(false)
    const [tagSubmitting, setTagSubmitting] = useState(false)

    // Default tag colors that match the app theme
    const DEFAULT_TAG_COLORS = [
        { name: 'Pink', bg: '#ec4899', text: '#ffffff' },      // Primary/accent
        { name: 'Purple', bg: '#8b5cf6', text: '#ffffff' },    // Verifier color
        { name: 'Blue', bg: '#3b82f6', text: '#ffffff' },      // Standard link color
        { name: 'Green', bg: '#22c55e', text: '#ffffff' },     // Success/verified
        { name: 'Yellow', bg: '#eab308', text: '#000000' },    // Warning/caution
        { name: 'Orange', bg: '#f97316', text: '#ffffff' },    // Energetic
        { name: 'Red', bg: '#ef4444', text: '#ffffff' },       // Admin/important
        { name: 'Cyan', bg: '#06b6d4', text: '#ffffff' },      // Cool accent
        { name: 'Slate', bg: '#64748b', text: '#ffffff' },     // Neutral
    ]

    // Helper function to get color name from hex
    const getColorDisplayName = (bgColor: string): string => {
        const match = DEFAULT_TAG_COLORS.find(c => c.bg.toLowerCase() === bgColor.toLowerCase())
        return match ? match.name : bgColor.toUpperCase()
    }

    // Actions dropdown state
    const [openActionsUserId, setOpenActionsUserId] = useState<string | null>(null)
    const [dropdownPosition, setDropdownPosition] = useState<{ top: number; left: number } | null>(null)
    const actionsDropdownRef = useRef<HTMLDivElement>(null)
    const actionButtonRefs = useRef<Map<string, HTMLButtonElement>>(new Map())

    // Close actions dropdown when clicking outside
    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            const target = event.target as Node
            // Check if click is outside dropdown
            if (actionsDropdownRef.current && !actionsDropdownRef.current.contains(target)) {
                // Also check if click is on any action button (handled separately)
                let isActionButton = false
                actionButtonRefs.current.forEach((btn) => {
                    if (btn && btn.contains(target)) isActionButton = true
                })
                if (!isActionButton) {
                    setOpenActionsUserId(null)
                    setDropdownPosition(null)
                }
            }
        }

        if (openActionsUserId) {
            document.addEventListener('mousedown', handleClickOutside)
            return () => document.removeEventListener('mousedown', handleClickOutside)
        }
    }, [openActionsUserId])

    // Update URL when tab changes (URL is source of truth, so just update URL)
    const handleTabChange = (tab: TabType) => {
        setSearchParams({ tab }, { replace: true })
    }

    const fetchWithAuth = async (endpoint: string) => {
        const response = await fetch(`${API_CONFIG.baseUrl}/api${endpoint}`, {
            headers: {
                'Authorization': `Bearer ${accessToken}`,
                'Content-Type': 'application/json',
            },
        })
        if (!response.ok) {
            if (response.status === 401) {
                throw new Error('Session expired. Please log in again.')
            }
            if (response.status === 403) {
                throw new Error('Access denied. Admin permissions required.')
            }
            if (response.status === 404) {
                throw new Error(`API endpoint not found: ${endpoint}. This may be a configuration issue.`)
            }
            // Try to get error detail from response
            try {
                const errorData = await response.json()
                throw new Error(errorData.detail || `Request failed with status ${response.status}`)
            } catch {
                throw new Error(`Request failed with status ${response.status}`)
            }
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
        setContributionsLoading(true)
        setContributionsError(null)
        try {
            const [statsData, leaderboardData] = await Promise.all([
                fetchWithAuth('/contributions/export-stats'),
                fetchWithAuth('/verifier/leaderboard').catch(() => ({ verifiers: [] })),
            ])
            setContributionStats(statsData)
            setVerifierLeaderboard(leaderboardData.verifiers || [])
        } catch (err) {
            console.warn('Failed to load contribution stats:', err)
            setContributionsError(err instanceof Error ? err.message : 'Failed to load contribution statistics')
        } finally {
            setContributionsLoading(false)
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
            const response = await fetch(`${API_CONFIG.baseUrl}/api/admin/users/${userId}/role`, {
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

    // Filtered and sorted users
    const sortedUsers = useMemo(() => {
        if (!users || users.length === 0) return []

        // Apply filters first
        let filtered = [...users]

        // Role filter
        if (roleFilter !== 'all') {
            filtered = filtered.filter(user => user.role === roleFilter)
        }

        // Status filter
        if (statusFilter !== 'all') {
            switch (statusFilter) {
                case 'active':
                    filtered = filtered.filter(user => user.restriction_level === 'none')
                    break
                case 'silenced':
                    filtered = filtered.filter(user => user.restriction_level === 'silenced')
                    break
                case 'restricted':
                    filtered = filtered.filter(user => user.restriction_level === 'restricted')
                    break
                case 'banned':
                    filtered = filtered.filter(user => user.restriction_level === 'banned')
                    break
            }
        }

        // Then sort
        return filtered.sort((a, b) => {
            let comparison = 0

            switch (sortField) {
                case 'display_name':
                    comparison = a.display_name.localeCompare(b.display_name)
                    break
                case 'email':
                    comparison = a.email.localeCompare(b.email)
                    break
                case 'role':
                    comparison = a.role.localeCompare(b.role)
                    break
                case 'created_at':
                    comparison = new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
                    break
                case 'karma_score':
                    comparison = a.karma_score - b.karma_score
                    break
                case 'job_count':
                    comparison = a.job_count - b.job_count
                    break
                case 'restriction_level':
                    comparison = a.restriction_level.localeCompare(b.restriction_level)
                    break
                default:
                    comparison = 0
            }

            return sortDirection === 'asc' ? comparison : -comparison
        })
    }, [users, sortField, sortDirection, roleFilter, statusFilter])

    // Handle sort column click
    const handleSort = (field: SortField) => {
        if (sortField === field) {
            setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
        } else {
            setSortField(field)
            setSortDirection('desc')
        }
    }

    // Sort indicator component
    const SortIndicator = ({ field }: { field: SortField }) => {
        if (sortField !== field) return <span className="text-gray-600">↕</span>
        return sortDirection === 'asc'
            ? <span className="text-primary-400">↑</span>
            : <span className="text-primary-400">↓</span>
    }

    // Moderation action handler
    const handleModerationSubmit = async () => {
        if (!moderationModalUser || !moderationAction) return

        setModerationSubmitting(true)
        try {
            let endpoint = ''
            let body: Record<string, unknown> = {}

            switch (moderationAction) {
                case 'silence':
                    endpoint = `/api/admin/users/${moderationModalUser.id}/silence`
                    body = { duration_hours: moderationDuration, reason: moderationReason }
                    break
                case 'restrict':
                    endpoint = `/api/admin/users/${moderationModalUser.id}/restrict`
                    body = {
                        duration_hours: moderationPermanent ? null : moderationDuration,
                        reason: moderationReason
                    }
                    break
                case 'ban':
                    endpoint = `/api/admin/users/${moderationModalUser.id}/ban`
                    body = {
                        permanent: moderationPermanent,
                        duration_hours: moderationPermanent ? null : moderationDuration,
                        reason: moderationReason
                    }
                    break
                case 'note':
                    endpoint = `/api/admin/users/${moderationModalUser.id}/add-note`
                    body = { note: moderationReason }
                    break
            }

            const response = await fetch(`${API_CONFIG.baseUrl}${endpoint}`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(body),
            })

            if (!response.ok) {
                const data = await response.json().catch(() => ({ detail: 'Action failed' }))
                throw new Error(data.detail || 'Action failed')
            }

            setSuccessMessage(`${moderationAction.charAt(0).toUpperCase() + moderationAction.slice(1)} action successful`)
            setTimeout(() => setSuccessMessage(null), 3000)

            // Close modal and refresh users
            setModerationModalUser(null)
            setModerationAction(null)
            setModerationReason('')
            loadUsers()
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Action failed')
        } finally {
            setModerationSubmitting(false)
        }
    }

    // Remove restriction handler
    const handleRemoveRestriction = async (userId: string) => {
        if (!confirm('Are you sure you want to remove all restrictions from this user?')) return

        try {
            const response = await fetch(`${API_CONFIG.baseUrl}/api/admin/users/${userId}/remove-restriction`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                    'Content-Type': 'application/json',
                },
            })

            if (!response.ok) {
                const data = await response.json().catch(() => ({ detail: 'Action failed' }))
                throw new Error(data.detail || 'Action failed')
            }

            setSuccessMessage('Restriction removed successfully')
            setTimeout(() => setSuccessMessage(null), 3000)
            loadUsers()
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Action failed')
        }
    }

    // Tags management functions
    const loadUserTags = async (userId: string) => {
        setTagsLoading(true)
        try {
            const response = await fetch(`${API_CONFIG.baseUrl}/api/admin/users/${userId}/tags`, {
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                },
            })
            if (response.ok) {
                const data = await response.json()
                setUserTags(data.tags || [])
            }
        } catch (err) {
            console.error('Failed to load user tags:', err)
        } finally {
            setTagsLoading(false)
        }
    }

    const handleAddTag = async () => {
        if (!tagsModalUser || !newTagName.trim()) return

        setTagSubmitting(true)
        try {
            const response = await fetch(`${API_CONFIG.baseUrl}/api/admin/users/${tagsModalUser.id}/tags`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    name: newTagName.trim(),
                    background_color: newTagBgColor,
                    text_color: newTagTextColor || '#ffffff',
                    display_order: userTags.length,
                }),
            })

            if (!response.ok) {
                throw new Error('Failed to add tag')
            }

            const newTag = await response.json()
            setUserTags([...userTags, newTag])
            setNewTagName('')
            setSuccessMessage('Tag added successfully')
            setTimeout(() => setSuccessMessage(null), 3000)
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to add tag')
        } finally {
            setTagSubmitting(false)
        }
    }

    const handleDeleteTag = async (tagId: number) => {
        if (!tagsModalUser || !confirm('Are you sure you want to remove this tag?')) return

        try {
            const response = await fetch(`${API_CONFIG.baseUrl}/api/admin/users/${tagsModalUser.id}/tags/${tagId}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                },
            })

            if (!response.ok) {
                throw new Error('Failed to delete tag')
            }

            setUserTags(userTags.filter(t => t.id !== tagId))
            setSuccessMessage('Tag removed')
            setTimeout(() => setSuccessMessage(null), 3000)
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to delete tag')
        }
    }

    const openTagsModal = (user: AdminUser) => {
        setTagsModalUser(user)
        setNewTagName('')
        setNewTagBgColor('#ec4899')  // Default to Pink
        setNewTagTextColor('#ffffff')
        setUseCustomColors(false)
        loadUserTags(user.id)
    }

    if (loading) {
        return (
            <PageContentWrapper isLoading={true} className="flex items-center justify-center min-h-[60vh]">
                <div className="animate-spin h-10 w-10 border-4 border-primary-500 border-t-transparent rounded-full" />
            </PageContentWrapper>
        )
    }

    if (error && !overview) {
        return (
            <PageContentWrapper className="flex items-center justify-center min-h-[60vh]">
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
            </PageContentWrapper>
        )
    }

    return (
        <PageContentWrapper className="max-w-7xl mx-auto px-4 py-8">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold text-white">Admin Dashboard</h1>
                    <p className="text-gray-400 text-sm sm:text-base mt-1">System monitoring and management</p>
                </div>
            </div>

            {/* Tabs */}
            <div className="overflow-x-auto -mx-4 px-4 sm:mx-0 sm:px-0 pb-2 mb-8">
                <div className="flex gap-1 p-1 bg-dark-400 rounded-lg w-fit">
                    {(['overview', 'users', 'jobs', 'contributions', 'reports'] as const).map((tab) => (
                        <AnimatedTabButton
                            key={tab}
                            isActive={activeTab === tab}
                            onClick={() => handleTabChange(tab)}
                            label={tab.charAt(0).toUpperCase() + tab.slice(1)}
                            variant="pills"
                        />
                    ))}
                </div>
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

            {/* Tab Content with Unified Transitions */}
            <AnimatedTabContent activeTab={activeTab}>
                {/* Overview Tab */}
                {activeTab === 'overview' && overview && userStats && queueStats && (
                    <StaggerPageContent className="space-y-8">
                        {/* Key Metrics Grid */}
                        <StaggerSection>
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
                        </StaggerSection>

                        {/* Queue Status */}
                        <StaggerSection>
                            <div className="bg-dark-400 rounded-xl p-6 border border-white/10">
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
                        </StaggerSection>

                        {/* User Stats */}
                        <StaggerSection>
                            <div className="bg-dark-400 rounded-xl p-6 border border-white/10">
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
                                <div className="mt-4 pt-4 border-t border-white/10">
                                    <p className="text-gray-400 text-sm">
                                        {userStats.verified_users} verified ({((userStats.verified_users / userStats.total_users) * 100).toFixed(0)}%)
                                    </p>
                                </div>
                            </div>
                        </StaggerSection>
                    </StaggerPageContent>
                )}

                {/* Users Tab */}
                {activeTab === 'users' && (
                    <StaggerPageContent className="space-y-6">
                        {/* Search and Filters */}
                        <StaggerSection>
                            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                                <div className="flex-1 min-w-0 relative">
                                    <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                                    </svg>
                                    <input
                                        type="text"
                                        placeholder="Search by email or name..."
                                        value={searchQuery}
                                        onChange={(e) => setSearchQuery(e.target.value)}
                                        className="w-full pl-10 pr-4 py-2.5 bg-dark-400 border border-white/10 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500"
                                    />
                                </div>

                                {/* Filters row - wraps properly on mobile */}
                                <div className="flex flex-wrap sm:flex-nowrap items-center gap-3">
                                    {/* Role Filter */}
                                    <Select
                                        value={roleFilter}
                                        onValueChange={(value) => setRoleFilter(value)}
                                        className="w-full sm:w-[150px] flex-shrink-0"
                                        size="md"
                                        options={[
                                            { value: 'all', label: 'All Roles' },
                                            { value: 'user', label: 'User' },
                                            { value: 'verifier', label: 'Verifier' },
                                            { value: 'staff', label: 'Staff' },
                                            { value: 'admin', label: 'Admin' },
                                        ]}
                                    />

                                    {/* Status Filter */}
                                    <Select
                                        value={statusFilter}
                                        onValueChange={(value) => setStatusFilter(value)}
                                        className="w-full sm:w-[160px] flex-shrink-0"
                                        size="md"
                                        options={[
                                            { value: 'all', label: 'All Statuses' },
                                            { value: 'active', label: 'Active' },
                                            { value: 'silenced', label: 'Silenced' },
                                            { value: 'restricted', label: 'Restricted' },
                                            { value: 'banned', label: 'Banned' },
                                        ]}
                                    />

                                    <button
                                        onClick={loadUsers}
                                        className="w-full sm:w-auto px-4 py-2.5 bg-primary-500 hover:bg-primary-600 text-white rounded-lg font-medium transition-colors flex-shrink-0"
                                    >
                                        Search
                                    </button>
                                </div>
                            </div>
                        </StaggerSection>

                        {/* Results count */}
                        {users.length > 0 && (
                            <StaggerSection>
                                <div className="flex items-center justify-between text-sm text-gray-400">
                                    <span>
                                        Showing {sortedUsers.length} of {users.length} users
                                        {(roleFilter !== 'all' || statusFilter !== 'all') && (
                                            <button
                                                onClick={() => {
                                                    setRoleFilter('all')
                                                    setStatusFilter('all')
                                                }}
                                                className="ml-2 text-primary-400 hover:text-primary-300"
                                            >
                                                Clear filters
                                            </button>
                                        )}
                                    </span>
                                </div>
                            </StaggerSection>
                        )}

                        {/* Users Table */}
                        <StaggerSection>
                            <div className="bg-dark-400 rounded-xl border border-white/10 overflow-x-auto">
                                <table className="w-full min-w-[900px]">
                                    <thead className="bg-dark-500">
                                        <tr>
                                            <th
                                                onClick={() => handleSort('display_name')}
                                                className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider cursor-pointer hover:text-white"
                                            >
                                                User <SortIndicator field="display_name" />
                                            </th>
                                            <th
                                                onClick={() => handleSort('role')}
                                                className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider cursor-pointer hover:text-white"
                                            >
                                                Role <SortIndicator field="role" />
                                            </th>
                                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                                                Plan
                                            </th>
                                            <th
                                                onClick={() => handleSort('karma_score')}
                                                className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider cursor-pointer hover:text-white"
                                            >
                                                Karma <SortIndicator field="karma_score" />
                                            </th>
                                            <th
                                                onClick={() => handleSort('job_count')}
                                                className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider cursor-pointer hover:text-white"
                                            >
                                                Jobs <SortIndicator field="job_count" />
                                            </th>
                                            <th
                                                onClick={() => handleSort('created_at')}
                                                className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider cursor-pointer hover:text-white"
                                            >
                                                Joined <SortIndicator field="created_at" />
                                            </th>
                                            <th
                                                onClick={() => handleSort('restriction_level')}
                                                className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider cursor-pointer hover:text-white"
                                            >
                                                Status <SortIndicator field="restriction_level" />
                                            </th>
                                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                                                Actions
                                            </th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-700">
                                        {sortedUsers.map((user) => (
                                            <tr key={user.id} className="hover:bg-dark-300/50">
                                                <td className="px-4 py-3">
                                                    <div className="flex items-center gap-2">
                                                        <div className={`w-8 h-8 rounded-full flex items-center justify-center ${user.is_banned ? 'bg-red-500/20' :
                                                            user.is_restricted ? 'bg-yellow-500/20' :
                                                                'bg-primary-500/20'
                                                            }`}>
                                                            <span className={`font-medium text-sm ${user.is_banned ? 'text-red-400' :
                                                                user.is_restricted ? 'text-yellow-400' :
                                                                    'text-primary-400'
                                                                }`}>
                                                                {user.display_name.charAt(0).toUpperCase()}
                                                            </span>
                                                        </div>
                                                        <div className="min-w-0">
                                                            <Link to={`/user/${user.user_number ?? user.id}`} className="text-white font-medium truncate hover:text-primary-400 transition-colors block">
                                                                {user.display_name}
                                                            </Link>
                                                            <p className="text-gray-400 text-xs truncate">{user.email}</p>
                                                        </div>
                                                        <div className="flex gap-1 flex-shrink-0">
                                                            {user.email_verified && (
                                                                <svg className="w-4 h-4 text-green-500" fill="currentColor" viewBox="0 0 20 20" aria-label="Email Verified">
                                                                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                                                                </svg>
                                                            )}
                                                            {user.phone_verified && (
                                                                <svg className="w-4 h-4 text-blue-500" fill="currentColor" viewBox="0 0 20 20" aria-label="Phone Verified">
                                                                    <path d="M2 3a1 1 0 011-1h2.153a1 1 0 01.986.836l.74 4.435a1 1 0 01-.54 1.06l-1.548.773a11.037 11.037 0 006.105 6.105l.774-1.548a1 1 0 011.059-.54l4.435.74a1 1 0 01.836.986V17a1 1 0 01-1 1h-2C7.82 18 2 12.18 2 5V3z" />
                                                                </svg>
                                                            )}
                                                        </div>
                                                    </div>
                                                </td>
                                                <td className="px-4 py-3">
                                                    <select
                                                        value={user.role}
                                                        onChange={(e) => handleUpdateRole(user.id, e.target.value)}
                                                        disabled={updatingRoleUserId === user.id}
                                                        className={`text-xs rounded-full px-2 py-1 border-0 cursor-pointer ${user.role === 'admin' ? 'bg-red-500/10 text-red-400' :
                                                            user.role === 'verifier' ? 'bg-purple-500/10 text-purple-400' :
                                                                'bg-gray-500/10 text-gray-400'
                                                            } disabled:opacity-50`}
                                                    >
                                                        <option value="user">User</option>
                                                        <option value="verifier">Verifier</option>
                                                        <option value="admin">Admin</option>
                                                    </select>
                                                </td>
                                                <td className="px-4 py-3">
                                                    <span className={`inline-flex px-2 py-1 text-xs rounded-full ${user.subscription_plan?.includes('pro')
                                                        ? 'bg-primary-500/10 text-primary-400'
                                                        : 'bg-gray-500/10 text-gray-400'
                                                        }`}>
                                                        {user.subscription_plan || 'free'}
                                                    </span>
                                                </td>
                                                <td className="px-4 py-3 text-gray-300 text-sm">{user.karma_score}</td>
                                                <td className="px-4 py-3 text-gray-300 text-sm">{user.job_count}</td>
                                                <td className="px-4 py-3 text-gray-400 text-xs">
                                                    {new Date(user.created_at).toLocaleDateString()}
                                                </td>
                                                <td className="px-4 py-3">
                                                    {user.is_banned ? (
                                                        <span className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-red-500/20 text-red-400">
                                                            <span className="w-1.5 h-1.5 rounded-full bg-red-400"></span>
                                                            Banned
                                                        </span>
                                                    ) : user.is_restricted ? (
                                                        <span className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-yellow-500/20 text-yellow-400">
                                                            <span className="w-1.5 h-1.5 rounded-full bg-yellow-400"></span>
                                                            {user.restriction_level}
                                                        </span>
                                                    ) : (
                                                        <span className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-green-500/20 text-green-400">
                                                            <span className="w-1.5 h-1.5 rounded-full bg-green-400"></span>
                                                            Active
                                                        </span>
                                                    )}
                                                    {user.user_warnings > 0 && (
                                                        <span className="ml-1 text-xs text-yellow-500" title={`${user.user_warnings} warning(s)`}>
                                                            ⚠️{user.user_warnings}
                                                        </span>
                                                    )}
                                                </td>
                                                <td className="px-4 py-3">
                                                    <div className="flex items-center gap-1">
                                                        {/* Moderation dropdown trigger */}
                                                        <button
                                                            ref={(el) => {
                                                                if (el) actionButtonRefs.current.set(user.id, el)
                                                                else actionButtonRefs.current.delete(user.id)
                                                            }}
                                                            onClick={() => {
                                                                if (openActionsUserId === user.id) {
                                                                    setOpenActionsUserId(null)
                                                                    setDropdownPosition(null)
                                                                } else {
                                                                    const btn = actionButtonRefs.current.get(user.id)
                                                                    if (btn) {
                                                                        const rect = btn.getBoundingClientRect()
                                                                        setDropdownPosition({
                                                                            top: rect.bottom + 4,
                                                                            left: rect.right - 192, // 192px = w-48
                                                                        })
                                                                    }
                                                                    setOpenActionsUserId(user.id)
                                                                }
                                                            }}
                                                            className="p-1.5 rounded hover:bg-dark-300 text-gray-400 hover:text-white"
                                                        >
                                                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z" />
                                                            </svg>
                                                        </button>
                                                    </div>
                                                </td>
                                            </tr>
                                        ))}
                                        {sortedUsers.length === 0 && (
                                            <tr>
                                                <td colSpan={8} className="px-6 py-8 text-center text-gray-400">
                                                    No users found
                                                </td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </StaggerSection>

                        {/* Actions Dropdown Portal */}
                        {openActionsUserId && dropdownPosition && createPortal(
                            <AnimatePresence>
                                <motion.div
                                    ref={actionsDropdownRef}
                                    initial={{ opacity: 0, scale: 0.95, y: -10 }}
                                    animate={{ opacity: 1, scale: 1, y: 0 }}
                                    exit={{ opacity: 0, scale: 0.95, y: -10 }}
                                    transition={{ duration: TRANSITION_DURATION, ease: EASE_CURVE }}
                                    style={{
                                        position: 'fixed',
                                        top: dropdownPosition.top,
                                        left: dropdownPosition.left,
                                    }}
                                    className="w-48 bg-dark-400 border border-white/10 rounded-lg shadow-xl z-[9999]"
                                >
                                    <div className="p-1">
                                        {(() => {
                                            const user = users.find(u => u.id === openActionsUserId)
                                            if (!user) return null
                                            return (
                                                <>
                                                    <button
                                                        onClick={() => {
                                                            openTagsModal(user)
                                                            setOpenActionsUserId(null)
                                                            setDropdownPosition(null)
                                                        }}
                                                        className="w-full text-left px-3 py-2 text-sm text-primary-400 hover:bg-dark-300 rounded"
                                                    >
                                                        🏷️ Tags
                                                    </button>
                                                    <div className="border-t border-white/10 my-1" />
                                                    <button
                                                        onClick={() => {
                                                            setModerationModalUser(user)
                                                            setModerationAction('note')
                                                            setOpenActionsUserId(null)
                                                            setDropdownPosition(null)
                                                        }}
                                                        className="w-full text-left px-3 py-2 text-sm text-gray-300 hover:bg-dark-300 rounded"
                                                    >
                                                        📝 Add Note
                                                    </button>
                                                    {!user.is_restricted && (
                                                        <>
                                                            <button
                                                                onClick={() => {
                                                                    setModerationModalUser(user)
                                                                    setModerationAction('silence')
                                                                    setModerationDuration(24)
                                                                    setOpenActionsUserId(null)
                                                                    setDropdownPosition(null)
                                                                }}
                                                                className="w-full text-left px-3 py-2 text-sm text-yellow-400 hover:bg-dark-300 rounded"
                                                            >
                                                                🔇 Silence
                                                            </button>
                                                            <button
                                                                onClick={() => {
                                                                    setModerationModalUser(user)
                                                                    setModerationAction('restrict')
                                                                    setModerationDuration(168)
                                                                    setOpenActionsUserId(null)
                                                                    setDropdownPosition(null)
                                                                }}
                                                                className="w-full text-left px-3 py-2 text-sm text-orange-400 hover:bg-dark-300 rounded"
                                                            >
                                                                ⚠️ Restrict
                                                            </button>
                                                            <button
                                                                onClick={() => {
                                                                    setModerationModalUser(user)
                                                                    setModerationAction('ban')
                                                                    setModerationPermanent(false)
                                                                    setModerationDuration(720)
                                                                    setOpenActionsUserId(null)
                                                                    setDropdownPosition(null)
                                                                }}
                                                                className="w-full text-left px-3 py-2 text-sm text-red-400 hover:bg-dark-300 rounded"
                                                            >
                                                                🚫 Ban
                                                            </button>
                                                        </>
                                                    )}
                                                    {user.is_restricted && (
                                                        <button
                                                            onClick={() => {
                                                                handleRemoveRestriction(user.id)
                                                                setOpenActionsUserId(null)
                                                                setDropdownPosition(null)
                                                            }}
                                                            className="w-full text-left px-3 py-2 text-sm text-green-400 hover:bg-dark-300 rounded"
                                                        >
                                                            ✅ Remove Restriction
                                                        </button>
                                                    )}
                                                </>
                                            )
                                        })()}
                                    </div>
                                </motion.div>
                            </AnimatePresence>,
                            document.body
                        )}

                        {/* Moderation Modal */}
                        {moderationModalUser && moderationAction && (
                            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
                                <div className="bg-dark-400 rounded-xl border border-white/10 p-6 w-full max-w-md mx-4">
                                    <h3 className="text-lg font-semibold text-white mb-4">
                                        {moderationAction === 'note' && '📝 Add Note'}
                                        {moderationAction === 'silence' && '🔇 Silence User'}
                                        {moderationAction === 'restrict' && '⚠️ Restrict User'}
                                        {moderationAction === 'ban' && '🚫 Ban User'}
                                    </h3>

                                    <p className="text-gray-400 text-sm mb-4">
                                        User: <span className="text-white">{moderationModalUser.display_name}</span> ({moderationModalUser.email})
                                    </p>

                                    {moderationAction !== 'note' && (
                                        <div className="mb-4">
                                            <label className="block text-sm text-gray-400 mb-1">Duration</label>
                                            {moderationAction === 'ban' && (
                                                <label className="flex items-center gap-2 mb-2 text-sm text-gray-300">
                                                    <input
                                                        type="checkbox"
                                                        checked={moderationPermanent}
                                                        onChange={(e) => setModerationPermanent(e.target.checked)}
                                                        className="rounded"
                                                    />
                                                    Permanent
                                                </label>
                                            )}
                                            {!moderationPermanent && (
                                                <select
                                                    value={moderationDuration}
                                                    onChange={(e) => setModerationDuration(Number(e.target.value))}
                                                    className="w-full bg-dark-300 border border-gray-600 text-white rounded-lg px-3 py-2"
                                                >
                                                    <option value={1}>1 hour</option>
                                                    <option value={6}>6 hours</option>
                                                    <option value={24}>24 hours</option>
                                                    <option value={72}>3 days</option>
                                                    <option value={168}>1 week</option>
                                                    <option value={336}>2 weeks</option>
                                                    <option value={720}>1 month</option>
                                                    <option value={2160}>3 months</option>
                                                </select>
                                            )}
                                        </div>
                                    )}

                                    <div className="mb-4">
                                        <label className="block text-sm text-gray-400 mb-1">
                                            {moderationAction === 'note' ? 'Note' : 'Reason'}
                                        </label>
                                        <textarea
                                            value={moderationReason}
                                            onChange={(e) => setModerationReason(e.target.value)}
                                            placeholder={moderationAction === 'note' ? 'Enter administrative note...' : 'Enter reason for this action...'}
                                            className="w-full bg-dark-300 border border-gray-600 text-white rounded-lg px-3 py-2 h-24 resize-none"
                                            required
                                        />
                                    </div>

                                    <div className="flex gap-3 justify-end">
                                        <button
                                            onClick={() => {
                                                setModerationModalUser(null)
                                                setModerationAction(null)
                                                setModerationReason('')
                                            }}
                                            className="px-4 py-2 text-gray-400 hover:text-white transition-colors"
                                        >
                                            Cancel
                                        </button>
                                        <button
                                            onClick={handleModerationSubmit}
                                            disabled={!moderationReason.trim() || moderationSubmitting}
                                            className={`px-4 py-2 rounded-lg font-medium transition-colors disabled:opacity-50 ${moderationAction === 'note' ? 'bg-blue-500 hover:bg-blue-600 text-white' :
                                                moderationAction === 'silence' ? 'bg-yellow-500 hover:bg-yellow-600 text-black' :
                                                    moderationAction === 'restrict' ? 'bg-orange-500 hover:bg-orange-600 text-white' :
                                                        'bg-red-500 hover:bg-red-600 text-white'
                                                }`}
                                        >
                                            {moderationSubmitting ? 'Submitting...' : 'Confirm'}
                                        </button>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Tags Modal (like osu!'s DEV, VIP tags) */}
                        {tagsModalUser && (
                            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
                                <div className="bg-dark-400 rounded-xl border border-white/10 p-6 w-full max-w-md mx-4 max-h-[80vh] overflow-y-auto">
                                    <h3 className="text-lg font-semibold text-white mb-2">🏷️ Manage Tags</h3>
                                    <p className="text-gray-400 text-sm mb-4">
                                        User: <Link to={`/user/${tagsModalUser.user_number ?? tagsModalUser.id}`} className="text-primary-400 hover:underline">{tagsModalUser.display_name}</Link>
                                    </p>

                                    {/* Current Tags */}
                                    <div className="mb-6">
                                        <label className="block text-sm text-gray-400 mb-2">Current Tags</label>
                                        {tagsLoading ? (
                                            <div className="flex items-center justify-center py-4">
                                                <div className="w-5 h-5 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
                                            </div>
                                        ) : userTags.length === 0 ? (
                                            <p className="text-gray-500 text-sm py-2">No tags assigned</p>
                                        ) : (
                                            <div className="space-y-2">
                                                {userTags.map((tag) => (
                                                    <div
                                                        key={tag.id}
                                                        className="flex items-center justify-between bg-dark-300 rounded-lg p-2"
                                                    >
                                                        <div className="flex items-center gap-3">
                                                            <span
                                                                className="px-2 py-1 rounded text-xs font-bold"
                                                                style={{
                                                                    backgroundColor: tag.background_color,
                                                                    color: tag.text_color || '#ffffff',
                                                                }}
                                                            >
                                                                {tag.name}
                                                            </span>
                                                            <span className="text-xs text-gray-500 font-mono">
                                                                {getColorDisplayName(tag.background_color)}
                                                            </span>
                                                        </div>
                                                        <button
                                                            onClick={() => handleDeleteTag(tag.id)}
                                                            className="text-gray-400 hover:text-red-400 transition-colors"
                                                        >
                                                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                                            </svg>
                                                        </button>
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </div>

                                    {/* Add New Tag */}
                                    <div className="border-t border-white/10 pt-4">
                                        <label className="block text-sm text-gray-400 mb-2">Add New Tag</label>

                                        <div className="space-y-3">
                                            <input
                                                type="text"
                                                value={newTagName}
                                                onChange={(e) => setNewTagName(e.target.value.toUpperCase())}
                                                placeholder="Tag name (e.g., DEV, VIP, MAPPER)"
                                                maxLength={32}
                                                className="w-full bg-dark-300 border border-gray-600 text-white rounded-lg px-3 py-2 text-sm"
                                            />

                                            {/* Custom Colors Toggle */}
                                            <label className="flex items-center gap-2 text-sm text-gray-300">
                                                <input
                                                    type="checkbox"
                                                    checked={useCustomColors}
                                                    onChange={(e) => setUseCustomColors(e.target.checked)}
                                                    className="rounded"
                                                />
                                                Use custom colors
                                            </label>

                                            {!useCustomColors ? (
                                                /* Default Color Presets */
                                                <div>
                                                    <label className="block text-xs text-gray-500 mb-2">Select Color</label>
                                                    <div className="grid grid-cols-3 gap-2">
                                                        {DEFAULT_TAG_COLORS.map((color) => (
                                                            <button
                                                                key={color.name}
                                                                onClick={() => {
                                                                    setNewTagBgColor(color.bg)
                                                                    setNewTagTextColor(color.text)
                                                                }}
                                                                className={`flex items-center gap-2 px-3 py-2 rounded-lg border transition-all ${newTagBgColor === color.bg
                                                                    ? 'border-white/50 bg-dark-200'
                                                                    : 'border-white/10 hover:border-white/30'
                                                                    }`}
                                                            >
                                                                <div
                                                                    className="w-4 h-4 rounded"
                                                                    style={{ backgroundColor: color.bg }}
                                                                />
                                                                <span className="text-xs text-gray-300">{color.name}</span>
                                                            </button>
                                                        ))}
                                                    </div>
                                                </div>
                                            ) : (
                                                /* Custom Color Pickers */
                                                <div className="space-y-3">
                                                    <div>
                                                        <label className="block text-xs text-gray-500 mb-1">Background Color</label>
                                                        <div className="flex items-center gap-2">
                                                            <input
                                                                type="color"
                                                                value={newTagBgColor}
                                                                onChange={(e) => setNewTagBgColor(e.target.value)}
                                                                className="w-10 h-8 rounded cursor-pointer border-0"
                                                            />
                                                            <input
                                                                type="text"
                                                                value={newTagBgColor}
                                                                onChange={(e) => setNewTagBgColor(e.target.value)}
                                                                className="flex-1 bg-dark-300 border border-gray-600 text-white rounded px-2 py-1 text-xs font-mono"
                                                            />
                                                        </div>
                                                    </div>
                                                    <div>
                                                        <label className="block text-xs text-gray-500 mb-1">Text Color</label>
                                                        <div className="flex items-center gap-2">
                                                            <input
                                                                type="color"
                                                                value={newTagTextColor}
                                                                onChange={(e) => setNewTagTextColor(e.target.value)}
                                                                className="w-10 h-8 rounded cursor-pointer border-0"
                                                            />
                                                            <input
                                                                type="text"
                                                                value={newTagTextColor}
                                                                onChange={(e) => setNewTagTextColor(e.target.value)}
                                                                className="flex-1 bg-dark-300 border border-gray-600 text-white rounded px-2 py-1 text-xs font-mono"
                                                            />
                                                        </div>
                                                    </div>
                                                </div>
                                            )}

                                            {/* Preview */}
                                            {newTagName && (
                                                <div className="flex items-center gap-2 pt-2">
                                                    <span className="text-xs text-gray-500">Preview:</span>
                                                    <span
                                                        className="px-2 py-1 rounded text-xs font-bold"
                                                        style={{
                                                            backgroundColor: newTagBgColor,
                                                            color: newTagTextColor,
                                                        }}
                                                    >
                                                        {newTagName}
                                                    </span>
                                                    <span className="text-xs text-gray-500 font-mono">
                                                        ({getColorDisplayName(newTagBgColor)})
                                                    </span>
                                                </div>
                                            )}
                                        </div>
                                    </div>

                                    <div className="flex gap-3 justify-end mt-6">
                                        <button
                                            onClick={() => {
                                                setTagsModalUser(null)
                                                setUserTags([])
                                            }}
                                            className="px-4 py-2 text-gray-400 hover:text-white transition-colors"
                                        >
                                            Close
                                        </button>
                                        <button
                                            onClick={handleAddTag}
                                            disabled={!newTagName.trim() || tagSubmitting}
                                            className="px-4 py-2 bg-primary-500 hover:bg-primary-600 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
                                        >
                                            {tagSubmitting ? 'Adding...' : 'Add Tag'}
                                        </button>
                                    </div>
                                </div>
                            </div>
                        )}
                    </StaggerPageContent>
                )}

                {/* Jobs Tab */}
                {activeTab === 'jobs' && queueStats && (
                    <StaggerPageContent className="space-y-6">
                        {/* Job Stats Overview */}
                        <StaggerSection>
                            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                                <div className="bg-blue-500/10 rounded-xl p-4 border border-blue-500/30">
                                    <p className="text-3xl font-bold text-blue-400">{queueStats.queued}</p>
                                    <p className="text-sm text-blue-300/80">Queued</p>
                                </div>
                                <div className="bg-yellow-500/10 rounded-xl p-4 border border-yellow-500/30">
                                    <p className="text-3xl font-bold text-yellow-400">{queueStats.processing}</p>
                                    <p className="text-sm text-yellow-300/80">Processing</p>
                                </div>
                                <div className="bg-green-500/10 rounded-xl p-4 border border-green-500/30">
                                    <p className="text-3xl font-bold text-green-400">{queueStats.complete}</p>
                                    <p className="text-sm text-green-300/80">Complete</p>
                                </div>
                                <div className="bg-red-500/10 rounded-xl p-4 border border-red-500/30">
                                    <p className="text-3xl font-bold text-red-400">{queueStats.failed}</p>
                                    <p className="text-sm text-red-300/80">Failed</p>
                                </div>
                                <div className="bg-gray-500/10 rounded-xl p-4 border border-gray-500/30">
                                    <p className="text-3xl font-bold text-gray-400">{queueStats.cancelled}</p>
                                    <p className="text-sm text-gray-300/80">Cancelled</p>
                                </div>
                            </div>

                            {/* Additional Stats */}
                            <div className="bg-dark-400 rounded-xl p-6 border border-white/10">
                                <h3 className="text-lg font-semibold text-white mb-4">Processing Statistics</h3>
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                                    <div>
                                        <p className="text-2xl font-bold text-white">{queueStats.total_jobs.toLocaleString()}</p>
                                        <p className="text-gray-400 text-sm">Total Jobs</p>
                                    </div>
                                    <div>
                                        <p className="text-2xl font-bold text-white">{queueStats.jobs_today}</p>
                                        <p className="text-gray-400 text-sm">Jobs Today</p>
                                    </div>
                                    <div>
                                        <p className="text-2xl font-bold text-white">{queueStats.jobs_this_hour}</p>
                                        <p className="text-gray-400 text-sm">Jobs This Hour</p>
                                    </div>
                                    <div>
                                        <p className="text-2xl font-bold text-white">
                                            {queueStats.avg_processing_time_seconds
                                                ? `${Math.round(queueStats.avg_processing_time_seconds)}s`
                                                : 'N/A'
                                            }
                                        </p>
                                        <p className="text-gray-400 text-sm">Avg Processing Time</p>
                                    </div>
                                </div>
                            </div>

                            {/* Quick Actions */}
                            <div className="bg-dark-400 rounded-xl p-6 border border-white/10">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <h3 className="text-lg font-semibold text-white">Job Management</h3>
                                        <p className="text-gray-400 text-sm mt-1">
                                            View detailed job information, retry failed jobs, and manage the processing queue.
                                        </p>
                                    </div>
                                    <Link
                                        to="/queue"
                                        className="px-4 py-2 bg-primary-500 hover:bg-primary-600 text-white rounded-lg font-medium transition-colors"
                                    >
                                        View Full Queue →
                                    </Link>
                                </div>
                            </div>
                        </StaggerSection>
                    </StaggerPageContent>
                )}

                {/* Contributions Tab */}
                {activeTab === 'contributions' && (
                    <StaggerPageContent className="space-y-6">
                        {/* Contribution Stats Cards */}
                        {contributionStats && (
                            <StaggerSection>
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
                            </StaggerSection>
                        )}

                        {/* Approval Metrics */}
                        {contributionStats && (
                            <StaggerSection>
                                <div className="bg-dark-400 rounded-xl p-6 border border-white/10">
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
                            </StaggerSection>
                        )}

                        {/* Correction Types Breakdown */}
                        {contributionStats && Object.keys(contributionStats.correction_types_approved).length > 0 && (
                            <StaggerSection>
                                <div className="bg-dark-400 rounded-xl p-6 border border-white/10">
                                    <h3 className="text-lg font-semibold text-white mb-4">Correction Types (Approved)</h3>
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                                        {Object.entries(contributionStats.correction_types_approved).map(([type, count]) => (
                                            <div key={type} className="bg-dark-300/50 rounded-lg p-3">
                                                <p className="text-lg font-bold text-white">{count}</p>
                                                <p className="text-sm text-gray-400 capitalize">{type.replace(/_/g, ' ')}</p>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </StaggerSection>
                        )}

                        {/* Verifier Leaderboard */}
                        {verifierLeaderboard.length > 0 && (
                            <StaggerSection>
                                <div className="bg-dark-400 rounded-xl p-6 border border-white/10">
                                    <h3 className="text-lg font-semibold text-white mb-4">Top Verifiers</h3>
                                    <div className="space-y-3">
                                        {verifierLeaderboard.slice(0, 10).map((verifier, index) => (
                                            <div key={verifier.verifier_id} className="flex items-center justify-between bg-dark-300/50 rounded-lg p-3">
                                                <div className="flex items-center gap-3">
                                                    <span className={`w-6 h-6 flex items-center justify-center rounded-full text-sm font-bold ${index === 0 ? 'bg-yellow-500 text-black' :
                                                        index === 1 ? 'bg-gray-400 text-black' :
                                                            index === 2 ? 'bg-amber-600 text-white' :
                                                                'bg-gray-600 text-white'
                                                        }`}>
                                                        {index + 1}
                                                    </span>
                                                    <span className="text-white font-medium">@{verifier.display_name}</span>
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
                            </StaggerSection>
                        )}

                        {contributionsLoading && (
                            <StaggerSection>
                                <div className="bg-dark-400 rounded-xl p-8 border border-white/10 text-center">
                                    <div className="flex items-center justify-center gap-3">
                                        <div className="animate-spin h-5 w-5 border-2 border-primary-500 border-t-transparent rounded-full" />
                                        <p className="text-gray-400">Loading contribution statistics...</p>
                                    </div>
                                </div>
                            </StaggerSection>
                        )}

                        {contributionsError && !contributionsLoading && (
                            <StaggerSection>
                                <div className="bg-red-500/10 rounded-xl p-6 border border-red-500/30 text-center">
                                    <p className="text-red-400">{contributionsError}</p>
                                    <button
                                        onClick={loadContributions}
                                        className="mt-4 px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg transition-colors"
                                    >
                                        Retry
                                    </button>
                                </div>
                            </StaggerSection>
                        )}

                        {!contributionStats && !contributionsLoading && !contributionsError && (
                            <StaggerSection>
                                <div className="bg-dark-400 rounded-xl p-8 border border-white/10 text-center">
                                    <p className="text-gray-400">No contribution statistics available</p>
                                </div>
                            </StaggerSection>
                        )}
                    </StaggerPageContent>
                )}

                {/* Reports Tab */}
                {activeTab === 'reports' && (
                    <StaggerPageContent className="space-y-6">
                        <ReportsTabContent />
                    </StaggerPageContent>
                )}
            </AnimatedTabContent>
        </PageContentWrapper>
    )
}

function StatCard({ title, value, icon, trend }: { title: string; value: number; icon: string; trend?: string }) {
    return (
        <div className="bg-dark-400 rounded-xl p-5 border border-white/10">
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
        blue: 'bg-dark-300 text-blue-400 border-white/10',
        yellow: 'bg-dark-300 text-yellow-400 border-white/10',
        green: 'bg-dark-300 text-green-400 border-white/10',
        red: 'bg-dark-300 text-red-400 border-white/10',
        gray: 'bg-dark-300 text-gray-400 border-white/10',
    }

    return (
        <div className={`rounded-lg p-4 border ${colorClasses[color as keyof typeof colorClasses]}`}>
            <p className="text-2xl font-bold">{value}</p>
            <p className="text-sm text-gray-400">{label}</p>
        </div>
    )
}

// =============================================================================
// Reports Tab Content
// =============================================================================

function ReportsTabContent() {
    const [statusFilter, setStatusFilter] = useState<ReportStatus | undefined>(undefined)
    const { data: reportsData, isLoading, error, refetch } = useAdminReports({ status: statusFilter })
    const updateReportStatus = useUpdateReportStatus()
    const [selectedReport, setSelectedReport] = useState<AdminReport | null>(null)
    const [adminNotes, setAdminNotes] = useState('')
    const [actionStatus, setActionStatus] = useState<ReportStatus | null>(null)

    const handleResolveReport = async () => {
        if (!selectedReport || !actionStatus) return

        try {
            await updateReportStatus.mutateAsync({
                reportId: selectedReport.id,
                status: actionStatus,
                adminNotes: adminNotes || undefined,
            })
            setSelectedReport(null)
            setAdminNotes('')
            setActionStatus(null)
        } catch (err) {
            console.error('Failed to update report:', err)
        }
    }

    const getStatusColor = (status: ReportStatus) => {
        switch (status) {
            case 'pending':
                return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
            case 'under_review':
                return 'bg-blue-500/20 text-blue-400 border-blue-500/30'
            case 'resolved':
                return 'bg-green-500/20 text-green-400 border-green-500/30'
            case 'dismissed':
                return 'bg-gray-500/20 text-gray-400 border-gray-500/30'
            default:
                return 'bg-gray-500/20 text-gray-400 border-gray-500/30'
        }
    }

    const getReportTypeIcon = (type: string) => {
        switch (type) {
            case 'spam':
                return '📧'
            case 'harassment':
                return '⚠️'
            case 'inappropriate_content':
                return '🚫'
            case 'cheating':
                return '🎮'
            case 'impersonation':
                return '👤'
            case 'copyright':
                return '©️'
            default:
                return '📋'
        }
    }

    if (isLoading) {
        return (
            <StaggerSection>
                <div className="bg-dark-400 rounded-xl p-8 border border-white/10 text-center">
                    <div className="flex items-center justify-center gap-3">
                        <div className="animate-spin h-5 w-5 border-2 border-primary-500 border-t-transparent rounded-full" />
                        <p className="text-gray-400">Loading reports...</p>
                    </div>
                </div>
            </StaggerSection>
        )
    }

    if (error) {
        return (
            <StaggerSection>
                <div className="bg-red-500/10 rounded-xl p-6 border border-red-500/30 text-center">
                    <p className="text-red-400">Failed to load reports</p>
                    <button
                        onClick={() => refetch()}
                        className="mt-4 px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg transition-colors"
                    >
                        Retry
                    </button>
                </div>
            </StaggerSection>
        )
    }

    return (
        <>
            {/* Filter Bar */}
            <StaggerSection>
                <div className="bg-dark-400 rounded-xl p-4 border border-white/10">
                    <div className="flex flex-wrap items-center gap-4">
                        <span className="text-white font-medium">Filter by status:</span>
                        <div className="flex gap-2 flex-wrap">
                            <button
                                onClick={() => setStatusFilter(undefined)}
                                className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${!statusFilter
                                    ? 'bg-primary-500 text-white'
                                    : 'bg-dark-300 text-gray-400 hover:text-white'
                                    }`}
                            >
                                All
                            </button>
                            {(['pending', 'under_review', 'resolved', 'dismissed'] as ReportStatus[]).map((status) => (
                                <button
                                    key={status}
                                    onClick={() => setStatusFilter(status)}
                                    className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${statusFilter === status
                                        ? 'bg-primary-500 text-white'
                                        : 'bg-dark-300 text-gray-400 hover:text-white'
                                        }`}
                                >
                                    {status.replace('_', ' ').charAt(0).toUpperCase() + status.replace('_', ' ').slice(1)}
                                </button>
                            ))}
                        </div>
                        <span className="ml-auto text-gray-500 text-sm">
                            {reportsData?.total || 0} reports
                        </span>
                    </div>
                </div>
            </StaggerSection>

            {/* Reports List */}
            <StaggerSection>
                <div className="bg-dark-400 rounded-xl border border-white/10 overflow-hidden">
                    {reportsData?.items && reportsData.items.length > 0 ? (
                        <div className="divide-y divide-white/10">
                            {reportsData.items.map((report) => (
                                <div
                                    key={report.id}
                                    className="p-4 hover:bg-dark-300/50 transition-colors cursor-pointer"
                                    onClick={() => {
                                        setSelectedReport(report)
                                        setAdminNotes(report.admin_notes || '')
                                    }}
                                >
                                    <div className="flex items-start gap-4">
                                        {/* Report Type Icon */}
                                        <div className="text-2xl">
                                            {getReportTypeIcon(report.report_type)}
                                        </div>

                                        {/* Report Content */}
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2 mb-1">
                                                <span className={`px-2 py-0.5 rounded text-xs border ${getStatusColor(report.status)}`}>
                                                    {report.status.replace('_', ' ')}
                                                </span>
                                                <span className="text-xs text-gray-500">
                                                    {new Date(report.created_at).toLocaleDateString()}
                                                </span>
                                            </div>

                                            <p className="text-white font-medium">
                                                {report.report_type.replace('_', ' ').charAt(0).toUpperCase() +
                                                    report.report_type.replace('_', ' ').slice(1)}
                                            </p>

                                            <p className="text-gray-400 text-sm mt-1 line-clamp-2">
                                                {report.description}
                                            </p>

                                            <div className="flex items-center gap-4 mt-2 text-sm">
                                                <div className="flex items-center gap-2">
                                                    <Avatar
                                                        src={report.reporter.avatar_url || undefined}
                                                        alt={report.reporter.display_name}
                                                        size="xs"
                                                    />
                                                    <span className="text-gray-400">
                                                        from <span className="text-white">{report.reporter.display_name}</span>
                                                    </span>
                                                </div>
                                                <span className="text-gray-600">→</span>
                                                <div className="flex items-center gap-2">
                                                    <Avatar
                                                        src={report.reported_user.avatar_url || undefined}
                                                        alt={report.reported_user.display_name}
                                                        size="xs"
                                                    />
                                                    <span className="text-gray-400">
                                                        about <Link
                                                            to={`/user/${report.reported_user.user_number}`}
                                                            className="text-primary-400 hover:text-primary-300"
                                                            onClick={(e) => e.stopPropagation()}
                                                        >
                                                            {report.reported_user.display_name}
                                                        </Link>
                                                    </span>
                                                </div>
                                            </div>
                                        </div>

                                        {/* Action Arrow */}
                                        <svg
                                            className="w-5 h-5 text-gray-500"
                                            fill="none"
                                            viewBox="0 0 24 24"
                                            stroke="currentColor"
                                        >
                                            <path
                                                strokeLinecap="round"
                                                strokeLinejoin="round"
                                                strokeWidth={2}
                                                d="M9 5l7 7-7 7"
                                            />
                                        </svg>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="p-8 text-center">
                            <p className="text-gray-400">No reports found</p>
                        </div>
                    )}
                </div>
            </StaggerSection>

            {/* Report Detail Modal */}
            <AnimatePresence>
                {selectedReport && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
                        onClick={() => setSelectedReport(null)}
                    >
                        <motion.div
                            initial={{ opacity: 0, scale: 0.95 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.95 }}
                            className="bg-dark-500 rounded-xl border border-white/10 max-w-2xl w-full max-h-[80vh] overflow-y-auto"
                            onClick={(e) => e.stopPropagation()}
                        >
                            {/* Header */}
                            <div className="p-6 border-b border-white/10">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-3">
                                        <span className="text-3xl">{getReportTypeIcon(selectedReport.report_type)}</span>
                                        <div>
                                            <h3 className="text-xl font-bold text-white">
                                                {selectedReport.report_type.replace('_', ' ').charAt(0).toUpperCase() +
                                                    selectedReport.report_type.replace('_', ' ').slice(1)} Report
                                            </h3>
                                            <p className="text-gray-400 text-sm">
                                                Submitted {new Date(selectedReport.created_at).toLocaleString()}
                                            </p>
                                        </div>
                                    </div>
                                    <span className={`px-3 py-1 rounded-lg text-sm border ${getStatusColor(selectedReport.status)}`}>
                                        {selectedReport.status.replace('_', ' ')}
                                    </span>
                                </div>
                            </div>

                            {/* Content */}
                            <div className="p-6 space-y-6">
                                {/* Users */}
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="bg-dark-400 rounded-lg p-4">
                                        <p className="text-gray-400 text-sm mb-2">Reporter</p>
                                        <div className="flex items-center gap-3">
                                            <Avatar
                                                src={selectedReport.reporter.avatar_url || undefined}
                                                alt={selectedReport.reporter.display_name}
                                                size="md"
                                            />
                                            <div>
                                                <Link
                                                    to={`/user/${selectedReport.reporter.user_number}`}
                                                    className="text-white font-medium hover:text-primary-400"
                                                >
                                                    {selectedReport.reporter.display_name}
                                                </Link>
                                                <p className="text-gray-500 text-sm">@{selectedReport.reporter.display_name}</p>
                                            </div>
                                        </div>
                                    </div>
                                    <div className="bg-dark-400 rounded-lg p-4">
                                        <p className="text-gray-400 text-sm mb-2">Reported User</p>
                                        <div className="flex items-center gap-3">
                                            <Avatar
                                                src={selectedReport.reported_user.avatar_url || undefined}
                                                alt={selectedReport.reported_user.display_name}
                                                size="md"
                                            />
                                            <div>
                                                <Link
                                                    to={`/user/${selectedReport.reported_user.user_number}`}
                                                    className="text-white font-medium hover:text-primary-400"
                                                >
                                                    {selectedReport.reported_user.display_name}
                                                </Link>
                                                <p className="text-gray-500 text-sm">@{selectedReport.reported_user.display_name}</p>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                {/* Description */}
                                <div>
                                    <p className="text-gray-400 text-sm mb-2">Description</p>
                                    <div className="bg-dark-400 rounded-lg p-4">
                                        <p className="text-white whitespace-pre-wrap">{selectedReport.description}</p>
                                    </div>
                                </div>

                                {/* Admin Notes */}
                                <div>
                                    <label className="text-gray-400 text-sm mb-2 block">Admin Notes</label>
                                    <textarea
                                        value={adminNotes}
                                        onChange={(e) => setAdminNotes(e.target.value)}
                                        className="w-full bg-dark-400 border border-white/10 rounded-lg p-4 text-white placeholder-gray-500 focus:outline-none focus:border-primary-500"
                                        placeholder="Add internal notes about this report..."
                                        rows={3}
                                    />
                                </div>

                                {/* Action Selection */}
                                {(selectedReport.status === 'pending' || selectedReport.status === 'under_review') && (
                                    <div>
                                        <p className="text-gray-400 text-sm mb-2">Take Action</p>
                                        <div className="flex gap-2 flex-wrap">
                                            <button
                                                onClick={() => setActionStatus('under_review')}
                                                className={`px-4 py-2 rounded-lg text-sm transition-colors ${actionStatus === 'under_review'
                                                    ? 'bg-blue-500 text-white'
                                                    : 'bg-dark-400 text-gray-400 hover:text-white border border-white/10'
                                                    }`}
                                            >
                                                Mark Under Review
                                            </button>
                                            <button
                                                onClick={() => setActionStatus('resolved')}
                                                className={`px-4 py-2 rounded-lg text-sm transition-colors ${actionStatus === 'resolved'
                                                    ? 'bg-green-500 text-white'
                                                    : 'bg-dark-400 text-gray-400 hover:text-white border border-white/10'
                                                    }`}
                                            >
                                                Resolve
                                            </button>
                                            <button
                                                onClick={() => setActionStatus('dismissed')}
                                                className={`px-4 py-2 rounded-lg text-sm transition-colors ${actionStatus === 'dismissed'
                                                    ? 'bg-gray-500 text-white'
                                                    : 'bg-dark-400 text-gray-400 hover:text-white border border-white/10'
                                                    }`}
                                            >
                                                Dismiss
                                            </button>
                                        </div>
                                    </div>
                                )}

                                {/* Reviewed By */}
                                {selectedReport.reviewed_by && (
                                    <div className="bg-dark-400 rounded-lg p-4">
                                        <p className="text-gray-400 text-sm mb-2">Reviewed by</p>
                                        <div className="flex items-center gap-2">
                                            <Avatar
                                                src={selectedReport.reviewed_by.avatar_url || undefined}
                                                alt={selectedReport.reviewed_by.display_name}
                                                size="sm"
                                            />
                                            <span className="text-white">{selectedReport.reviewed_by.display_name}</span>
                                            {selectedReport.reviewed_at && (
                                                <span className="text-gray-500 text-sm">
                                                    on {new Date(selectedReport.reviewed_at).toLocaleString()}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* Footer */}
                            <div className="p-6 border-t border-white/10 flex justify-end gap-3">
                                <button
                                    onClick={() => setSelectedReport(null)}
                                    className="px-4 py-2 bg-dark-400 text-white rounded-lg hover:bg-dark-300 transition-colors"
                                >
                                    Close
                                </button>
                                {actionStatus && (
                                    <button
                                        onClick={handleResolveReport}
                                        disabled={updateReportStatus.isPending}
                                        className="px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 transition-colors disabled:opacity-50"
                                    >
                                        {updateReportStatus.isPending ? 'Saving...' : 'Save Changes'}
                                    </button>
                                )}
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
        </>
    )
}
