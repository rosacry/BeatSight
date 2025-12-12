/**
 * Leaderboard Page - Unified karma leaderboard with source breakdown
 * 
 * Shows a single karma leaderboard ranked by total karma,
 * with expandable breakdown showing where each user's karma came from:
 * - Map upvotes
 * - Contributions approved
 * - Verification activity
 * - Forum activity
 * - Bonuses
 */

import { useState } from 'react'
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

// Helper to format karma numbers with + or - prefix
function formatKarma(value: number): string {
    if (value > 0) return `+${value.toLocaleString()}`
    if (value < 0) return value.toLocaleString()
    return '0'
}

// Helper to get color class based on karma value
function getKarmaColorClass(value: number): string {
    if (value > 0) return 'text-green-400'
    if (value < 0) return 'text-red-400'
    return 'text-gray-500'
}

// Expandable breakdown row component
function BreakdownRow({ label, value, icon }: { label: string; value: number; icon: string }) {
    if (value === 0) return null
    return (
        <div className="flex items-center justify-between py-1 px-2 rounded hover:bg-dark-500/50">
            <span className="text-xs text-gray-400 flex items-center gap-2">
                <span>{icon}</span>
                {label}
            </span>
            <span className={`text-xs font-medium ${getKarmaColorClass(value)}`}>
                {formatKarma(value)}
            </span>
        </div>
    )
}

