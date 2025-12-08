/**
 * Topic list item component for displaying topics in a forum.
 */

import { Link } from 'react-router-dom'
import clsx from 'clsx'
import { format, formatDistanceToNow } from 'date-fns'
import type { Topic } from '@/types/forum'

// Icons
function PinIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="currentColor" viewBox="0 0 20 20">
            <path d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" />
        </svg>
    )
}

function LockIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
        </svg>
    )
}

function AnnouncementIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M11 5.882V19.24a1.76 1.76 0 01-3.417.592l-2.147-6.15M18 13a3 3 0 100-6M5.436 13.683A4.001 4.001 0 017 6h1.832c4.1 0 7.625-1.234 9.168-3v14c-1.543-1.766-5.067-3-9.168-3H7a3.988 3.988 0 01-1.564-.317z" />
        </svg>
    )
}

function PollIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
    )
}

interface TopicListItemProps {
    topic: Topic
    /** Show the forum name (for "recent topics" lists) */
    showForum?: boolean
}

export function TopicListItem({ topic, showForum = false }: TopicListItemProps) {
    const isSticky = topic.topic_type === 'sticky' || topic.is_pinned
    const isAnnouncement = topic.topic_type === 'announcement'

    return (
        <Link
            to={`/forum/topics/${topic.id}`}
            className={clsx(
                'block p-4 border-b border-gray-700 hover:bg-gray-800/50 transition-colors',
                isSticky && 'bg-purple-500/5',
                isAnnouncement && 'bg-yellow-500/5'
            )}
        >
            <div className="flex items-start gap-4">
                {/* Author avatar */}
                <div className="flex-shrink-0 hidden sm:block">
                    {topic.author?.avatar_url ? (
                        <img
                            src={topic.author.avatar_url}
                            alt={topic.author.display_name}
                            className="w-10 h-10 rounded-full"
                        />
                    ) : (
                        <div className="w-10 h-10 rounded-full bg-purple-600 flex items-center justify-center text-white font-medium">
                            {topic.author?.display_name?.[0]?.toUpperCase() || '?'}
                        </div>
                    )}
                </div>

                {/* Topic info */}
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                        {/* Topic type indicators */}
                        {isAnnouncement && (
                            <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded bg-yellow-500/20 text-yellow-400">
                                <AnnouncementIcon className="w-3 h-3" />
                                Announcement
                            </span>
                        )}
                        {isSticky && !isAnnouncement && (
                            <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded bg-purple-500/20 text-purple-400">
                                <PinIcon className="w-3 h-3" />
                                Pinned
                            </span>
                        )}
                        {topic.is_locked && (
                            <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded bg-red-500/20 text-red-400">
                                <LockIcon className="w-3 h-3" />
                                Locked
                            </span>
                        )}
                        {topic.poll && (
                            <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded bg-blue-500/20 text-blue-400">
                                <PollIcon className="w-3 h-3" />
                                Poll
                            </span>
                        )}
                    </div>

                    <h3
                        className={clsx(
                            'text-lg font-medium truncate mt-1',
                            topic.is_read ? 'text-gray-300' : 'text-white'
                        )}
                    >
                        {topic.title}
                    </h3>

                    <div className="flex items-center gap-2 mt-1 text-sm text-gray-400">
                        <span>
                            by{' '}
                            <span className="text-gray-300">
                                {topic.author?.display_name || 'Unknown'}
                            </span>
                        </span>
                        <span>•</span>
                        <span title={format(new Date(topic.created_at), 'PPpp')}>
                            {formatDistanceToNow(new Date(topic.created_at), {
                                addSuffix: true,
                            })}
                        </span>
                        {showForum && topic.forum_id && (
                            <>
                                <span>•</span>
                                <span className="text-purple-400">in Forum</span>
                            </>
                        )}
                    </div>
                </div>

                {/* Stats */}
                <div className="flex-shrink-0 text-right hidden md:block">
                    <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                            <div className="text-white font-medium">
                                {topic.post_count.toLocaleString()}
                            </div>
                            <div className="text-gray-500">posts</div>
                        </div>
                        <div>
                            <div className="text-white font-medium">
                                {topic.view_count.toLocaleString()}
                            </div>
                            <div className="text-gray-500">views</div>
                        </div>
                    </div>
                </div>

                {/* Last post info */}
                <div className="flex-shrink-0 hidden lg:block w-48">
                    {topic.last_post ? (
                        <div className="text-sm">
                            <div className="text-gray-400 truncate">
                                Last reply by{' '}
                                <span className="text-gray-300">
                                    {topic.last_post.author?.display_name || 'Unknown'}
                                </span>
                            </div>
                            <div
                                className="text-gray-500"
                                title={format(
                                    new Date(topic.last_post.created_at),
                                    'PPpp'
                                )}
                            >
                                {formatDistanceToNow(
                                    new Date(topic.last_post.created_at),
                                    { addSuffix: true }
                                )}
                            </div>
                        </div>
                    ) : (
                        <div className="text-sm text-gray-500">No replies yet</div>
                    )}
                </div>
            </div>
        </Link>
    )
}

interface TopicListProps {
    topics: Topic[]
    showForum?: boolean
    emptyMessage?: string
}

export function TopicList({
    topics,
    showForum = false,
    emptyMessage = 'No topics found.',
}: TopicListProps) {
    if (topics.length === 0) {
        return (
            <div className="text-center py-12 text-gray-400">
                <p>{emptyMessage}</p>
            </div>
        )
    }

    // Separate pinned/announcements from regular topics
    const pinnedTopics = topics.filter(
        (t) => t.topic_type === 'announcement' || t.topic_type === 'sticky' || t.is_pinned
    )
    const regularTopics = topics.filter(
        (t) => t.topic_type === 'normal' && !t.is_pinned
    )

    return (
        <div className="divide-y divide-gray-700">
            {pinnedTopics.map((topic) => (
                <TopicListItem
                    key={topic.id}
                    topic={topic}
                    showForum={showForum}
                />
            ))}
            {regularTopics.map((topic) => (
                <TopicListItem
                    key={topic.id}
                    topic={topic}
                    showForum={showForum}
                />
            ))}
        </div>
    )
}
