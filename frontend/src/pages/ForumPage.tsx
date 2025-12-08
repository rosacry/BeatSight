/**
 * Main forum page showing all categories and forums.
 */

import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getForumCategories, getRecentTopics } from '@/api/forum'
import { ForumCategoryList, TopicList } from '@/components/forum'
import { useAuthStore } from '@/stores/authStore'

export function ForumPage() {
    const user = useAuthStore((state) => state.user)

    const {
        data: categories,
        isLoading: categoriesLoading,
        error: categoriesError,
    } = useQuery({
        queryKey: ['forumCategories'],
        queryFn: getForumCategories,
    })

    const { data: recentTopics } = useQuery({
        queryKey: ['recentTopics'],
        queryFn: () => getRecentTopics({ pageSize: 5 }),
    })

    return (
        <div className="max-w-6xl mx-auto space-y-8">
            {/* Header with gradient */}
            <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-purple-600/20 via-fuchsia-600/10 to-cyan-600/20 border border-gray-700/50 p-8">
                <div className="relative z-10">
                    <div className="flex items-center justify-between">
                        <div>
                            <h1 className="text-4xl font-bold text-white mb-2">Community Forums</h1>
                            <p className="text-gray-300 text-lg">
                                Discuss beatmaps, strategies, and connect with other drummers
                            </p>
                        </div>

                        {/* Search */}
                        <Link
                            to="/forum/search"
                            className="flex items-center gap-2 px-5 py-2.5 bg-white/10 hover:bg-white/20 rounded-xl text-white transition-all duration-200 backdrop-blur-sm border border-white/10"
                        >
                            <svg
                                className="w-5 h-5"
                                fill="none"
                                viewBox="0 0 24 24"
                                stroke="currentColor"
                                strokeWidth={2}
                            >
                                <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                                />
                            </svg>
                            Search
                        </Link>
                    </div>
                </div>
                {/* Background decoration */}
                <div className="absolute top-0 right-0 w-64 h-64 bg-purple-500/10 rounded-full blur-3xl" />
                <div className="absolute bottom-0 left-0 w-48 h-48 bg-cyan-500/10 rounded-full blur-3xl" />
            </div>

            {/* Quick stats */}
            {user && (
                <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
                    <div className="group card bg-gradient-to-br from-purple-600/10 to-purple-600/5 border border-purple-500/20 hover:border-purple-500/40 transition-all duration-200">
                        <div className="text-3xl font-bold text-purple-400">{user.karma_score || 0}</div>
                        <div className="text-sm text-gray-400 mt-1">Your Karma</div>
                    </div>
                    <div className="group card bg-gradient-to-br from-cyan-600/10 to-cyan-600/5 border border-cyan-500/20 hover:border-cyan-500/40 transition-all duration-200">
                        <div className="text-3xl font-bold text-cyan-400">
                            {categories?.reduce((acc, c) => acc + c.forums.reduce((a, f) => a + f.topic_count, 0), 0) || 0}
                        </div>
                        <div className="text-sm text-gray-400 mt-1">Total Topics</div>
                    </div>
                    <div className="group card bg-gradient-to-br from-fuchsia-600/10 to-fuchsia-600/5 border border-fuchsia-500/20 hover:border-fuchsia-500/40 transition-all duration-200">
                        <div className="text-3xl font-bold text-fuchsia-400">
                            {categories?.reduce((acc, c) => acc + c.forums.reduce((a, f) => a + f.post_count, 0), 0) || 0}
                        </div>
                        <div className="text-sm text-gray-400 mt-1">Total Posts</div>
                    </div>
                    <div className="group card bg-gradient-to-br from-amber-600/10 to-amber-600/5 border border-amber-500/20 hover:border-amber-500/40 transition-all duration-200">
                        <div className="text-3xl font-bold text-amber-400">
                            {categories?.reduce((acc, c) => acc + c.forums.length, 0) || 0}
                        </div>
                        <div className="text-sm text-gray-400 mt-1">Forums</div>
                    </div>
                </div>
            )}

            {/* Recent Topics */}
            {recentTopics && recentTopics.items.length > 0 && (
                <div className="card bg-gray-800/50 border border-gray-700 rounded-xl overflow-hidden">
                    <div className="flex items-center justify-between p-5 border-b border-gray-700">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-fuchsia-500 flex items-center justify-center">
                                <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                            </div>
                            <h2 className="text-xl font-bold text-white">Recent Topics</h2>
                        </div>
                        <Link
                            to="/forum/recent"
                            className="text-sm text-purple-400 hover:text-purple-300 transition-colors font-medium"
                        >
                            View all →
                        </Link>
                    </div>
                    <div className="px-5 pb-5">
                        <TopicList
                            topics={recentTopics.items}
                            showForum={true}
                            emptyMessage="No recent topics"
                        />
                    </div>
                </div>
            )}

            {/* Error state */}
            {categoriesError && (
                <div className="card bg-red-500/10 border border-red-500/30 text-red-400">
                    <div className="flex items-center gap-3">
                        <svg
                            className="w-6 h-6"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                            strokeWidth={2}
                        >
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                            />
                        </svg>
                        <span>Failed to load forums. Please try again later.</span>
                    </div>
                </div>
            )}

            {/* Categories and Forums */}
            <ForumCategoryList
                categories={categories || []}
                isLoading={categoriesLoading}
            />
        </div>
    )
}
