/**
 * Leaderboard Page - Unified karma leaderboard with sortable columns
 * 
 * Shows a single karma leaderboard ranked by total karma with:
 * - Karma rank badges (Bronze → Grandmaster)
 * - Sortable breakdown columns
 * - Clean, professional design
 */

import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/authStore'
import { API_CONFIG } from '@/lib/config'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { UsernameLink } from '@/components/social'
import { PageContentWrapper } from '@/components/ui/UnifiedTransitions'

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

// Karma Rank System - Like ELO tiers
interface KarmaRank {
    name: string
    minKarma: number
    color: string
    bgColor: string
    borderColor: string
    icon: string
}

const KARMA_RANKS: KarmaRank[] = [
    { name: 'Grandmaster', minKarma: 10000, color: 'text-red-400', bgColor: 'bg-red-500/20', borderColor: 'border-red-500/50', icon: '👑' },
    { name: 'Master', minKarma: 5000, color: 'text-purple-400', bgColor: 'bg-purple-500/20', borderColor: 'border-purple-500/50', icon: '💎' },
    { name: 'Diamond', minKarma: 2500, color: 'text-cyan-400', bgColor: 'bg-cyan-500/20', borderColor: 'border-cyan-500/50', icon: '💠' },
    { name: 'Platinum', minKarma: 1000, color: 'text-teal-300', bgColor: 'bg-teal-500/20', borderColor: 'border-teal-500/50', icon: '✦' },
    { name: 'Gold', minKarma: 500, color: 'text-yellow-400', bgColor: 'bg-yellow-500/20', borderColor: 'border-yellow-500/50', icon: '⭐' },
    { name: 'Silver', minKarma: 200, color: 'text-gray-300', bgColor: 'bg-gray-400/20', borderColor: 'border-gray-400/50', icon: '◆' },
    { name: 'Bronze', minKarma: 50, color: 'text-amber-600', bgColor: 'bg-amber-600/20', borderColor: 'border-amber-600/50', icon: '●' },
    { name: 'Unranked', minKarma: 0, color: 'text-gray-500', bgColor: 'bg-dark-500', borderColor: 'border-dark-300', icon: '○' },
]

function getKarmaRank(karma: number): KarmaRank {
    return KARMA_RANKS.find(r => karma >= r.minKarma) || KARMA_RANKS[KARMA_RANKS.length - 1]
}

// Sort configuration
type SortKey = 'karma_score' | 'maps' | 'contributions' | 'verification' | 'votes'
type SortDirection = 'asc' | 'desc'

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
        case 'votes':
            // Forum activity represents votes on content (posts, comments, etc.)
            return entry.breakdown.forum_activity
        default:
            return 0
    }
}

// Karma Rank Badge Component
function KarmaRankBadge({ karma }: { karma: number }) {
    const rank = getKarmaRank(karma)
    return (
        <span className={`text-[10px] px-1.5 py-0.5 ${rank.bgColor} ${rank.color} ${rank.borderColor} border rounded font-medium inline-flex items-center gap-1 whitespace-nowrap`}>
            <span>{rank.icon}</span>
            <span>{rank.name}</span>
        </span>
    )
}

// Sortable Column Header
function SortableHeader({
    label,
    sortKey: key,
    currentKey,
    direction,
    onSort,
    className = ''
}: {
    label: string
    sortKey: SortKey
    currentKey: SortKey
    direction: SortDirection
    onSort: (key: SortKey) => void
    className?: string
}) {
    const isActive = currentKey === key
    return (
        <th
            onClick={() => onSort(key)}
            className={`px-3 py-3 text-xs font-semibold uppercase tracking-wider cursor-pointer select-none transition-colors hover:bg-dark-400 ${className}`}
        >
            <div className="flex items-center justify-end gap-1">
                <span className={isActive ? 'text-primary-400' : 'text-gray-400'}>
                    {label}
                </span>
                {isActive && (
                    <svg className="w-3 h-3 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                            d={direction === 'desc' ? 'M19 9l-7 7-7-7' : 'M5 15l7-7 7 7'} />
                    </svg>
                )}
            </div>
        </th>
    )
}

