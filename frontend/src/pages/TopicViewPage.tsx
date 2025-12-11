/**
 * Topic view page showing a single topic and its posts.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams, Link, useSearchParams } from 'react-router-dom'
import {
    getTopic,
    getTopicPosts,
    createPost,
    watchTopic,
    unwatchTopic,
    lockTopic,
    unlockTopic,
    pinTopic,
    unpinTopic,
} from '@/api/forum'
import { ForumPostCard, ForumPoll, PostEditor } from '@/components/forum'
import { useAuthStore } from '@/stores/authStore'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import clsx from 'clsx'

export function TopicViewPage() {
    const { topicId } = useParams<{ topicId: string }>()
    const [searchParams, setSearchParams] = useSearchParams()
    const queryClient = useQueryClient()
    const user = useAuthStore((state) => state.user)

    const page = parseInt(searchParams.get('page') || '1', 10)

    const {
        data: topic,
        isLoading: topicLoading,
        error: topicError,
    } = useQuery({
        queryKey: ['topic', topicId],
        queryFn: () => getTopic(topicId!),
        enabled: !!topicId,
    })

    useDocumentTitle(topic?.title || 'topic')

    const {
        data: postsData,
        isLoading: postsLoading,
        refetch: refetchPosts,
    } = useQuery({
        queryKey: ['topicPosts', topicId, page],
        queryFn: () =>
            getTopicPosts(topicId!, {
                page,
                pageSize: 20,
            }),
        enabled: !!topicId,
    })

    // Watch/unwatch mutation
    const watchMutation = useMutation({
        mutationFn: async () => {
            if (topic?.is_watched) {
                return unwatchTopic(topicId!)
            } else {
                return watchTopic(topicId!)
            }
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['topic', topicId] })
        },
    })

    // Lock/unlock mutations (moderator only)
    const lockMutation = useMutation({
        mutationFn: async () => {
            if (topic?.is_locked) {
                return unlockTopic(topicId!)
            } else {
                return lockTopic(topicId!)
            }
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['topic', topicId] })
        },
    })

    // Pin/unpin mutations (moderator only)
    const pinMutation = useMutation({
        mutationFn: async () => {
            if (topic?.is_pinned) {
                return unpinTopic(topicId!)
            } else {
                return pinTopic(topicId!)
            }
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['topic', topicId] })
        },
    })

    const handlePageChange = (newPage: number) => {
        setSearchParams({ page: newPage.toString() })
        window.scrollTo({ top: 0, behavior: 'smooth' })
    }

    const handleReply = async (content: string) => {
        await createPost(topicId!, { content })
        refetchPosts()
        queryClient.invalidateQueries({ queryKey: ['topic', topicId] })
    }

    const canModerate =
        user?.roles?.includes('admin') || user?.roles?.includes('staff') || user?.roles?.includes('verifier')

    if (topicLoading) {
        return (
            <div className="max-w-4xl mx-auto">
                <div className="animate-pulse space-y-6">
                    <div className="h-8 bg-dark-300 rounded w-3/4" />
                    <div className="h-4 bg-dark-300 rounded w-48" />
                    <div className="space-y-4">
                        {[1, 2, 3].map((i) => (
                            <div key={i} className="card bg-dark-400/50 border border-white/10">
                                <div className="h-32 bg-dark-300 rounded" />
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        )
    }

    if (topicError || !topic) {
        return (
            <div className="max-w-4xl mx-auto">
                <div className="card bg-red-500/10 border border-red-500/30 text-red-400 text-center py-12">
                    <h2 className="text-xl font-bold mb-2">Topic Not Found</h2>
                    <p>The topic you're looking for doesn't exist or has been removed.</p>
                    <Link to="/forum" className="btn btn-primary mt-4">
                        Back to Forums
                    </Link>
                </div>
            </div>
        )
    }

    return (
        <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">
            {/* Topic header */}
            <div className="card bg-dark-400/50 border border-white/10">
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap mb-2">
                            {topic.topic_type === 'announcement' && (
                                <span className="text-xs px-2 py-0.5 rounded bg-yellow-500/20 text-yellow-400">
                                    Announcement
                                </span>
                            )}
                            {topic.is_pinned && topic.topic_type !== 'announcement' && (
                                <span className="text-xs px-2 py-0.5 rounded bg-purple-500/20 text-purple-400">
                                    Pinned
                                </span>
                            )}
                            {topic.is_locked && (
                                <span className="text-xs px-2 py-0.5 rounded bg-red-500/20 text-red-400">
                                    Locked
                                </span>
                            )}
                        </div>
                        <h1 className="text-xl sm:text-2xl font-bold text-white break-words">
                            {topic.title}
                        </h1>
                        <div className="flex flex-wrap items-center gap-2 sm:gap-4 mt-2 text-xs sm:text-sm text-gray-400">
                            <span>
                                by{' '}
                                <span className="text-gray-300 truncate max-w-[100px] sm:max-w-none inline-block align-bottom">
                                    {topic.author?.display_name || 'Unknown'}
                                </span>
                            </span>
                            <span className="whitespace-nowrap">{topic.view_count.toLocaleString()} views</span>
                            <span className="whitespace-nowrap">{topic.post_count.toLocaleString()} posts</span>
                        </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2 flex-shrink-0">
                        {user && (
                            <button
                                onClick={() => watchMutation.mutate()}
                                disabled={watchMutation.isPending}
                                className={clsx(
                                    'flex items-center gap-1 px-3 py-2 rounded transition-colors text-sm',
                                    topic.is_watched
                                        ? 'bg-primary-500 text-white'
                                        : 'bg-dark-400 text-gray-300 hover:bg-dark-300'
                                )}
                            >
                                <svg
                                    className="w-4 h-4"
                                    fill={topic.is_watched ? 'currentColor' : 'none'}
                                    viewBox="0 0 24 24"
                                    stroke="currentColor"
                                    strokeWidth={2}
                                >
                                    <path
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
                                    />
                                </svg>
                                {topic.is_watched ? 'Watching' : 'Watch'}
                            </button>
                        )}

                        {/* Moderator actions */}
                        {canModerate && (
                            <div className="relative group">
                                <button className="p-2 rounded bg-dark-300 text-gray-300 hover:bg-gray-600 transition-colors">
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
                                            d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z"
                                        />
                                    </svg>
                                </button>
                                <div className="absolute right-0 top-full mt-1 w-48 bg-dark-400 border border-white/10 rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-10">
                                    <button
                                        onClick={() => lockMutation.mutate()}
                                        disabled={lockMutation.isPending}
                                        className="w-full px-4 py-2 text-left text-sm text-gray-300 hover:bg-dark-300 first:rounded-t-lg"
                                    >
                                        {topic.is_locked ? 'Unlock Topic' : 'Lock Topic'}
                                    </button>
                                    <button
                                        onClick={() => pinMutation.mutate()}
                                        disabled={pinMutation.isPending}
                                        className="w-full px-4 py-2 text-left text-sm text-gray-300 hover:bg-dark-300 last:rounded-b-lg"
                                    >
                                        {topic.is_pinned ? 'Unpin Topic' : 'Pin Topic'}
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Poll (if exists) */}
            {topic.poll && (
                <ForumPoll
                    poll={topic.poll}
                    topicId={topicId!}
                    isLocked={topic.is_locked}
                />
            )}

            {/* Posts */}
            <div className="space-y-4">
                {postsLoading ? (
                    <>
                        {[1, 2, 3].map((i) => (
                            <div
                                key={i}
                                className="card bg-dark-400/50 border border-white/10 animate-pulse"
                            >
                                <div className="h-32 bg-dark-300 rounded" />
                            </div>
                        ))}
                    </>
                ) : (
                    postsData?.items.map((post, index) => (
                        <ForumPostCard
                            key={post.id}
                            post={post}
                            isFirstPost={page === 1 && index === 0}
                            isLocked={topic.is_locked}
                            postNumber={(page - 1) * 20 + index + 1}
                        />
                    ))
                )}
            </div>

            {/* Pagination */}
            {postsData && postsData.total_pages > 1 && (
                <div className="flex items-center justify-center gap-2">
                    <button
                        onClick={() => handlePageChange(page - 1)}
                        disabled={!postsData.has_prev}
                        className={clsx(
                            'px-4 py-2 rounded transition-colors',
                            postsData.has_prev
                                ? 'bg-dark-400 text-white hover:bg-dark-300'
                                : 'bg-dark-400/50 text-gray-500 cursor-not-allowed'
                        )}
                    >
                        Previous
                    </button>

                    <div className="flex items-center gap-1">
                        {Array.from(
                            { length: Math.min(postsData.total_pages, 7) },
                            (_, i) => {
                                let pageNum: number
                                if (postsData.total_pages <= 7) {
                                    pageNum = i + 1
                                } else if (page <= 4) {
                                    pageNum = i + 1
                                } else if (page >= postsData.total_pages - 3) {
                                    pageNum = postsData.total_pages - 6 + i
                                } else {
                                    pageNum = page - 3 + i
                                }

                                return (
                                    <button
                                        key={pageNum}
                                        onClick={() => handlePageChange(pageNum)}
                                        className={clsx(
                                            'w-10 h-10 rounded transition-colors',
                                            page === pageNum
                                                ? 'bg-primary-500 text-white'
                                                : 'bg-dark-400 text-gray-400 hover:text-white'
                                        )}
                                    >
                                        {pageNum}
                                    </button>
                                )
                            }
                        )}
                    </div>

                    <button
                        onClick={() => handlePageChange(page + 1)}
                        disabled={!postsData.has_next}
                        className={clsx(
                            'px-4 py-2 rounded transition-colors',
                            postsData.has_next
                                ? 'bg-dark-400 text-white hover:bg-dark-300'
                                : 'bg-dark-400/50 text-gray-500 cursor-not-allowed'
                        )}
                    >
                        Next
                    </button>
                </div>
            )}

            {/* Reply editor */}
            <PostEditor
                onSubmit={handleReply}
                isLocked={topic.is_locked}
                placeholder="Write your reply..."
                submitText="Post Reply"
            />
        </div>
    )
}
