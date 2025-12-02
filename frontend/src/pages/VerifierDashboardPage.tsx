/**
 * Verifier Dashboard Page
 * Allows verifiers to review and approve/reject map edit proposals.
 */

import { useState, useEffect } from 'react'
import { useAuthStore } from '@/stores/authStore'
import { ProposalDiffViewer, type DiffPayload } from '@/components/ProposalDiffViewer'

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

export function VerifierDashboardPage() {
    const { accessToken } = useAuthStore()
    const [activeTab, setActiveTab] = useState<'queue' | 'history'>('queue')
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
        const response = await fetch(`/api${endpoint}`, {
            ...options,
            headers: {
                'Authorization': `Bearer ${accessToken}`,
                'Content-Type': 'application/json',
                ...options?.headers,
            },
        })
        if (!response.ok) {
            if (response.status === 403) {
                throw new Error('Access denied. Verifier permissions required.')
            }
            throw new Error('Failed to fetch data')
        }
        return response.json()
    }

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
            pending: 'bg-yellow-100 text-yellow-800',
            approved: 'bg-green-100 text-green-800',
            rejected: 'bg-red-100 text-red-800',
            withdrawn: 'bg-gray-100 text-gray-800',
        }
        return colors[status] || 'bg-gray-100 text-gray-800'
    }

    if (loading && !stats) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
            </div>
        )
    }

    if (error) {
        return (
            <div className="max-w-6xl mx-auto p-6">
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
                    {error}
                </div>
            </div>
        )
    }

    return (
        <div className="max-w-6xl mx-auto p-6">
            <h1 className="text-3xl font-bold mb-2">🔍 Verifier Dashboard</h1>
            <p className="text-gray-600 mb-6">Review and approve map edit proposals</p>

            {/* Stats Cards */}
            {stats && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                    <div className="bg-white rounded-lg shadow p-4">
                        <p className="text-sm text-gray-500">Pending Queue</p>
                        <p className="text-2xl font-bold text-yellow-600">{stats.pending_count}</p>
                    </div>
                    <div className="bg-white rounded-lg shadow p-4">
                        <p className="text-sm text-gray-500">Approved Today</p>
                        <p className="text-2xl font-bold text-green-600">{stats.approved_today}</p>
                    </div>
                    <div className="bg-white rounded-lg shadow p-4">
                        <p className="text-sm text-gray-500">Rejected Today</p>
                        <p className="text-2xl font-bold text-red-600">{stats.rejected_today}</p>
                    </div>
                    <div className="bg-white rounded-lg shadow p-4">
                        <p className="text-sm text-gray-500">Your Total Reviews</p>
                        <p className="text-2xl font-bold text-blue-600">{stats.total_reviewed_by_user}</p>
                    </div>
                </div>
            )}

            {/* Tabs */}
            <div className="border-b border-gray-200 mb-6">
                <nav className="-mb-px flex space-x-8">
                    <button
                        onClick={() => setActiveTab('queue')}
                        className={`py-2 px-1 border-b-2 font-medium text-sm ${activeTab === 'queue'
                            ? 'border-blue-500 text-blue-600'
                            : 'border-transparent text-gray-500 hover:text-gray-700'
                            }`}
                    >
                        📋 Pending Queue ({stats?.pending_count || 0})
                    </button>
                    <button
                        onClick={() => setActiveTab('history')}
                        className={`py-2 px-1 border-b-2 font-medium text-sm ${activeTab === 'history'
                            ? 'border-blue-500 text-blue-600'
                            : 'border-transparent text-gray-500 hover:text-gray-700'
                            }`}
                    >
                        📜 My Decision History
                    </button>
                </nav>
            </div>

            {/* Queue Tab */}
            {activeTab === 'queue' && (
                <div className="space-y-4">
                    {proposals.length === 0 ? (
                        <div className="bg-white rounded-lg shadow p-8 text-center">
                            <p className="text-gray-500">🎉 No pending proposals to review!</p>
                            <p className="text-sm text-gray-400 mt-2">Check back later for new submissions</p>
                        </div>
                    ) : (
                        proposals.map(proposal => (
                            <div key={proposal.id} className="bg-white rounded-lg shadow p-4">
                                <div className="flex items-start justify-between">
                                    <div className="flex-1">
                                        <div className="flex items-center gap-2 mb-2">
                                            <span className={`px-2 py-1 text-xs rounded-full ${getStatusBadge(proposal.status)}`}>
                                                {proposal.status}
                                            </span>
                                            <span className="text-sm text-gray-500">
                                                by @{proposal.proposer.username}
                                            </span>
                                        </div>
                                        <h3 className="font-medium text-lg">{proposal.summary}</h3>
                                        <p className="text-sm text-gray-500 mt-1">
                                            Submitted: {formatDate(proposal.submitted_at)}
                                        </p>

                                        {/* Diff Preview - User-friendly visualization */}
                                        <details className="mt-3">
                                            <summary className="cursor-pointer text-sm text-blue-600 hover:underline">
                                                View Changes ({(proposal.diff_payload as unknown as DiffPayload).edit_count || Object.keys(proposal.diff_payload).length} modifications)
                                            </summary>
                                            <div className="mt-2 p-3 bg-gray-50 rounded">
                                                <ProposalDiffViewer diffPayload={proposal.diff_payload as unknown as DiffPayload} />
                                            </div>
                                        </details>
                                    </div>

                                    {proposal.status === 'pending' && (
                                        <div className="ml-4">
                                            <button
                                                onClick={() => setSelectedProposal(proposal)}
                                                className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
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
                            className="w-full py-2 text-blue-600 hover:bg-blue-50 rounded"
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
                        <div className="bg-white rounded-lg shadow p-8 text-center">
                            <p className="text-gray-500">No decisions yet</p>
                            <p className="text-sm text-gray-400 mt-2">
                                Your review history will appear here
                            </p>
                        </div>
                    ) : (
                        myDecisions.map(proposal => (
                            <div key={proposal.id} className="bg-white rounded-lg shadow p-4">
                                <div className="flex items-center gap-2 mb-2">
                                    <span className={`px-2 py-1 text-xs rounded-full ${getStatusBadge(proposal.status)}`}>
                                        {proposal.status}
                                    </span>
                                    {proposal.decision && (
                                        <span className="text-xs text-gray-500">
                                            Decision: {proposal.decision.decision}
                                        </span>
                                    )}
                                </div>
                                <h3 className="font-medium">{proposal.summary}</h3>
                                <p className="text-sm text-gray-500 mt-1">
                                    by @{proposal.proposer.username} • {formatDate(proposal.submitted_at)}
                                </p>
                                {proposal.decision?.notes && (
                                    <p className="text-sm text-gray-600 mt-2 italic">
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
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
                    <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-y-auto">
                        <div className="p-6">
                            <div className="flex items-center justify-between mb-4">
                                <h2 className="text-xl font-bold">Review Proposal</h2>
                                <button
                                    onClick={() => {
                                        setSelectedProposal(null)
                                        setDecisionNotes('')
                                    }}
                                    className="text-gray-400 hover:text-gray-600"
                                >
                                    ✕
                                </button>
                            </div>

                            <div className="mb-4">
                                <h3 className="font-medium mb-2">{selectedProposal.summary}</h3>
                                <p className="text-sm text-gray-500">
                                    Submitted by @{selectedProposal.proposer.username} on {formatDate(selectedProposal.submitted_at)}
                                </p>
                            </div>

                            <div className="mb-4">
                                <h4 className="font-medium mb-2">Changes</h4>
                                <div className="border rounded-lg p-4 bg-gray-50 max-h-64 overflow-y-auto">
                                    <ProposalDiffViewer diffPayload={selectedProposal.diff_payload as unknown as DiffPayload} />
                                </div>
                            </div>

                            <div className="mb-4">
                                <label className="block text-sm font-medium mb-2">
                                    Decision Notes (optional)
                                </label>
                                <textarea
                                    value={decisionNotes}
                                    onChange={e => setDecisionNotes(e.target.value)}
                                    className="w-full p-2 border rounded focus:ring-2 focus:ring-blue-500"
                                    rows={3}
                                    placeholder="Add feedback for the proposer..."
                                    maxLength={512}
                                />
                                <p className="text-xs text-gray-400 mt-1">
                                    {decisionNotes.length}/512 characters
                                </p>
                            </div>

                            <div className="flex gap-3">
                                <button
                                    onClick={() => handleDecision(selectedProposal.id, 'approve')}
                                    disabled={submitting}
                                    className="flex-1 py-2 bg-green-500 text-white rounded hover:bg-green-600 disabled:opacity-50"
                                >
                                    ✓ Approve
                                </button>
                                <button
                                    onClick={() => handleDecision(selectedProposal.id, 'needs_changes')}
                                    disabled={submitting}
                                    className="flex-1 py-2 bg-yellow-500 text-white rounded hover:bg-yellow-600 disabled:opacity-50"
                                >
                                    ↻ Needs Changes
                                </button>
                                <button
                                    onClick={() => handleDecision(selectedProposal.id, 'reject')}
                                    disabled={submitting}
                                    className="flex-1 py-2 bg-red-500 text-white rounded hover:bg-red-600 disabled:opacity-50"
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
