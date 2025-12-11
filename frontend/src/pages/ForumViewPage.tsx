/**
 * Forum view page showing topics in a specific forum.
 */

import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useParams, Link, useNavigate, useSearchParams } from 'react-router-dom'
import { getForum, getForumTopics, createTopic } from '@/api/forum'
import { TopicList, CreateTopicForm } from '@/components/forum'
import { useAuthStore } from '@/stores/authStore'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import clsx from 'clsx'

type SortOption = 'newest' | 'oldest' | 'most_posts' | 'most_views'

export function ForumViewPage() {
    const { forumId } = useParams<{ forumId: string }>()
    const navigate = useNavigate()
    const [searchParams, setSearchParams] = useSearchParams()
    const user = useAuthStore((state) => state.user)

    const page = parseInt(searchParams.get('page') || '1', 10)
    const sort = (searchParams.get('sort') as SortOption) || 'newest'
    const showNew = searchParams.get('new') === 'true'
    const [showCreateForm, setShowCreateForm] = useState(showNew)

    const {
        data: forum,
        isLoading: forumLoading,
        error: forumError,
    } = useQuery({
        queryKey: ['forum', forumId],
        queryFn: () => getForum(forumId!),
        enabled: !!forumId,
    })

    useDocumentTitle(forum?.name || 'forum')

    // Auto-show create form when ?new=true is in URL
    useEffect(() => {
        if (showNew && user) {
            setShowCreateForm(true)
            // Remove the ?new param from URL without navigation
            const newParams = new URLSearchParams(searchParams)
            newParams.delete('new')
            setSearchParams(newParams, { replace: true })
        }
    }, [showNew, user, searchParams, setSearchParams])

    const {
        data: topicsData,
        isLoading: topicsLoading,
    } = useQuery({
        queryKey: ['forumTopics', forumId, page, sort],
        queryFn: () =>
            getForumTopics(forumId!, {
                page,
                pageSize: 25,
                sort,
            }),
        enabled: !!forumId,
    })

    const handleSortChange = (newSort: SortOption) => {
        setSearchParams({ sort: newSort, page: '1' })
    }

    const handlePageChange = (newPage: number) => {
        setSearchParams({ sort, page: newPage.toString() })
    }

    const handleCreateTopic = async (data: {
        title: string
        content: string
        poll?: {
            title: string
            options: string[]
            maxOptions: number
            allowChange: boolean
            hideResults: boolean
            endsInDays?: number
        }
    }) => {
        const result = await createTopic(forumId!, {
            title: data.title,
            content: data.content,
            poll: data.poll
                ? {
                    title: data.poll.title,
                    options: data.poll.options,
                    max_options: data.poll.maxOptions,
                    allow_change: data.poll.allowChange,
                    hide_results: data.poll.hideResults,
                    ends_in_days: data.poll.endsInDays,
                }
                : undefined,
        })

        // Navigate to the new topic
        navigate(`/forum/topics/${result.id}`)
    }

    if (forumLoading) {
        return (
            <div className="max-w-6xl mx-auto">
                <div className="animate-pulse space-y-6">
                    <div className="h-8 bg-dark-300 rounded w-64" />
                    <div className="h-4 bg-dark-300 rounded w-96" />
                    <div className="card bg-dark-400/50 border border-white/10">
                        <div className="space-y-4">
                            {[1, 2, 3, 4, 5].map((i) => (
                                <div key={i} className="h-20 bg-dark-300 rounded" />
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        )
    }

    if (forumError || !forum) {
        return (
            <div className="max-w-6xl mx-auto">
                <div className="card bg-red-500/10 border border-red-500/30 text-red-400 text-center py-12">
                    <h2 className="text-xl font-bold mb-2">Forum Not Found</h2>
                    <p>The forum you're looking for doesn't exist or has been removed.</p>
                    <Link to="/forum" className="btn btn-primary mt-4">
                        Back to Forums
                    </Link>
                </div>
            </div>
        )
    }

    return (
        <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
            {/* Forum header */}
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                <div className="min-w-0 flex-1">
                    <h1 className="text-2xl sm:text-3xl font-bold text-white break-words">{forum.name}</h1>
                    {forum.description && (
                        <p className="text-gray-400 mt-1 text-sm sm:text-base">{forum.description}</p>
                    )}
                    <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
                        <span className="whitespace-nowrap">{forum.topic_count.toLocaleString()} topics</span>
                        <span className="whitespace-nowrap">{forum.post_count.toLocaleString()} posts</span>
                    </div>
                </div>

                {/* Create topic button */}
                {user && forum.allow_topics && (
                    <button
                        onClick={() => setShowCreateForm(!showCreateForm)}
                        className="btn btn-primary w-full sm:w-auto"
                    >
                        {showCreateForm ? 'Cancel' : 'New Topic'}
                    </button>
                )}
            </div>

            {/* Create topic form */}
            {showCreateForm && (
                <div className="card bg-dark-400/50 border border-white/10">
                    <h2 className="text-xl font-bold text-white mb-4">Create New Topic</h2>
                    <CreateTopicForm
                        forumId={forumId!}
                        onSubmit={handleCreateTopic}
                        onCancel={() => setShowCreateForm(false)}
                    />
                </div>
            )}

            {/* Sort and filter controls */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div className="flex flex-col sm:flex-row sm:items-center gap-2">
                    <span className="text-sm text-gray-400">Sort by:</span>
                    <div className="flex flex-wrap gap-1">
                        {[
                            { value: 'newest', label: 'Newest' },
                            { value: 'oldest', label: 'Oldest' },
                            { value: 'most_posts', label: 'Replies' },
                            { value: 'most_views', label: 'Views' },
                        ].map((option) => (
                            <button
                                key={option.value}
                                onClick={() => handleSortChange(option.value as SortOption)}
                                className={clsx(
                                    'px-3 py-1.5 text-xs sm:text-sm rounded transition-colors',
                                    sort === option.value
                                        ? 'bg-primary-500 text-white'
                                        : 'bg-dark-400 text-gray-400 hover:text-white'
                                )}
                            >
                                {option.label}
                            </button>
                        ))}
                    </div>
                </div>

                {topicsData && (
                    <div className="text-sm text-gray-400 whitespace-nowrap">
                        <span className="hidden sm:inline">Showing {topicsData.items.length} of </span>
                        {topicsData.total.toLocaleString()} topics
                    </div>
                )}
            </div>

            {/* Topics list */}
            <div className="card bg-dark-400/50 border border-white/10 p-0 overflow-hidden">
                {topicsLoading ? (
                    <div className="p-4 space-y-4">
                        {[1, 2, 3, 4, 5].map((i) => (
                            <div key={i} className="h-20 bg-dark-300 rounded animate-pulse" />
                        ))}
                    </div>
                ) : (
                    <TopicList
                        topics={topicsData?.items || []}
                        emptyMessage="No topics yet. Be the first to start a discussion!"
                    />
                )}
            </div>

            {/* Pagination */}
            {topicsData && topicsData.total_pages > 1 && (
                <div className="flex items-center justify-center gap-2">
                    <button
                        onClick={() => handlePageChange(page - 1)}
                        disabled={!topicsData.has_prev}
                        className={clsx(
                            'px-4 py-2 rounded transition-colors',
                            topicsData.has_prev
                                ? 'bg-dark-400 text-white hover:bg-dark-300'
                                : 'bg-dark-400/50 text-gray-500 cursor-not-allowed'
                        )}
                    >
                        Previous
                    </button>

                    <div className="flex items-center gap-1">
                        {Array.from({ length: Math.min(topicsData.total_pages, 7) }, (_, i) => {
                            let pageNum: number
                            if (topicsData.total_pages <= 7) {
                                pageNum = i + 1
                            } else if (page <= 4) {
                                pageNum = i + 1
                            } else if (page >= topicsData.total_pages - 3) {
                                pageNum = topicsData.total_pages - 6 + i
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
                        })}
                    </div>

                    <button
                        onClick={() => handlePageChange(page + 1)}
                        disabled={!topicsData.has_next}
                        className={clsx(
                            'px-4 py-2 rounded transition-colors',
                            topicsData.has_next
                                ? 'bg-dark-400 text-white hover:bg-dark-300'
                                : 'bg-dark-400/50 text-gray-500 cursor-not-allowed'
                        )}
                    >
                        Next
                    </button>
                </div>
            )}
        </div>
    )
}
