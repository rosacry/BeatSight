/**
 * Leaderboard Page - Unified karma leaderboard with sortable columns
 * 
 * Shows a single karma leaderboard as a table with sortable columns:
 * - Total karma
 * - Map upvotes
 * - Contributions
 * - Verification
 * - Bonuses
 */

import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/authStore'
import { API_CONFIG } from '@/lib/config'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { UsernameLink } from '@/components/social'
import {
    StaggerPageContent,
    StaggerSection,
    PageContentWrapper
} from '@/components/ui/UnifiedTransitions'

// Types
interface KarmaSourceBreakdown {
    map_upvotes: number
    map_downvotes: number
    contributions_approved: number
    contributions_rejected: number
    verification_votes: number
    verification_consensus: number
    forum_activity: number
    verification_bonuses: number
    subscription_bonuses: number
    admin_adjustments: number
    other: number
}

interface LeaderboardEntry {
    rank: number
    user_id: string
    user_number: number
    display_name: string
    avatar_url: string | null
    karma_score: number
    is_anonymous: boolean
    breakdown: KarmaSourceBreakdown
}

// Sort configuration
type SortKey = 'karma_score' | 'maps' | 'contributions' | 'verification' | 'bonuses' | 'forum'
type SortDirection = 'asc' | 'desc'

// Column definitions for the table
const COLUMNS: { key: SortKey; label: string; icon: string; tooltip: string }[] = [
    { key: 'karma_score', label: 'Total', icon: '🏆', tooltip: 'Total karma score' },
    { key: 'maps', label: 'Maps', icon: '👍', tooltip: 'Karma from map upvotes/downvotes' },
    { key: 'contributions', label: 'Contrib', icon: '📝', tooltip: 'Karma from contributions' },
    { key: 'verification', label: 'Verify', icon: '✓', tooltip: 'Karma from verification activity' },
    { key: 'bonuses', label: 'Bonus', icon: '🎁', tooltip: 'Verification & subscription bonuses' },
    { key: 'forum', label: 'Forum', icon: '💬', tooltip: 'Karma from forum activity' },
]

// Helper to get computed values for sorting
function getColumnValue(entry: LeaderboardEntry, key: SortKey): number {
    switch (key) {
        case 'karma_score':
            return entry.karma_score
        case 'maps':
            return entry.breakdown.map_upvotes + entry.breakdown.map_downvotes
        case 'contributions':
            return entry.breakdown.contributions_approved + entry.breakdown.contributions_rejected
        case 'verification':
            return entry.breakdown.verification_votes + entry.breakdown.verification_consensus
        case 'bonuses':
            return entry.breakdown.verification_bonuses + entry.breakdown.subscription_bonuses
        case 'forum':
            return entry.breakdown.forum_activity
        default:
            return 0
    }
}

// Helper to format karma with color
function KarmaCell({ value, highlight = false }: { value: number; highlight?: boolean }) {
    if (value === 0) return <span className="text-gray-600">—</span>
    const colorClass = value > 0 ? 'text-green-400' : 'text-red-400'
    return (
        <span className={`${colorClass} ${highlight ? 'font-bold' : ''}`}>
            {value > 0 ? '+' : ''}{value.toLocaleString()}
        </span>
    )
}

// Sort indicator arrow
function SortArrow({ direction, active }: { direction: SortDirection; active: boolean }) {
    return (
        <span className={`ml-1 transition-opacity ${active ? 'opacity-100' : 'opacity-0 group-hover:opacity-50'}`}>
            {direction === 'desc' ? '↓' : '↑'}
        </span>
    )
}

