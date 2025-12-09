/**
 * Verifier Dashboard Page
 * Allows verifiers to review and approve/reject map edit proposals.
 */

import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { ProposalDiffViewer, type DiffPayload } from '@/components/ProposalDiffViewer'
import { API_CONFIG } from '@/lib/config'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'

interface Proposer {
    id: string
    username: string
    avatar_url: string | null
}

interface Decision {
    id: string
    decision: 'approve' | 'reject' | 'needs_changes'
    notes: string | null
    verifier_id: string
    verifier_username: string | null
    decided_at: string
}

interface Proposal {
    id: string
    map_version_id: string
    proposer: Proposer
    summary: string
    diff_payload: Record<string, unknown>
    status: 'pending' | 'approved' | 'rejected' | 'withdrawn'
    submitted_at: string
    updated_at: string
    decision: Decision | null
}

interface VerifierStats {
    pending_count: number
    approved_today: number
    rejected_today: number
    total_reviewed_by_user: number
    avg_review_time_hours: number | null
}

const VALID_TABS = ['queue', 'history'] as const
type TabType = typeof VALID_TABS[number]

export function VerifierDashboardPage() {
    useDocumentTitle('verifier')
    const { accessToken } = useAuthStore()
    const [searchParams, setSearchParams] = useSearchParams()

    // Get tab from URL or default to 'queue'
    const tabFromUrl = searchParams.get('tab') as TabType | null
    const initialTab: TabType = tabFromUrl && VALID_TABS.includes(tabFromUrl) ? tabFromUrl : 'queue'
    const [activeTab, setActiveTab] = useState<TabType>(initialTab)

    const [stats, setStats] = useState<VerifierStats | null>(null)
    const [proposals, setProposals] = useState<Proposal[]>([])
    const [myDecisions, setMyDecisions] = useState<Proposal[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [selectedProposal, setSelectedProposal] = useState<Proposal | null>(null)
    const [decisionNotes, setDecisionNotes] = useState('')
    const [submitting, setSubmitting] = useState(false)
    const [_page, setPage] = useState(1)
    const [hasMore, setHasMore] = useState(false)

    const fetchWithAuth = async (endpoint: string, options?: RequestInit) => {
        const response = await fetch(`${API_CONFIG.baseUrl}/api${endpoint}`, {
            ...options,
            headers: {
                'Authorization': `Bearer ${accessToken}`,
                'Content-Type': 'application/json',
                ...options?.headers,
            },
        })
        if (!response.ok) {
            if (response.status === 401) {
                throw new Error('Session expired. Please log in again.')
            }
            if (response.status === 403) {
                throw new Error('Access denied. Verifier permissions required.')
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

    // Update URL when tab changes
    const handleTabChange = (tab: TabType) => {
        setActiveTab(tab)
        setSearchParams({ tab }, { replace: true })
    }

    // Sync tab state with URL on mount and URL changes
    useEffect(() => {
        const tabFromUrl = searchParams.get('tab')
        if (tabFromUrl && (VALID_TABS as readonly string[]).includes(tabFromUrl)) {
            setActiveTab(tabFromUrl as TabType)
        }
    }, [searchParams])

    const loadData = async () => {
        try {
            setLoading(true)
            setError(null)

            const [statsData, pendingData] = await Promise.all([
                fetchWithAuth('/verifier/stats'),
                fetchWithAuth('/verifier/proposals?status_filter=pending&page=1&page_size=20'),
            ])

            setStats(statsData)
            setProposals(pendingData.items)
            setHasMore(pendingData.has_next)
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to load verifier data')
        } finally {
            setLoading(false)
        }
    }

    const loadMyDecisions = async () => {
        try {
            setLoading(true)
            const data = await fetchWithAuth('/verifier/my-decisions?page=1&page_size=50')
            setMyDecisions(data.items)
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to load decision history')
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        loadData()
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [accessToken])

    useEffect(() => {
        if (activeTab === 'history') {
            loadMyDecisions()
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [activeTab])

    const handleDecision = async (proposalId: string, decision: 'approve' | 'reject' | 'needs_changes') => {
        try {
            setSubmitting(true)
            await fetchWithAuth(`/verifier/proposals/${proposalId}/decision`, {
                method: 'POST',
                body: JSON.stringify({
                    decision,
                    notes: decisionNotes || null,
                }),
            })

            // Refresh the list
            setSelectedProposal(null)
            setDecisionNotes('')
            await loadData()
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to submit decision')
        } finally {
            setSubmitting(false)
        }
    }

    const formatDate = (dateStr: string) => {
        const date = new Date(dateStr)
        return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
        })
    }

    const getStatusBadge = (status: string) => {
        const colors: Record<string, string> = {
            pending: 'bg-yellow-500/20 text-yellow-400',
            approved: 'bg-green-500/20 text-green-400',
            rejected: 'bg-red-500/20 text-red-400',
            withdrawn: 'bg-gray-500/20 text-gray-400',
        }
        return colors[status] || 'bg-gray-500/20 text-gray-400'
    }

    if (loading && !stats) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500"></div>
            </div>
        )
    }

    if (error) {
        return (
            <div className="max-w-6xl mx-auto p-6">
                <div className="bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-3 rounded-lg">
                    {error}
                </div>
            </div>
        )
    }

    return (
        <div className="max-w-6xl mx-auto p-6">
            <h1 className="text-3xl font-bold text-white mb-2">Verifier Dashboard</h1>
            <p className="text-gray-400 mb-6">Review and approve map edit proposals</p>

            {/* Stats Cards */}
            {stats && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                    <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
                        <p className="text-sm text-gray-400">Pending Queue</p>
                        <p className="text-2xl font-bold text-yellow-400">{stats.pending_count}</p>
                    </div>
                    <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
                        <p className="text-sm text-gray-400">Approved Today</p>
                        <p className="text-2xl font-bold text-green-400">{stats.approved_today}</p>
                    </div>
                    <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
                        <p className="text-sm text-gray-400">Rejected Today</p>
                        <p className="text-2xl font-bold text-red-400">{stats.rejected_today}</p>
                    </div>
                    <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
                        <p className="text-sm text-gray-400">Your Total Reviews</p>
                        <p className="text-2xl font-bold text-primary-400">{stats.total_reviewed_by_user}</p>
                    </div>
                </div>
            )}

            {/* Tabs */}
            <div className="flex gap-1 p-1 bg-gray-800 rounded-lg w-fit mb-6">
                <button
                    onClick={() => handleTabChange('queue')}
                    className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${activeTab === 'queue'
                        ? 'bg-primary-500 text-white'
                        : 'text-gray-400 hover:text-white'
                        }`}
                >
                    Pending Queue ({stats?.pending_count || 0})
                </button>
                <button
                    onClick={() => handleTabChange('history')}
                    className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${activeTab === 'history'
                        ? 'bg-primary-500 text-white'
                        : 'text-gray-400 hover:text-white'
                        }`}
                >
                    My Decision History
                </button>
            </div>

            {/* Queue Tab */}
            {activeTab === 'queue' && (
                <div className="space-y-4">
                    {proposals.length === 0 ? (
                        <div className="bg-gray-800 rounded-lg border border-gray-700 p-8 text-center">
                            <p className="text-gray-300">No pending proposals to review!</p>
                            <p className="text-sm text-gray-500 mt-2">Check back later for new submissions</p>
                        </div>
                    ) : (
                        proposals.map(proposal => (
                            <div key={proposal.id} className="bg-gray-800 rounded-lg border border-gray-700 p-4">
                                <div className="flex items-start justify-between">
                                    <div className="flex-1">
                                        <div className="flex items-center gap-2 mb-2">
                                            <span className={`px-2 py-1 text-xs rounded-full ${getStatusBadge(proposal.status)}`}>
                                                {proposal.status}
                                            </span>
                                            <span className="text-sm text-gray-400">
                                                by @{proposal.proposer.username}
                                            </span>
                                        </div>
                                        <h3 className="font-medium text-lg text-white">{proposal.summary}</h3>
                                        <p className="text-sm text-gray-400 mt-1">
                                            Submitted: {formatDate(proposal.submitted_at)}
                                        </p>

                                        {/* Diff Preview - User-friendly visualization */}
                                        <details className="mt-3">
                                            <summary className="cursor-pointer text-sm text-primary-400 hover:text-primary-300">
                                                View Changes ({(proposal.diff_payload as unknown as DiffPayload).edit_count || Object.keys(proposal.diff_payload).length} modifications)
                                            </summary>
                                            <div className="mt-2 p-3 bg-gray-900 rounded border border-gray-700">
                                                <ProposalDiffViewer diffPayload={proposal.diff_payload as unknown as DiffPayload} />
                                            </div>
                                        </details>
                                    </div>

                                    {proposal.status === 'pending' && (
                                        <div className="ml-4">
                                            <button
                                                onClick={() => setSelectedProposal(proposal)}
                                                className="px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 transition-colors"
                                            >
                                                Review
                                            </button>
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))
                    )}

                    {hasMore && (
                        <button
                            onClick={() => setPage(p => p + 1)}
                            className="w-full py-2 text-primary-400 hover:bg-gray-700 rounded-lg transition-colors"
                        >
                            Load More
                        </button>
                    )}
                </div>
            )}

            {/* History Tab */}
            {activeTab === 'history' && (
                <div className="space-y-4">
                    {myDecisions.length === 0 ? (
                        <div className="bg-gray-800 rounded-lg border border-gray-700 p-8 text-center">
                            <p className="text-gray-300">No decisions yet</p>
                            <p className="text-sm text-gray-500 mt-2">
                                Your review history will appear here
                            </p>
                        </div>
                    ) : (
                        myDecisions.map(proposal => (
                            <div key={proposal.id} className="bg-gray-800 rounded-lg border border-gray-700 p-4">
                                <div className="flex items-center gap-2 mb-2">
                                    <span className={`px-2 py-1 text-xs rounded-full ${getStatusBadge(proposal.status)}`}>
                                        {proposal.status}
                                    </span>
                                    {proposal.decision && (
                                        <span className="text-xs text-gray-400">
                                            Decision: {proposal.decision.decision}
                                        </span>
                                    )}
                                </div>
                                <h3 className="font-medium text-white">{proposal.summary}</h3>
                                <p className="text-sm text-gray-400 mt-1">
                                    by @{proposal.proposer.username} • {formatDate(proposal.submitted_at)}
                                </p>
                                {proposal.decision?.notes && (
                                    <p className="text-sm text-gray-300 mt-2 italic">
                                        "{proposal.decision.notes}"
                                    </p>
                                )}
                            </div>
                        ))
                    )}
                </div>
            )}

            {/* Review Modal */}
            {selectedProposal && (
                <div className="fixed inset-0 bg-black/70 flex items-center justify-center p-4 z-50">
                    <div className="bg-gray-800 rounded-xl border border-gray-700 max-w-2xl w-full max-h-[80vh] overflow-y-auto">
                        <div className="p-6">
                            <div className="flex items-center justify-between mb-4">
                                <h2 className="text-xl font-bold text-white">Review Proposal</h2>
                                <button
                                    onClick={() => {
                                        setSelectedProposal(null)
                                        setDecisionNotes('')
                                    }}
                                    className="text-gray-400 hover:text-white transition-colors"
                                >
                                    ✕
                                </button>
                            </div>

                            <div className="mb-4">
                                <h3 className="font-medium text-white mb-2">{selectedProposal.summary}</h3>
                                <p className="text-sm text-gray-400">
                                    Submitted by @{selectedProposal.proposer.username} on {formatDate(selectedProposal.submitted_at)}
                                </p>
                            </div>

                            <div className="mb-4">
                                <h4 className="font-medium text-gray-300 mb-2">Changes</h4>
                                <div className="border border-gray-600 rounded-lg p-4 bg-gray-900 max-h-64 overflow-y-auto">
                                    <ProposalDiffViewer diffPayload={selectedProposal.diff_payload as unknown as DiffPayload} />
                                </div>
                            </div>

                            {/* Karma Impact Preview */}
                            <div className="mb-4 bg-primary-500/10 border border-primary-500/30 rounded-lg p-4">
                                <h4 className="font-medium text-primary-400 mb-2">Karma Impact</h4>
                                <p className="text-sm text-gray-300">
                                    Your decision will affect @{selectedProposal.proposer.username}'s karma:
                                </p>
                                <div className="flex gap-4 mt-2">
                                    <span className="text-green-400 font-medium">
                                        ✓ Approve: <span className="font-bold">+25</span> karma
                                    </span>
                                    <span className="text-red-400 font-medium">
                                        ✗ Reject: <span className="font-bold">-10</span> karma
                                    </span>
                                </div>
                            </div>

                            <div className="mb-4">
                                <label className="block text-sm font-medium text-gray-300 mb-2">
                                    Decision Notes (optional)
                                </label>
                                <textarea
                                    value={decisionNotes}
                                    onChange={e => setDecisionNotes(e.target.value)}
                                    className="w-full p-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                                    rows={3}
                                    placeholder="Add feedback for the proposer..."
                                    maxLength={512}
                                />
                                <p className="text-xs text-gray-500 mt-1">
                                    {decisionNotes.length}/512 characters
                                </p>
                            </div>

                            <div className="flex gap-3">
                                <button
                                    onClick={() => handleDecision(selectedProposal.id, 'approve')}
                                    disabled={submitting}
                                    className="flex-1 py-2.5 bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:opacity-50 transition-colors font-medium"
                                >
                                    ✓ Approve
                                </button>
                                <button
                                    onClick={() => handleDecision(selectedProposal.id, 'needs_changes')}
                                    disabled={submitting}
                                    className="flex-1 py-2.5 bg-yellow-500 text-white rounded-lg hover:bg-yellow-600 disabled:opacity-50 transition-colors font-medium"
                                >
                                    ↻ Needs Changes
                                </button>
                                <button
                                    onClick={() => handleDecision(selectedProposal.id, 'reject')}
                                    disabled={submitting}
                                    className="flex-1 py-2.5 bg-red-500 text-white rounded-lg hover:bg-red-600 disabled:opacity-50 transition-colors font-medium"
                                >
                                    ✗ Reject
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