export function LeaderboardPage() {
    useDocumentTitle('leaderboard')
    const [expandedUser, setExpandedUser] = useState<string | null>(null)
    const user = useAuthStore((state) => state.user)

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

    const toggleExpanded = (userId: string) => {
        setExpandedUser(expandedUser === userId ? null : userId)
    }

    return (
        <PageContentWrapper className="max-w-4xl mx-auto px-4 py-8">
            {/* Header */}
            <div className="text-center mb-8">
                <h1 className="text-2xl sm:text-3xl font-bold text-white mb-2">🏆 Karma Leaderboard</h1>
                <p className="text-gray-400 text-sm sm:text-base">
                    Top contributors ranked by total karma earned
                </p>
                <p className="text-xs text-gray-500 mt-2">
                    Click any user to see their karma breakdown
                </p>
            </div>

            {/* Leaderboard Content */}
            <div className="bg-dark-400 rounded-xl border border-dark-300 overflow-hidden">
                {isLoading ? (
                    <div className="p-8 text-center">
                        <div className="animate-spin h-8 w-8 border-4 border-primary-500 border-t-transparent rounded-full mx-auto"></div>
                        <p className="text-gray-400 mt-4">Loading leaderboard...</p>
                    </div>
                ) : leaderboard && leaderboard.length > 0 ? (
                    <StaggerPageContent>
                        <div className="divide-y divide-dark-300">
                            {leaderboard.map((entry, index) => (
                                <StaggerSection key={entry.user_id}>
                                    <div className="group">
                                        {/* Main Row - Clickable */}
                                        <div
                                            onClick={() => toggleExpanded(entry.user_id)}
                                            className={`flex items-center gap-4 p-4 cursor-pointer transition-colors ${entry.user_id === user?.id
                                                    ? 'bg-primary-500/10 border-l-4 border-primary-500'
                                                    : 'hover:bg-dark-300'
                                                }`}
                                        >
                                            {/* Rank */}
                                            <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold flex-shrink-0 ${index === 0 ? 'bg-yellow-500 text-black' :
                                                    index === 1 ? 'bg-gray-300 text-black' :
                                                        index === 2 ? 'bg-amber-600 text-white' :
                                                            'bg-dark-500 text-gray-400'
                                                }`}>
                                                {entry.rank}
                                            </div>

                                            {/* Avatar & Name */}
                                            <div className="flex items-center gap-3 flex-1 min-w-0">
                                                {entry.is_anonymous ? (
                                                    <div className="w-10 h-10 rounded-full bg-accent-500 flex items-center justify-center text-white flex-shrink-0">
                                                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                                                        </svg>
                                                    </div>
                                                ) : entry.avatar_url ? (
                                                    <img
                                                        src={entry.avatar_url}
                                                        alt={entry.display_name}
                                                        className="w-10 h-10 rounded-full flex-shrink-0"
                                                    />
                                                ) : (
                                                    <div className="w-10 h-10 rounded-full bg-primary-500 flex items-center justify-center text-white font-medium flex-shrink-0">
                                                        {entry.display_name?.[0]?.toUpperCase() || '?'}
                                                    </div>
                                                )}
                                                <div className="min-w-0">
                                                    {entry.is_anonymous ? (
                                                        <p className="font-medium text-accent-300 truncate">
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
                                                            className="font-medium truncate"
                                                            onClick={(e) => e.stopPropagation()}
                                                        />
                                                    )}
                                                    {/* Quick breakdown preview */}
                                                    <div className="flex gap-2 mt-0.5 flex-wrap">
                                                        {entry.breakdown.map_upvotes > 0 && (
                                                            <span className="text-[10px] text-gray-500">
                                                                👍 {entry.breakdown.map_upvotes}
                                                            </span>
                                                        )}
                                                        {entry.breakdown.contributions_approved > 0 && (
                                                            <span className="text-[10px] text-gray-500">
                                                                📝 {entry.breakdown.contributions_approved}
                                                            </span>
                                                        )}
                                                        {entry.breakdown.verification_consensus > 0 && (
                                                            <span className="text-[10px] text-gray-500">
                                                                ✓ {entry.breakdown.verification_consensus}
                                                            </span>
                                                        )}
                                                        {entry.breakdown.verification_bonuses > 0 && (
                                                            <span className="text-[10px] text-gray-500">
                                                                🎁 {entry.breakdown.verification_bonuses}
                                                            </span>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>

                                            {/* Total Score */}
                                            <div className="text-right flex-shrink-0">
                                                <p className="text-lg font-bold text-primary-400">
                                                    {entry.karma_score.toLocaleString()}
                                                </p>
                                                <p className="text-xs text-gray-400">karma</p>
                                            </div>

                                            {/* Expand indicator */}
                                            <div className="text-gray-500 flex-shrink-0 transition-transform duration-200"
                                                style={{ transform: expandedUser === entry.user_id ? 'rotate(180deg)' : 'rotate(0deg)' }}>
                                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                                </svg>
                                            </div>
                                        </div>

                                        {/* Expanded Breakdown */}
                                        {expandedUser === entry.user_id && (
                                            <div className="px-4 pb-4 pt-0 bg-dark-500/30 animate-in slide-in-from-top-2 duration-200">
                                                <div className="ml-14 pl-3 border-l-2 border-dark-300">
                                                    <p className="text-xs text-gray-500 mb-2 font-medium uppercase tracking-wide">
                                                        Karma Sources
                                                    </p>
                                                    <div className="space-y-0.5">
                                                        <BreakdownRow
                                                            label="Map Upvotes"
                                                            value={entry.breakdown.map_upvotes}
                                                            icon="👍"
                                                        />
                                                        <BreakdownRow
                                                            label="Map Downvotes"
                                                            value={entry.breakdown.map_downvotes}
                                                            icon="👎"
                                                        />
                                                        <BreakdownRow
                                                            label="Contributions Approved"
                                                            value={entry.breakdown.contributions_approved}
                                                            icon="📝"
                                                        />
                                                        <BreakdownRow
                                                            label="Contributions Rejected"
                                                            value={entry.breakdown.contributions_rejected}
                                                            icon="❌"
                                                        />
                                                        <BreakdownRow
                                                            label="Verification Votes"
                                                            value={entry.breakdown.verification_votes}
                                                            icon="🗳️"
                                                        />
                                                        <BreakdownRow
                                                            label="Consensus Matches"
                                                            value={entry.breakdown.verification_consensus}
                                                            icon="✓"
                                                        />
                                                        <BreakdownRow
                                                            label="Forum Activity"
                                                            value={entry.breakdown.forum_activity}
                                                            icon="💬"
                                                        />
                                                        <BreakdownRow
                                                            label="Verification Bonuses"
                                                            value={entry.breakdown.verification_bonuses}
                                                            icon="🎁"
                                                        />
                                                        <BreakdownRow
                                                            label="Subscription Bonuses"
                                                            value={entry.breakdown.subscription_bonuses}
                                                            icon="⭐"
                                                        />
                                                        <BreakdownRow
                                                            label="Admin Adjustments"
                                                            value={entry.breakdown.admin_adjustments}
                                                            icon="🔧"
                                                        />
                                                        <BreakdownRow
                                                            label="Other"
                                                            value={entry.breakdown.other}
                                                            icon="📦"
                                                        />
                                                    </div>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </StaggerSection>
                            ))}
                        </div>
                    </StaggerPageContent>
                ) : (
                    <div className="p-8 text-center text-gray-400">
                        No karma data available yet. Be the first to earn karma!
                    </div>
                )}
            </div>

            {/* How to Earn Karma Section */}
            <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <div className="p-5 rounded-xl bg-dark-400 border border-primary-500/20">
                    <h3 className="font-semibold text-primary-400 mb-2">👍 Map Upvotes</h3>
                    <p className="text-sm text-gray-400 mb-3">
                        Create and share quality beatmaps to earn karma from community upvotes.
                    </p>
                    <ul className="text-xs text-gray-500 space-y-1">
                        <li>• +5 karma per upvote received</li>
                        <li>• -3 karma per downvote received</li>
                        <li>• No karma for AI-generated maps (only upvotes)</li>
                    </ul>
                </div>
                <div className="p-5 rounded-xl bg-dark-400 border border-green-500/20">
                    <h3 className="font-semibold text-green-400 mb-2">📝 Contributions</h3>
                    <p className="text-sm text-gray-400 mb-3">
                        Polish beatmaps by fixing timing, adding notes, or correcting errors.
                    </p>
                    <ul className="text-xs text-gray-500 space-y-1">
                        <li>• +15 karma per approved contribution</li>
                        <li>• -5 karma if contribution rejected</li>
                        <li>• Higher weight for consistent accuracy</li>
                    </ul>
                </div>
                <div className="p-5 rounded-xl bg-dark-400 border border-accent-500/20">
                    <h3 className="font-semibold text-accent-400 mb-2">✓ Verification</h3>
                    <p className="text-sm text-gray-400 mb-3">
                        Help verify beatmap accuracy by voting on map quality.
                    </p>
                    <ul className="text-xs text-gray-500 space-y-1">
                        <li>• +5 karma per verification vote</li>
                        <li>• +10 karma if your vote matches consensus</li>
                        <li>• Requires verifier role (500+ karma)</li>
                    </ul>
                </div>
            </div>

            {/* Bonuses Section */}
            <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="p-5 rounded-xl bg-dark-400 border border-yellow-500/20">
                    <h3 className="font-semibold text-yellow-400 mb-2">🎁 Verification Bonuses</h3>
                    <p className="text-sm text-gray-400 mb-3">
                        Verify your account to unlock bonus karma.
                    </p>
                    <ul className="text-xs text-gray-500 space-y-1">
                        <li>• +50 karma for email verification</li>
                        <li>• +50 karma for phone verification</li>
                        <li>• +100 bonus for completing both</li>
                    </ul>
                </div>
                <div className="p-5 rounded-xl bg-dark-400 border border-blue-500/20">
                    <h3 className="font-semibold text-blue-400 mb-2">💬 Forum Activity</h3>
                    <p className="text-sm text-gray-400 mb-3">
                        Participate in community discussions.
                    </p>
                    <ul className="text-xs text-gray-500 space-y-1">
                        <li>• +3-5 karma for upvoted posts</li>
                        <li>• +15 karma for helpful answers</li>
                        <li>• -25 karma penalty for spam</li>
                    </ul>
                </div>
            </div>

            {/* Role Tiers Section */}
            <div className="mt-8 p-6 rounded-xl bg-dark-400 border border-dark-300">
                <h3 className="text-lg font-semibold text-white mb-4">🎖️ Role Progression</h3>
                <p className="text-sm text-gray-400 mb-4">
                    Earn karma to unlock new roles and abilities within the BeatSight community.
                </p>
                <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-2 sm:gap-3">
                    <div className="p-3 rounded-lg bg-dark-500 border border-dark-300">
                        <div className="text-sm font-medium text-gray-300">Fixer</div>
                        <div className="text-xs text-gray-500">100+ karma</div>
                        <div className="text-xs text-gray-400 mt-1">Submit beatmap corrections</div>
                    </div>
                    <div className="p-3 rounded-lg bg-accent-500/10 border border-accent-500/30">
                        <div className="text-sm font-medium text-accent-400">Verifier</div>
                        <div className="text-xs text-gray-500">500+ karma + phone</div>
                        <div className="text-xs text-gray-400 mt-1">Review & approve contributions</div>
                    </div>
                    <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30">
                        <div className="text-sm font-medium text-amber-400">Curator</div>
                        <div className="text-xs text-gray-500">2000+ karma + phone</div>
                        <div className="text-xs text-gray-400 mt-1">Manage featured content</div>
                    </div>
                    <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30">
                        <div className="text-sm font-medium text-red-400">Admin</div>
                        <div className="text-xs text-gray-500">By invitation</div>
                        <div className="text-xs text-gray-400 mt-1">Full platform access</div>
                    </div>
                </div>
            </div>
        </PageContentWrapper>
    )
}
