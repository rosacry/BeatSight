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
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold text-white">Community Forums</h1>
                    <p className="text-gray-400 mt-1">
                        Discuss beatmaps, strategies, and connect with other drummers
                    </p>
                </div>

                {/* Search */}
                <Link
                    to="/forum/search"
                    className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-gray-300 transition-colors"
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

            {/* Quick stats */}
            {user && (
                <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
                    <div className="card bg-gray-800/50 border border-gray-700">
                        <div className="text-2xl font-bold text-white">{user.karma_score || 0}</div>
                        <div className="text-sm text-gray-400">Karma</div>
                    </div>
                    <div className="card bg-gray-800/50 border border-gray-700">
                        <div className="text-2xl font-bold text-white">
                            {categories?.reduce((acc, c) => acc + c.forums.reduce((a, f) => a + f.topic_count, 0), 0) || 0}
                        </div>
                        <div className="text-sm text-gray-400">Total Topics</div>
                    </div>
                    <div className="card bg-gray-800/50 border border-gray-700">
                        <div className="text-2xl font-bold text-white">
                            {categories?.reduce((acc, c) => acc + c.forums.reduce((a, f) => a + f.post_count, 0), 0) || 0}
                        </div>
                        <div className="text-sm text-gray-400">Total Posts</div>
                    </div>
                    <div className="card bg-gray-800/50 border border-gray-700">
                        <div className="text-2xl font-bold text-white">
                            {categories?.reduce((acc, c) => acc + c.forums.length, 0) || 0}
                        </div>
                        <div className="text-sm text-gray-400">Forums</div>
                    </div>
                </div>
            )}

            {/* Recent Topics */}
            {recentTopics && recentTopics.items.length > 0 && (
                <div className="card bg-gray-800/50 border border-gray-700">
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="text-xl font-bold text-white">Recent Topics</h2>
                        <Link
                            to="/forum/recent"
                            className="text-sm text-purple-400 hover:text-purple-300 transition-colors"
                        >
                            View all →
                        </Link>
                    </div>
                    <TopicList
                        topics={recentTopics.items}
                        showForum={true}
                        emptyMessage="No recent topics"
                    />
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
