/**
 * Forum category list component.
 * Displays all forum categories with their forums.
 */

import { Link } from 'react-router-dom'
import { format, formatDistanceToNow } from 'date-fns'
import type { ForumCategory, Forum } from '@/types/forum'

interface ForumCardProps {
    forum: Forum
}

function ForumCard({ forum }: ForumCardProps) {
    return (
        <Link
            to={`/forum/${forum.id}`}
            className="group flex items-start gap-4 p-4 bg-gray-800/30 rounded-xl hover:bg-gray-700/50 transition-all duration-200 border border-gray-700 hover:border-purple-500/30"
        >
            {/* Forum icon */}
            <div className="flex-shrink-0 w-12 h-12 rounded-xl bg-gradient-to-br from-purple-600/30 to-fuchsia-600/20 flex items-center justify-center group-hover:from-purple-600/40 group-hover:to-fuchsia-600/30 transition-colors">
                <svg
                    className="w-6 h-6 text-purple-400"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                >
                    <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M17 8h2a2 2 0 012 2v6a2 2 0 01-2 2h-2v4l-4-4H9a1.994 1.994 0 01-1.414-.586m0 0L11 14h4a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2v4l.586-.586z"
                    />
                </svg>
            </div>

            {/* Forum info */}
            <div className="flex-1 min-w-0">
                <h3 className="text-lg font-medium text-white truncate group-hover:text-purple-300 transition-colors">{forum.name}</h3>
                {forum.description && (
                    <p className="text-sm text-gray-400 mt-1 line-clamp-2">
                        {forum.description}
                    </p>
                )}
                <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
                    <span className="flex items-center gap-1">
                        <span className="text-cyan-400 font-medium">{forum.topic_count.toLocaleString()}</span> topics
                    </span>
                    <span className="flex items-center gap-1">
                        <span className="text-fuchsia-400 font-medium">{forum.post_count.toLocaleString()}</span> posts
                    </span>
                </div>
            </div>

            {/* Last post info */}
            <div className="flex-shrink-0 hidden md:block text-right w-48">
                {forum.last_post ? (
                    <div className="text-sm">
                        <div className="text-gray-400 truncate">
                            {forum.last_post.author?.display_name || 'Unknown'}
                        </div>
                        <div
                            className="text-gray-500"
                            title={format(new Date(forum.last_post.created_at), 'PPpp')}
                        >
                            {formatDistanceToNow(new Date(forum.last_post.created_at), {
                                addSuffix: true,
                            })}
                        </div>
                    </div>
                ) : (
                    <div className="text-sm text-gray-500">No posts yet</div>
                )}
            </div>
        </Link>
    )
}

interface ForumCategoryCardProps {
    category: ForumCategory
}

function ForumCategoryCard({ category }: ForumCategoryCardProps) {
    if (!category.is_visible) return null

    const visibleForums = category.forums.filter((f) => f.is_visible)
    if (visibleForums.length === 0) return null

    return (
        <div className="card bg-gray-800/40 border border-gray-700 rounded-xl overflow-hidden">
            {/* Category header */}
            <div className="p-5 border-b border-gray-700 bg-gradient-to-r from-gray-800/50 to-gray-800/30">
                <h2 className="text-xl font-bold text-white">{category.name}</h2>
                {category.description && (
                    <p className="text-sm text-gray-400 mt-1">{category.description}</p>
                )}
            </div>

            {/* Forums list */}
            <div className="p-5 space-y-3">
                {visibleForums.map((forum) => (
                    <ForumCard key={forum.id} forum={forum} />
                ))}
            </div>
        </div>
    )
}

interface ForumCategoryListProps {
    categories: ForumCategory[]
    isLoading?: boolean
}

export function ForumCategoryList({ categories, isLoading }: ForumCategoryListProps) {
    if (isLoading) {
        return (
            <div className="space-y-6">
                {[1, 2, 3].map((i) => (
                    <div key={i} className="card bg-gray-800/50 border border-gray-700 animate-pulse">
                        <div className="pb-4 border-b border-gray-700">
                            <div className="h-6 bg-gray-700 rounded w-48" />
                            <div className="h-4 bg-gray-700 rounded w-64 mt-2" />
                        </div>
                        <div className="mt-4 space-y-3">
                            {[1, 2].map((j) => (
                                <div
                                    key={j}
                                    className="flex items-start gap-4 p-4 bg-gray-800/30 rounded-lg"
                                >
                                    <div className="w-12 h-12 bg-gray-700 rounded-lg" />
                                    <div className="flex-1">
                                        <div className="h-5 bg-gray-700 rounded w-32" />
                                        <div className="h-4 bg-gray-700 rounded w-48 mt-2" />
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                ))}
            </div>
        )
    }

    if (categories.length === 0) {
        return (
            <div className="text-center py-12">
                <div className="text-gray-400 text-lg">No forum categories found.</div>
                <p className="text-gray-500 mt-2">Check back later for community discussions.</p>
            </div>
        )
    }

    return (
        <div className="space-y-6">
            {categories.map((category) => (
                <ForumCategoryCard key={category.id} category={category} />
            ))}
        </div>
    )
}