export function LeaderboardPage() {
    useDocumentTitle('leaderboard')
    const user = useAuthStore((state) => state.user)
    const [sortKey, setSortKey] = useState<SortKey>('karma_score')
    const [sortDirection, setSortDirection] = useState<SortDirection>('desc')

    // Fetch unified leaderboard with breakdown
    const { data: leaderboard, isLoading } = useQuery({
        queryKey: ['leaderboard', 'unified'],
        queryFn: async () => {
            const response = await fetch(`${API_CONFIG.baseUrl}/api/karma/leaderboard/unified?limit=50`)
            if (!response.ok) throw new Error('Failed to fetch leaderboard')
            const data = await response.json()
            return data.entries as LeaderboardEntry[]
        },
    })

    // Sort the leaderboard based on current sort settings
    const sortedLeaderboard = useMemo(() => {
        if (!leaderboard) return []

        return [...leaderboard].sort((a, b) => {
            const aVal = getColumnValue(a, sortKey)
            const bVal = getColumnValue(b, sortKey)
            const diff = bVal - aVal // Default descending
            return sortDirection === 'desc' ? diff : -diff
        })
    }, [leaderboard, sortKey, sortDirection])

    // Handle column header click for sorting
    const handleSort = (key: SortKey) => {
        if (sortKey === key) {
            // Toggle direction if same column
            setSortDirection(sortDirection === 'desc' ? 'asc' : 'desc')
        } else {
            // New column, default to descending
            setSortKey(key)
            setSortDirection('desc')
        }
    }

    return (
        <PageContentWrapper className="max-w-6xl mx-auto px-4 py-8">
            {/* Header */}
            <div className="text-center mb-8">
                <h1 className="text-2xl sm:text-3xl font-bold text-white mb-2">🏆 Karma Leaderboard</h1>
                <p className="text-gray-400 text-sm sm:text-base">
                    Top contributors ranked by karma earned
                </p>
                <p className="text-xs text-gray-500 mt-2">
                    Click column headers to sort
                </p>
            </div>

            {/* Leaderboard Table */}
            <div className="bg-dark-400 rounded-xl border border-dark-300 overflow-hidden">
                {isLoading ? (
                    <div className="p-8 text-center">
                        <div className="animate-spin h-8 w-8 border-4 border-primary-500 border-t-transparent rounded-full mx-auto"></div>
                        <p className="text-gray-400 mt-4">Loading leaderboard...</p>
                    </div>
                ) : sortedLeaderboard.length > 0 ? (
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            {/* Table Header */}
                            <thead className="bg-dark-500 border-b border-dark-300">
                                <tr>
                                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider w-12">
                                        #
                                    </th>
                                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider min-w-[150px]">
                                        User
                                    </th>
                                    {COLUMNS.map((col) => (
                                        <th
                                            key={col.key}
                                            onClick={() => handleSort(col.key)}
                                            className="px-2 py-3 text-right text-xs font-medium text-gray-400 uppercase tracking-wider cursor-pointer hover:bg-dark-400 transition-colors group select-none"
                                            title={col.tooltip}
                                        >
                                            <div className="flex items-center justify-end gap-1">
                                                <span className="hidden sm:inline">{col.icon}</span>
                                                <span className={sortKey === col.key ? 'text-primary-400' : ''}>
                                                    {col.label}
                                                </span>
                                                <SortArrow direction={sortDirection} active={sortKey === col.key} />
                                            </div>
                                        </th>
                                    ))}
                                </tr>
                            </thead>

                            {/* Table Body */}
                            <tbody className="divide-y divide-dark-300">
                                <StaggerPageContent>
                                    {sortedLeaderboard.map((entry, index) => {
                                        // Calculate display rank based on sort
                                        const displayRank = sortKey === 'karma_score' ? entry.rank : index + 1
                                        const isCurrentUser = entry.user_id === user?.id

                                        return (
                                            <StaggerSection key={entry.user_id}>
                                                <tr className={`hover:bg-dark-300/50 transition-colors ${isCurrentUser ? 'bg-primary-500/10' : ''
                                                    }`}>
                                                    {/* Rank */}
                                                    <td className="px-3 py-3 whitespace-nowrap">
                                                        <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${displayRank === 1 ? 'bg-yellow-500 text-black' :
                                                                displayRank === 2 ? 'bg-gray-300 text-black' :
                                                                    displayRank === 3 ? 'bg-amber-600 text-white' :
                                                                        'bg-dark-500 text-gray-400'
                                                            }`}>
                                                            {displayRank}
                                                        </div>
                                                    </td>

                                                    {/* User */}
                                                    <td className="px-3 py-3 whitespace-nowrap">
                                                        <div className="flex items-center gap-2">
                                                            {entry.is_anonymous ? (
                                                                <div className="w-8 h-8 rounded-full bg-accent-500 flex items-center justify-center text-white flex-shrink-0">
                                                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                                                                    </svg>
                                                                </div>
                                                            ) : entry.avatar_url ? (
                                                                <img
                                                                    src={entry.avatar_url}
                                                                    alt={entry.display_name}
                                                                    className="w-8 h-8 rounded-full flex-shrink-0"
                                                                />
                                                            ) : (
                                                                <div className="w-8 h-8 rounded-full bg-primary-500 flex items-center justify-center text-white text-sm font-medium flex-shrink-0">
                                                                    {entry.display_name?.[0]?.toUpperCase() || '?'}
                                                                </div>
                                                            )}
                                                            <div className="min-w-0">
                                                                {entry.is_anonymous ? (
                                                                    <p className="font-medium text-accent-300 truncate text-sm">
                                                                        {entry.display_name}
                                                                    </p>
                                                                ) : (
                                                                    <UsernameLink
                                                                        user={{
                                                                            id: entry.user_id,
                                                                            user_number: entry.user_number,
                                                                            username: entry.display_name,
                                                                            display_name: entry.display_name,
                                                                        }}
                                                                        className="text-sm"
                                                                    />
                                                                )}
                                                            </div>
                                                        </div>
                                                    </td>

                                                    {/* Total Karma */}
                                                    <td className="px-2 py-3 text-right whitespace-nowrap">
                                                        <span className={`font-bold ${sortKey === 'karma_score' ? 'text-primary-400' : 'text-white'}`}>
                                                            {entry.karma_score.toLocaleString()}
                                                        </span>
                                                    </td>

                                                    {/* Maps */}
                                                    <td className="px-2 py-3 text-right whitespace-nowrap">
                                                        <KarmaCell
                                                            value={entry.breakdown.map_upvotes + entry.breakdown.map_downvotes}
                                                            highlight={sortKey === 'maps'}
                                                        />
                                                    </td>

                                                    {/* Contributions */}
                                                    <td className="px-2 py-3 text-right whitespace-nowrap">
                                                        <KarmaCell
                                                            value={entry.breakdown.contributions_approved + entry.breakdown.contributions_rejected}
                                                            highlight={sortKey === 'contributions'}
                                                        />
                                                    </td>

                                                    {/* Verification */}
                                                    <td className="px-2 py-3 text-right whitespace-nowrap">
                                                        <KarmaCell
                                                            value={entry.breakdown.verification_votes + entry.breakdown.verification_consensus}
                                                            highlight={sortKey === 'verification'}
                                                        />
                                                    </td>

                                                    {/* Bonuses */}
                                                    <td className="px-2 py-3 text-right whitespace-nowrap">
                                                        <KarmaCell
                                                            value={entry.breakdown.verification_bonuses + entry.breakdown.subscription_bonuses}
                                                            highlight={sortKey === 'bonuses'}
                                                        />
                                                    </td>

                                                    {/* Forum */}
                                                    <td className="px-2 py-3 text-right whitespace-nowrap">
                                                        <KarmaCell
                                                            value={entry.breakdown.forum_activity}
                                                            highlight={sortKey === 'forum'}
                                                        />
                                                    </td>
                                                </tr>
                                            </StaggerSection>
                                        )
                                    })}
                                </StaggerPageContent>
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <div className="p-8 text-center text-gray-400">
                        No karma data available yet. Be the first to earn karma!
                    </div>
                )}
            </div>

            {/* Legend / How to Earn Section */}
            <div className="mt-8 p-6 rounded-xl bg-dark-400 border border-dark-300">
                <h3 className="text-lg font-semibold text-white mb-4">📊 Column Legend</h3>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 text-sm">
                    <div>
                        <div className="font-medium text-primary-400 mb-1">🏆 Total</div>
                        <p className="text-xs text-gray-500">Sum of all karma sources</p>
                    </div>
                    <div>
                        <div className="font-medium text-green-400 mb-1">👍 Maps</div>
                        <p className="text-xs text-gray-500">+5 upvote, -3 downvote</p>
                    </div>
                    <div>
                        <div className="font-medium text-blue-400 mb-1">📝 Contrib</div>
                        <p className="text-xs text-gray-500">+15 approved, -5 rejected</p>
                    </div>
                    <div>
                        <div className="font-medium text-accent-400 mb-1">✓ Verify</div>
                        <p className="text-xs text-gray-500">+5 vote, +10 consensus match</p>
                    </div>
                    <div>
                        <div className="font-medium text-yellow-400 mb-1">🎁 Bonus</div>
                        <p className="text-xs text-gray-500">Email/phone verification</p>
                    </div>
                    <div>
                        <div className="font-medium text-purple-400 mb-1">💬 Forum</div>
                        <p className="text-xs text-gray-500">+3-15 posts, -25 spam</p>
                    </div>
                </div>
            </div>

            {/* Role Tiers Section */}
            <div className="mt-6 p-6 rounded-xl bg-dark-400 border border-dark-300">
                <h3 className="text-lg font-semibold text-white mb-4">🎖️ Role Progression</h3>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                    <div className="p-3 rounded-lg bg-dark-500 border border-dark-300">
                        <div className="text-sm font-medium text-gray-300">Fixer</div>
                        <div className="text-xs text-gray-500">100+ karma</div>
                        <div className="text-xs text-gray-400 mt-1">Submit corrections</div>
                    </div>
                    <div className="p-3 rounded-lg bg-accent-500/10 border border-accent-500/30">
                        <div className="text-sm font-medium text-accent-400">Verifier</div>
                        <div className="text-xs text-gray-500">500+ karma + phone</div>
                        <div className="text-xs text-gray-400 mt-1">Review contributions</div>
                    </div>
                    <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30">
                        <div className="text-sm font-medium text-amber-400">Curator</div>
                        <div className="text-xs text-gray-500">2000+ karma + phone</div>
                        <div className="text-xs text-gray-400 mt-1">Manage content</div>
                    </div>
                    <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30">
                        <div className="text-sm font-medium text-red-400">Admin</div>
                        <div className="text-xs text-gray-500">By invitation</div>
                        <div className="text-xs text-gray-400 mt-1">Full access</div>
                    </div>
                </div>
            </div>
        </PageContentWrapper>
    )
}
