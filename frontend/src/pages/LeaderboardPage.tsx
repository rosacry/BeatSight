/**
 * Leaderboard Page - Community rankings for karma and verifiers
 * 
 * Shows:
 * - Top karma earners
 * - Top verifiers
 * - Top contributors
 * - Achievement holders
 */

import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { API_CONFIG } from '@/lib/config'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import {
    AnimatedTabContent,
    AnimatedTabButton,
    StaggerPageContent,
    StaggerSection,
    PageContentWrapper
} from '@/components/ui/UnifiedTransitions'

// Types
interface LeaderboardUser {
    id: string
    display_name: string
    avatar_url: string | null
    karma_score: number
    rank: number
    is_anonymous?: boolean
}

interface VerifierStats {
    verifier_id: string
    username: string
    avatar_url: string | null
    total_reviews: number
    approved: number
    rejected: number
    accuracy: number
    rank: number
}

interface ContributorStats {
    user_id: string
    username: string
    avatar_url: string | null
    contribution_count: number
    approved_count: number
    rank: number
}

type LeaderboardTab = 'karma' | 'verifiers' | 'contributors'

const VALID_TABS: LeaderboardTab[] = ['karma', 'verifiers', 'contributors']

export function LeaderboardPage() {
    useDocumentTitle('leaderboard')
    const [searchParams, setSearchParams] = useSearchParams()

    // Get tab from URL or default to 'karma'
    const tabFromUrl = searchParams.get('tab') as LeaderboardTab | null
    const initialTab: LeaderboardTab = tabFromUrl && VALID_TABS.includes(tabFromUrl) ? tabFromUrl : 'karma'
    const [activeTab, setActiveTab] = useState<LeaderboardTab>(initialTab)
    const { accessToken } = useAuthStore()
    const user = useAuthStore((state) => state.user)

    // Update URL when tab changes
    const handleTabChange = (tab: LeaderboardTab) => {
        setActiveTab(tab)
        setSearchParams({ tab }, { replace: true })
    }

    // Sync tab state with URL on mount and URL changes
    useEffect(() => {
        const tabFromUrl = searchParams.get('tab')
        if (tabFromUrl && VALID_TABS.includes(tabFromUrl as LeaderboardTab)) {
            setActiveTab(tabFromUrl as LeaderboardTab)
        }
    }, [searchParams])

    // Fetch karma leaderboard
    const { data: karmaLeaderboard, isLoading: karmaLoading } = useQuery({
        queryKey: ['leaderboard', 'karma'],
        queryFn: async () => {
            const response = await fetch(`${API_CONFIG.baseUrl}/api/karma/leaderboard?limit=50`)
            if (!response.ok) throw new Error('Failed to fetch karma leaderboard')
            const data = await response.json()
            // Transform the response to match our LeaderboardUser interface
            return data.entries.map((entry: { user_id: string; display_name: string; karma_score: number; rank: number; is_anonymous?: boolean }) => ({
                id: entry.user_id,
                display_name: entry.display_name,
                avatar_url: null, // API doesn't return avatar_url
                karma_score: entry.karma_score,
                rank: entry.rank,
                is_anonymous: entry.is_anonymous || false,
            })) as LeaderboardUser[]
        },
        enabled: activeTab === 'karma',
    })

    // Fetch verifier leaderboard (requires authentication)
    const { data: verifierLeaderboard, isLoading: verifierLoading } = useQuery({
        queryKey: ['leaderboard', 'verifiers'],
        queryFn: async () => {
            if (!accessToken) {
                // Return empty array for unauthenticated users
                return [] as VerifierStats[]
            }
            const response = await fetch(`${API_CONFIG.baseUrl}/api/verifier/leaderboard`, {
                headers: { Authorization: `Bearer ${accessToken}` },
            })
            if (!response.ok) {
                if (response.status === 401) {
                    return [] as VerifierStats[]
                }
                throw new Error('Failed to fetch verifier leaderboard')
            }
            const data = await response.json()
            return data.verifiers as VerifierStats[]
        },
        enabled: activeTab === 'verifiers',
    })

    // Fetch contributor leaderboard
    const { data: contributorLeaderboard, isLoading: contributorLoading } = useQuery({
        queryKey: ['leaderboard', 'contributors'],
        queryFn: async () => {
            const response = await fetch(`${API_CONFIG.baseUrl}/api/contributions/leaderboard?limit=50`, {
                headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
            })
            if (!response.ok) throw new Error('Failed to fetch contributor leaderboard')
            const data = await response.json()
            return data.contributors.map((entry: { user_id: string; username: string; avatar_url: string | null; contribution_count: number; approved_count: number; rank: number }) => ({
                user_id: entry.user_id,
                username: entry.username,
                avatar_url: entry.avatar_url,
                contribution_count: entry.contribution_count,
                approved_count: entry.approved_count,
                rank: entry.rank,
            })) as ContributorStats[]
        },
        enabled: activeTab === 'contributors',
    })

    const isLoading = (activeTab === 'karma' && karmaLoading) ||
        (activeTab === 'verifiers' && verifierLoading) ||
        (activeTab === 'contributors' && contributorLoading)

    return (
        <PageContentWrapper className="max-w-4xl mx-auto px-4 py-8">
            {/* Header */}
            <div className="text-center mb-8">
                <h1 className="text-2xl sm:text-3xl font-bold text-white mb-2">Leaderboards</h1>
                <p className="text-gray-400 text-sm sm:text-base">Top contributors in the BeatSight community</p>
            </div>

            {/* Tab Navigation */}
            <div className="flex justify-center mb-8 overflow-x-auto pb-2 -mx-4 px-4 sm:mx-0 sm:px-0">
                <div className="inline-flex gap-1 p-1 bg-dark-400 rounded-xl flex-nowrap">
                    <AnimatedTabButton
                        isActive={activeTab === 'karma'}
                        onClick={() => handleTabChange('karma')}
                        label="🏆 Karma"
                        variant="pills"
                    />
                    <AnimatedTabButton
                        isActive={activeTab === 'verifiers'}
                        onClick={() => handleTabChange('verifiers')}
                        label="✓ Verifiers"
                        variant="pills"
                    />
                    <AnimatedTabButton
                        isActive={activeTab === 'contributors'}
                        onClick={() => handleTabChange('contributors')}
                        label="📝 Contributors"
                        variant="pills"
                    />
                </div>
            </div>

            {/* Leaderboard Content */}
            <div className="bg-dark-400 rounded-xl border border-dark-300 overflow-hidden">
                {isLoading ? (
                    <div className="p-8 text-center">
                        <div className="animate-spin h-8 w-8 border-4 border-primary-500 border-t-transparent rounded-full mx-auto"></div>
                        <p className="text-gray-400 mt-4">Loading leaderboard...</p>
                    </div>
                ) : (
                    <AnimatedTabContent activeTab={activeTab}>
                        <StaggerPageContent>
                            {/* Karma Leaderboard */}
                            {activeTab === 'karma' && karmaLeaderboard && (
                                <div className="divide-y divide-dark-300">
                                    {karmaLeaderboard.map((entry, index) => (
                                        <StaggerSection key={entry.id}>
                                            <div
                                                className={`flex items-center gap-4 p-4 hover:bg-dark-300 transition-colors ${entry.id === user?.id ? 'bg-primary-500/10 border-l-4 border-primary-500' : ''
                                                    }`}
                                            >
                                                {/* Rank */}
                                                <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold ${index === 0 ? 'bg-yellow-500 text-black' :
                                                    index === 1 ? 'bg-gray-300 text-black' :
                                                        index === 2 ? 'bg-amber-600 text-white' :
                                                            'bg-dark-500 text-gray-400'
                                                    }`}>
                                                    {index + 1}
                                                </div>

                                                {/* Avatar & Name */}
                                                <div className="flex items-center gap-3 flex-1 min-w-0">
                                                    {entry.is_anonymous ? (
                                                        <div className="w-10 h-10 rounded-full bg-accent-500 flex items-center justify-center text-white">
                                                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 14l-2-2m0 0l-2-2m2 2l2-2m-2 2l2 2" />
                                                            </svg>
                                                        </div>
                                                    ) : entry.avatar_url ? (
                                                        <img
                                                            src={entry.avatar_url}
                                                            alt={entry.display_name}
                                                            className="w-10 h-10 rounded-full"
                                                        />
                                                    ) : (
                                                        <div className="w-10 h-10 rounded-full bg-primary-500 flex items-center justify-center text-white font-medium">
                                                            {entry.display_name?.[0]?.toUpperCase() || '?'}
                                                        </div>
                                                    )}
                                                    <div className="min-w-0">
                                                        <p className={`font-medium truncate ${entry.is_anonymous ? 'text-accent-300 italic' : 'text-white'}`}>
                                                            {entry.display_name}
                                                            {entry.is_anonymous && (
                                                                <span className="ml-2 text-xs text-accent-400">🕵️</span>
                                                            )}
                                                        </p>
                                                        {entry.id === user?.id && (
                                                            <p className="text-xs text-primary-400">This is you!</p>
                                                        )}
                                                    </div>
                                                </div>

                                                {/* Score */}
                                                <div className="text-right">
                                                    <p className="text-lg font-bold text-primary-400">{entry.karma_score.toLocaleString()}</p>
                                                    <p className="text-xs text-gray-400">karma</p>
                                                </div>
                                            </div>
                                        </StaggerSection>
                                    ))}

                                    {karmaLeaderboard.length === 0 && (
                                        <StaggerSection>
                                            <div className="p-8 text-center text-gray-400">
                                                No karma data available yet.
                                            </div>
                                        </StaggerSection>
                                    )}
                                </div>
                            )}

                            {/* Verifier Leaderboard */}
                            {activeTab === 'verifiers' && verifierLeaderboard && (
                                <div className="divide-y divide-gray-700/50">
                                    {verifierLeaderboard.map((entry, index) => (
                                        <StaggerSection key={entry.verifier_id}>
                                            <div
                                                className="flex items-center gap-4 p-4 hover:bg-dark-300 transition-colors"
                                            >
                                                {/* Rank */}
                                                <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold ${index === 0 ? 'bg-yellow-500 text-black' :
                                                    index === 1 ? 'bg-gray-300 text-black' :
                                                        index === 2 ? 'bg-amber-600 text-white' :
                                                            'bg-dark-500 text-gray-400'
                                                    }`}>
                                                    {index + 1}
                                                </div>

                                                {/* Avatar & Name */}
                                                <div className="flex items-center gap-3 flex-1 min-w-0">
                                                    {entry.avatar_url ? (
                                                        <img
                                                            src={entry.avatar_url}
                                                            alt={entry.username}
                                                            className="w-10 h-10 rounded-full"
                                                        />
                                                    ) : (
                                                        <div className="w-10 h-10 rounded-full bg-accent-500 flex items-center justify-center text-white font-medium">
                                                            {entry.username?.[0]?.toUpperCase() || '?'}
                                                        </div>
                                                    )}
                                                    <div className="min-w-0">
                                                        <p className="font-medium text-white truncate">{entry.username}</p>
                                                        <div className="flex gap-3 text-xs text-gray-400">
                                                            <span className="text-green-400">{entry.approved} ✓</span>
                                                            <span className="text-red-400">{entry.rejected} ✗</span>
                                                        </div>
                                                    </div>
                                                </div>

                                                {/* Stats */}
                                                <div className="text-right">
                                                    <p className="text-lg font-bold text-accent-400">{entry.total_reviews}</p>
                                                    <p className="text-xs text-gray-400">reviews</p>
                                                </div>
                                            </div>
                                        </StaggerSection>
                                    ))}

                                    {verifierLeaderboard.length === 0 && (
                                        <StaggerSection>
                                            <div className="p-8 text-center text-gray-400">
                                                {!accessToken ? (
                                                    <>
                                                        <p>Sign in to view the verifier leaderboard.</p>
                                                        <Link to="/login" className="text-primary-400 hover:text-primary-300 mt-2 inline-block">
                                                            Sign in →
                                                        </Link>
                                                    </>
                                                ) : (
                                                    <>
                                                        <p>No verifier data available yet.</p>
                                                        <Link to="/verifier" className="text-primary-400 hover:text-primary-300 mt-2 inline-block">
                                                            Become a verifier →
                                                        </Link>
                                                    </>
                                                )}
                                            </div>
                                        </StaggerSection>
                                    )}
                                </div>
                            )}

                            {/* Contributor Leaderboard */}
                            {activeTab === 'contributors' && contributorLeaderboard && (
                                <div className="divide-y divide-dark-300">
                                    {contributorLeaderboard.map((entry, index) => (
                                        <StaggerSection key={entry.user_id}>
                                            <div
                                                className="flex items-center gap-4 p-4 hover:bg-dark-300 transition-colors"
                                            >
                                                {/* Rank */}
                                                <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold ${index === 0 ? 'bg-yellow-500 text-black' :
                                                    index === 1 ? 'bg-gray-300 text-black' :
                                                        index === 2 ? 'bg-amber-600 text-white' :
                                                            'bg-dark-500 text-gray-400'
                                                    }`}>
                                                    {index + 1}
                                                </div>

                                                {/* Avatar & Name */}
                                                <div className="flex items-center gap-3 flex-1 min-w-0">
                                                    {entry.avatar_url ? (
                                                        <img
                                                            src={entry.avatar_url}
                                                            alt={entry.username}
                                                            className="w-10 h-10 rounded-full"
                                                        />
                                                    ) : (
                                                        <div className="w-10 h-10 rounded-full bg-green-500 flex items-center justify-center text-white font-medium">
                                                            {entry.username?.[0]?.toUpperCase() || '?'}
                                                        </div>
                                                    )}
                                                    <div className="min-w-0">
                                                        <p className="font-medium text-white truncate">{entry.username}</p>
                                                        <p className="text-xs text-gray-400">
                                                            {entry.approved_count} approved
                                                        </p>
                                                    </div>
                                                </div>

                                                {/* Stats */}
                                                <div className="text-right">
                                                    <p className="text-lg font-bold text-green-400">{entry.contribution_count}</p>
                                                    <p className="text-xs text-gray-400">contributions</p>
                                                </div>
                                            </div>
                                        </StaggerSection>
                                    ))}

                                    {contributorLeaderboard.length === 0 && (
                                        <StaggerSection>
                                            <div className="p-8 text-center text-gray-400">
                                                <p>No contribution data available yet.</p>
                                                <Link to="/upload" className="text-primary-400 hover:text-primary-300 mt-2 inline-block">
                                                    Start contributing →
                                                </Link>
                                            </div>
                                        </StaggerSection>
                                    )}
                                </div>
                            )}
                        </StaggerPageContent>
                    </AnimatedTabContent>
                )}
            </div>

            {/* Incentives Section */}
            <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <div className="p-5 rounded-xl bg-dark-400 border border-primary-500/20">
                    <h3 className="font-semibold text-primary-400 mb-2">🏆 Earn Karma</h3>
                    <p className="text-sm text-gray-400 mb-3">
                        Create beatmaps, help verify contributions, and participate in the community.
                    </p>
                    <ul className="text-xs text-gray-500 space-y-1">
                        <li>• +10 karma per approved beatmap</li>
                        <li>• +5 karma per helpful review</li>
                        <li>• +2 karma per verified contribution</li>
                    </ul>
                </div>
                <div className="p-5 rounded-xl bg-dark-400 border border-accent-500/20">
                    <h3 className="font-semibold text-accent-400 mb-2">✓ Become a Verifier</h3>
                    <p className="text-sm text-gray-400 mb-3">
                        Help maintain quality by reviewing community beatmap contributions.
                    </p>
                    <ul className="text-xs text-gray-500 space-y-1">
                        <li>• Requires 100+ karma</li>
                        <li>• Phone verification needed</li>
                        <li>• Exclusive verifier badge</li>
                    </ul>
                </div>
                <div className="p-5 rounded-xl bg-dark-400 border border-green-500/20">
                    <h3 className="font-semibold text-green-400 mb-2">📝 Contribute</h3>
                    <p className="text-sm text-gray-400 mb-3">
                        Improve AI training by submitting beatmap corrections and annotations.
                    </p>
                    <ul className="text-xs text-gray-500 space-y-1">
                        <li>• Credit in published beatmaps</li>
                        <li>• Contribution badges</li>
                        <li>• Early access to new features</li>
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
                        <div className="text-xs text-gray-500">50+ karma</div>
                        <div className="text-xs text-gray-400 mt-1">Submit beatmap corrections</div>
                    </div>
                    <div className="p-3 rounded-lg bg-accent-500/10 border border-accent-500/30">
                        <div className="text-sm font-medium text-accent-400">Verifier</div>
                        <div className="text-xs text-gray-500">100+ karma + phone</div>
                        <div className="text-xs text-gray-400 mt-1">Review & approve contributions</div>
                    </div>
                    <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30">
                        <div className="text-sm font-medium text-amber-400">Curator</div>
                        <div className="text-xs text-gray-500">500+ karma + phone</div>
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