// Karma value cell with proper formatting
function KarmaValue({ value, highlight = false }: { value: number; highlight?: boolean }) {
    if (value === 0) {
        return <span className="text-gray-600 text-xs">—</span>
    }
    const isPositive = value > 0
    return (
        <span className={`text-sm tabular-nums ${highlight ? 'font-semibold' : ''} ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
            {isPositive && '+'}{value.toLocaleString()}
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
            const diff = bVal - aVal
            return sortDirection === 'desc' ? diff : -diff
        })
    }, [leaderboard, sortKey, sortDirection])

    // Handle column header click for sorting
    const handleSort = (key: SortKey) => {
        if (sortKey === key) {
            setSortDirection(sortDirection === 'desc' ? 'asc' : 'desc')
        } else {
            setSortKey(key)
            setSortDirection('desc')
        }
    }

    return (
        <PageContentWrapper className="max-w-5xl mx-auto px-4 py-8">
            {/* Header */}
            <div className="text-center mb-8">
                <h1 className="text-3xl font-bold text-white mb-2">Karma Leaderboard</h1>
                <p className="text-gray-400">
                    Top contributors to the drum transcription index
                </p>
            </div>

            {/* Leaderboard Table */}
            <div className="bg-dark-400 rounded-xl border border-dark-300 overflow-hidden shadow-lg">
                {isLoading ? (
                    <div className="p-12 text-center">
                        <div className="animate-spin h-8 w-8 border-4 border-primary-500 border-t-transparent rounded-full mx-auto"></div>
                        <p className="text-gray-400 mt-4">Loading leaderboard...</p>
                    </div>
                ) : sortedLeaderboard.length > 0 ? (
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead>
                                <tr className="bg-dark-500 border-b border-dark-300">
                                    <th className="w-16 px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">
                                        Rank
                                    </th>
                                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">
                                        User
                                    </th>
                                    <SortableHeader label="Total" sortKey="karma_score" currentKey={sortKey} direction={sortDirection} onSort={handleSort} className="text-right" />
                                    <SortableHeader label="Maps" sortKey="maps" currentKey={sortKey} direction={sortDirection} onSort={handleSort} className="text-right hidden sm:table-cell" />
                                    <SortableHeader label="Contrib" sortKey="contributions" currentKey={sortKey} direction={sortDirection} onSort={handleSort} className="text-right hidden md:table-cell" />
                                    <SortableHeader label="Verify" sortKey="verification" currentKey={sortKey} direction={sortDirection} onSort={handleSort} className="text-right hidden md:table-cell" />
                                    <SortableHeader label="Votes" sortKey="votes" currentKey={sortKey} direction={sortDirection} onSort={handleSort} className="text-right hidden lg:table-cell" />
                                </tr>
                            </thead>
                            <tbody>
                                {sortedLeaderboard.map((entry, index) => {
                                    const displayRank = sortKey === 'karma_score' ? entry.rank : index + 1
                                    const isCurrentUser = entry.user_id === user?.id
                                    const rank = getKarmaRank(entry.karma_score)

                                    return (
                                        <tr
                                            key={entry.user_id}
                                            className={`border-b border-dark-300/50 transition-colors ${isCurrentUser
                                                ? 'bg-primary-500/10 hover:bg-primary-500/15'
                                                : 'hover:bg-dark-300/30'
                                                }`}
                                        >
                                            {/* Rank */}
                                            <td className="px-4 py-3">
                                                <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold ${displayRank === 1 ? 'bg-gradient-to-br from-yellow-400 to-yellow-600 text-black shadow-lg shadow-yellow-500/30' :
                                                    displayRank === 2 ? 'bg-gradient-to-br from-gray-300 to-gray-400 text-black' :
                                                        displayRank === 3 ? 'bg-gradient-to-br from-amber-500 to-amber-700 text-white' :
                                                            'bg-dark-500 text-gray-400'
                                                    }`}>
                                                    {displayRank}
                                                </div>
                                            </td>

                                            {/* User Info */}
                                            <td className="px-4 py-3">
                                                <div className="flex items-center gap-3">
                                                    {/* Avatar */}
                                                    {entry.is_anonymous ? (
                                                        <div className="w-10 h-10 rounded-full bg-accent-500/30 flex items-center justify-center text-accent-400 flex-shrink-0">
                                                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                                                            </svg>
                                                        </div>
                                                    ) : entry.avatar_url ? (
                                                        <img
                                                            src={entry.avatar_url}
                                                            alt={entry.display_name}
                                                            className="w-10 h-10 rounded-full flex-shrink-0 ring-2 ring-dark-300"
                                                        />
                                                    ) : (
                                                        <div className={`w-10 h-10 rounded-full flex items-center justify-center text-white font-semibold flex-shrink-0 ${rank.bgColor} ${rank.borderColor} border`}>
                                                            {entry.display_name?.[0]?.toUpperCase() || '?'}
                                                        </div>
                                                    )}

                                                    {/* Name + Rank Badge */}
                                                    <div className="min-w-0">
                                                        {entry.is_anonymous ? (
                                                            <span className="font-medium text-accent-300 text-sm">
                                                                {entry.display_name}
                                                            </span>
                                                        ) : (
                                                            <UsernameLink
                                                                user={{
                                                                    id: entry.user_id,
                                                                    user_number: entry.user_number,
                                                                    username: entry.display_name,
                                                                    display_name: entry.display_name,
                                                                }}
                                                                className="font-medium text-sm"
                                                            />
                                                        )}
                                                        <div className="mt-1">
                                                            <KarmaRankBadge karma={entry.karma_score} />
                                                        </div>
                                                    </div>
                                                </div>
                                            </td>

                                            {/* Total Karma */}
                                            <td className="px-3 py-3 text-right">
                                                <span className={`text-lg font-bold tabular-nums ${sortKey === 'karma_score' ? 'text-primary-400' : 'text-white'}`}>
                                                    {entry.karma_score.toLocaleString()}
                                                </span>
                                            </td>

                                            {/* Maps */}
                                            <td className="px-3 py-3 text-right hidden sm:table-cell">
                                                <KarmaValue
                                                    value={entry.breakdown.map_upvotes + entry.breakdown.map_downvotes}
                                                    highlight={sortKey === 'maps'}
                                                />
                                            </td>

                                            {/* Contributions */}
                                            <td className="px-3 py-3 text-right hidden md:table-cell">
                                                <KarmaValue
                                                    value={entry.breakdown.contributions_approved + entry.breakdown.contributions_rejected}
                                                    highlight={sortKey === 'contributions'}
                                                />
                                            </td>

                                            {/* Verification */}
                                            <td className="px-3 py-3 text-right hidden md:table-cell">
                                                <KarmaValue
                                                    value={entry.breakdown.verification_votes + entry.breakdown.verification_consensus}
                                                    highlight={sortKey === 'verification'}
                                                />
                                            </td>

                                            {/* Votes (forum activity / upvotes on content) */}
                                            <td className="px-3 py-3 text-right hidden lg:table-cell">
                                                <KarmaValue
                                                    value={entry.breakdown.forum_activity}
                                                    highlight={sortKey === 'votes'}
                                                />
                                            </td>
                                        </tr>
                                    )
                                })}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <div className="p-12 text-center text-gray-400">
                        <div className="text-4xl mb-4">🥁</div>
                        <p>No karma data yet. Be the first to contribute!</p>
                    </div>
                )}
            </div>

            {/* Karma Ranks Section */}
            <div className="mt-10">
                <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                    <span>🏅</span>
                    Karma Ranks
                </h2>
                <p className="text-gray-400 text-sm mb-6">
                    Earn karma through contributions to climb the ranks. Your rank reflects your standing in the BeatSight community.
                </p>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {KARMA_RANKS.slice(0, -1).reverse().map((rank) => (
                        <div
                            key={rank.name}
                            className={`p-4 rounded-xl ${rank.bgColor} border ${rank.borderColor} transition-transform hover:scale-[1.02]`}
                        >
                            <div className="flex items-center gap-2 mb-2">
                                <span className="text-xl">{rank.icon}</span>
                                <span className={`font-bold ${rank.color}`}>{rank.name}</span>
                            </div>
                            <div className="text-xs text-gray-400">
                                {rank.minKarma.toLocaleString()}+ karma
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* How to Earn Section */}
            <div className="mt-10">
                <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                    <span>📈</span>
                    How to Earn Karma
                </h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    <div className="p-5 rounded-xl bg-dark-400 border border-dark-300">
                        <div className="flex items-center gap-2 mb-3">
                            <span className="text-2xl">👍</span>
                            <h3 className="font-semibold text-white">Map Ratings</h3>
                        </div>
                        <ul className="space-y-1.5 text-sm text-gray-400">
                            <li className="flex justify-between">
                                <span>Upvote received</span>
                                <span className="text-green-400 font-medium">+5</span>
                            </li>
                            <li className="flex justify-between">
                                <span>Downvote received</span>
                                <span className="text-red-400 font-medium">-3</span>
                            </li>
                        </ul>
                    </div>

                    <div className="p-5 rounded-xl bg-dark-400 border border-dark-300">
                        <div className="flex items-center gap-2 mb-3">
                            <span className="text-2xl">📝</span>
                            <h3 className="font-semibold text-white">Contributions</h3>
                        </div>
                        <ul className="space-y-1.5 text-sm text-gray-400">
                            <li className="flex justify-between">
                                <span>Contribution approved</span>
                                <span className="text-green-400 font-medium">+15</span>
                            </li>
                            <li className="flex justify-between">
                                <span>Contribution rejected</span>
                                <span className="text-red-400 font-medium">-5</span>
                            </li>
                        </ul>
                    </div>

                    <div className="p-5 rounded-xl bg-dark-400 border border-dark-300">
                        <div className="flex items-center gap-2 mb-3">
                            <span className="text-2xl">✓</span>
                            <h3 className="font-semibold text-white">Verification</h3>
                        </div>
                        <p className="text-xs text-gray-500 mb-2">Requires 200+ karma</p>
                        <ul className="space-y-1.5 text-sm text-gray-400">
                            <li className="flex justify-between">
                                <span>Verification vote</span>
                                <span className="text-green-400 font-medium">+5</span>
                            </li>
                            <li className="flex justify-between">
                                <span>Consensus match</span>
                                <span className="text-green-400 font-medium">+10</span>
                            </li>
                        </ul>
                    </div>

                    <div className="p-5 rounded-xl bg-dark-400 border border-dark-300">
                        <div className="flex items-center gap-2 mb-3">
                            <span className="text-2xl">🗳️</span>
                            <h3 className="font-semibold text-white">Votes</h3>
                        </div>
                        <ul className="space-y-1.5 text-sm text-gray-400">
                            <li className="flex justify-between">
                                <span>Helpful posts/comments</span>
                                <span className="text-green-400 font-medium">+3 to +15</span>
                            </li>
                            <li className="flex justify-between">
                                <span>Spam penalty</span>
                                <span className="text-red-400 font-medium">-25</span>
                            </li>
                        </ul>
                    </div>

                    <div className="p-5 rounded-xl bg-dark-400 border border-dark-300">
                        <div className="flex items-center gap-2 mb-3">
                            <span className="text-2xl">🎁</span>
                            <h3 className="font-semibold text-white">Account Bonuses</h3>
                        </div>
                        <ul className="space-y-1.5 text-sm text-gray-400">
                            <li className="flex justify-between">
                                <span>Email verified</span>
                                <span className="text-green-400 font-medium">+50</span>
                            </li>
                            <li className="flex justify-between">
                                <span>Phone verified</span>
                                <span className="text-green-400 font-medium">+50</span>
                            </li>
                            <li className="flex justify-between border-t border-dark-300 pt-1.5 mt-1.5">
                                <span className="text-gray-300">Both verified</span>
                                <span className="text-yellow-400 font-medium">+100 bonus</span>
                            </li>
                        </ul>
                        <p className="text-[10px] text-gray-500 mt-2">Total: 200 karma for full verification</p>
                    </div>

                    <div className="p-5 rounded-xl bg-dark-400 border border-dark-300 flex flex-col justify-center">
                        <p className="text-sm text-gray-400 text-center">
                            <span className="text-2xl block mb-2">🥁</span>
                            Karma reflects your contributions to building the world's best drum transcription index.
                        </p>
                    </div>
                </div>
            </div>
        </PageContentWrapper>
    )
}
