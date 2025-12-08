/**
 * Forum post component for displaying a single post in a topic.
 */

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { format, formatDistanceToNow } from 'date-fns'
import { editPost, deletePost } from '@/api/forum'
import type { ForumPost } from '@/types/forum'
import { PostVoteButtons } from './PostVoteButtons'
import { useAuthStore } from '@/stores/authStore'

interface ForumPostCardProps {
    post: ForumPost
    /** Whether this is the first post (OP) */
    isFirstPost?: boolean
    /** Whether the topic is locked */
    isLocked?: boolean
    /** Post number in the topic */
    postNumber?: number
}

export function ForumPostCard({
    post,
    isFirstPost = false,
    isLocked = false,
    postNumber,
}: ForumPostCardProps) {
    const queryClient = useQueryClient()
    const user = useAuthStore((state) => state.user)

    const [isEditing, setIsEditing] = useState(false)
    const [editContent, setEditContent] = useState(post.content)
    const [editReason, setEditReason] = useState('')
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

    const isAuthor = user?.id === post.user_id
    const canEdit = isAuthor && !isLocked && !post.is_deleted
    const canDelete = (isAuthor || user?.roles?.includes('admin') || user?.roles?.includes('staff')) && !post.is_deleted

    const editMutation = useMutation({
        mutationFn: async () => {
            return editPost(post.id, {
                content: editContent,
                edit_reason: editReason || undefined,
            })
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['topicPosts'] })
            setIsEditing(false)
            setEditReason('')
        },
    })

    const deleteMutation = useMutation({
        mutationFn: async () => {
            return deletePost(post.id)
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['topicPosts'] })
            setShowDeleteConfirm(false)
        },
    })

    const handleSaveEdit = () => {
        if (editContent.trim() && editContent !== post.content) {
            editMutation.mutate()
        } else {
            setIsEditing(false)
        }
    }

    const handleCancelEdit = () => {
        setEditContent(post.content)
        setEditReason('')
        setIsEditing(false)
    }

    // Deleted post display
    if (post.is_deleted) {
        return (
            <div className="card bg-gray-800/30 border border-gray-700/50">
                <div className="flex items-center gap-3 text-gray-500 italic">
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                        />
                    </svg>
                    <span>This post has been deleted.</span>
                </div>
            </div>
        )
    }

    return (
        <div
            className={clsx(
                'card bg-gray-800/50 border',
                isFirstPost ? 'border-purple-500/30' : 'border-gray-700'
            )}
            id={`post-${post.id}`}
        >
            <div className="flex gap-4">
                {/* Vote buttons (vertical) */}
                <div className="flex-shrink-0">
                    <PostVoteButtons
                        postId={post.id}
                        initialUpvotes={post.upvotes}
                        initialDownvotes={post.downvotes}
                        initialScore={post.score}
                        initialUserVote={post.user_vote}
                        vertical={true}
                        disabled={isLocked || isAuthor}
                    />
                </div>

                {/* Main content */}
                <div className="flex-1 min-w-0">
                    {/* Post header */}
                    <div className="flex items-start justify-between mb-3">
                        <div className="flex items-center gap-3">
                            {/* Author avatar */}
                            {post.author?.avatar_url ? (
                                <img
                                    src={post.author.avatar_url}
                                    alt={post.author.display_name}
                                    className="w-10 h-10 rounded-full"
                                />
                            ) : (
                                <div className="w-10 h-10 rounded-full bg-purple-600 flex items-center justify-center text-white font-medium">
                                    {post.author?.display_name?.[0]?.toUpperCase() || '?'}
                                </div>
                            )}

                            <div>
                                <div className="flex items-center gap-2">
                                    <span className="font-medium text-white">
                                        {post.author?.display_name || 'Unknown'}
                                    </span>
                                    {post.author?.role && post.author.role !== 'user' && (
                                        <span
                                            className={clsx(
                                                'text-xs px-2 py-0.5 rounded',
                                                post.author.role === 'admin' &&
                                                'bg-red-500/20 text-red-400',
                                                post.author.role === 'staff' &&
                                                'bg-blue-500/20 text-blue-400',
                                                post.author.role === 'verifier' &&
                                                'bg-green-500/20 text-green-400'
                                            )}
                                        >
                                            {post.author.role}
                                        </span>
                                    )}
                                    {isFirstPost && (
                                        <span className="text-xs px-2 py-0.5 rounded bg-purple-500/20 text-purple-400">
                                            OP
                                        </span>
                                    )}
                                </div>
                                <div className="text-xs text-gray-400">
                                    {post.author?.post_count?.toLocaleString()} posts •{' '}
                                    {post.author?.karma?.toLocaleString()} karma
                                </div>
                            </div>
                        </div>

                        <div className="flex items-center gap-2 text-sm text-gray-400">
                            {postNumber && (
                                <a
                                    href={`#post-${post.id}`}
                                    className="hover:text-purple-400 transition-colors"
                                >
                                    #{postNumber}
                                </a>
                            )}
                            <span
                                title={format(new Date(post.created_at), 'PPpp')}
                                className="cursor-help"
                            >
                                {formatDistanceToNow(new Date(post.created_at), {
                                    addSuffix: true,
                                })}
                            </span>
                        </div>
                    </div>

                    {/* Post content */}
                    {isEditing ? (
                        <div className="space-y-3">
                            <textarea
                                value={editContent}
                                onChange={(e) => setEditContent(e.target.value)}
                                className="w-full h-32 px-4 py-3 bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent resize-y"
                                placeholder="Write your reply..."
                            />
                            <input
                                type="text"
                                value={editReason}
                                onChange={(e) => setEditReason(e.target.value)}
                                className="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-white text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
                                placeholder="Edit reason (optional)"
                            />
                            <div className="flex gap-2">
                                <button
                                    onClick={handleSaveEdit}
                                    disabled={editMutation.isPending || !editContent.trim()}
                                    className="btn btn-primary text-sm"
                                >
                                    {editMutation.isPending ? 'Saving...' : 'Save'}
                                </button>
                                <button
                                    onClick={handleCancelEdit}
                                    disabled={editMutation.isPending}
                                    className="btn btn-secondary text-sm"
                                >
                                    Cancel
                                </button>
                            </div>
                        </div>
                    ) : (
                        <div className="prose prose-invert max-w-none">
                            {post.content_html ? (
                                <div
                                    dangerouslySetInnerHTML={{ __html: post.content_html }}
                                />
                            ) : (
                                <p className="text-gray-200 whitespace-pre-wrap">
                                    {post.content}
                                </p>
                            )}
                        </div>
                    )}

                    {/* Edit indicator */}
                    {post.edit_count > 0 && !isEditing && (
                        <div className="mt-2 text-xs text-gray-500 italic">
                            Edited {post.edit_count} time{post.edit_count > 1 ? 's' : ''}
                            {post.edit_reason && (
                                <span> • Reason: {post.edit_reason}</span>
                            )}
                        </div>
                    )}

                    {/* Post actions */}
                    {!isEditing && (canEdit || canDelete) && (
                        <div className="mt-4 pt-3 border-t border-gray-700 flex items-center gap-4">
                            {canEdit && (
                                <button
                                    onClick={() => setIsEditing(true)}
                                    className="text-sm text-gray-400 hover:text-white transition-colors"
                                >
                                    Edit
                                </button>
                            )}
                            {canDelete && (
                                <>
                                    {showDeleteConfirm ? (
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm text-red-400">
                                                Delete this post?
                                            </span>
                                            <button
                                                onClick={() => deleteMutation.mutate()}
                                                disabled={deleteMutation.isPending}
                                                className="text-sm text-red-400 hover:text-red-300 font-medium"
                                            >
                                                {deleteMutation.isPending
                                                    ? 'Deleting...'
                                                    : 'Yes'}
                                            </button>
                                            <button
                                                onClick={() => setShowDeleteConfirm(false)}
                                                className="text-sm text-gray-400 hover:text-white"
                                            >
                                                No
                                            </button>
                                        </div>
                                    ) : (
                                        <button
                                            onClick={() => setShowDeleteConfirm(true)}
                                            className="text-sm text-gray-400 hover:text-red-400 transition-colors"
                                        >
                                            Delete
                                        </button>
                                    )}
                                </>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
