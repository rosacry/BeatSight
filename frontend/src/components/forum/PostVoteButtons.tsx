/**
 * Post vote buttons component for forum upvote/downvote.
 *
 * Displays upvote and downvote buttons with vote counts.
 * Clicking the same vote again removes it.
 */

import { useState, useCallback } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { voteOnPost, removePostVote } from '@/api/forum'
import type { VoteType, VoteResponse } from '@/types/forum'
import { useAuthStore } from '@/stores/authStore'

// Arrow icons
function ArrowUp({ className }: { className?: string }) {
    return (
        <svg
            className={className}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2.5}
        >
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" />
        </svg>
    )
}

function ArrowDown({ className }: { className?: string }) {
    return (
        <svg
            className={className}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2.5}
        >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
    )
}

interface PostVoteButtonsProps {
    postId: string
    initialUpvotes?: number
    initialDownvotes?: number
    initialScore?: number
    initialUserVote?: VoteType | null
    /** Vertical or horizontal layout */
    vertical?: boolean
    /** Disable voting (e.g., for own posts or locked topics) */
    disabled?: boolean
    /** Show score only (hide individual vote counts) */
    scoreOnly?: boolean
    /** Callback when vote changes */
    onVoteChange?: (votes: VoteResponse) => void
}

export function PostVoteButtons({
    postId,
    initialUpvotes = 0,
    initialDownvotes = 0,
    initialScore = 0,
    initialUserVote = null,
    vertical = true,
    disabled = false,
    scoreOnly = false,
    onVoteChange,
}: PostVoteButtonsProps) {
    const queryClient = useQueryClient()
    const user = useAuthStore((state) => state.user)

    const [votes, setVotes] = useState({
        upvotes: initialUpvotes,
        downvotes: initialDownvotes,
        score: initialScore,
        user_vote: initialUserVote,
    })

    const voteMutation = useMutation({
        mutationFn: async ({ voteType }: { voteType: VoteType }) => {
            return voteOnPost(postId, voteType)
        },
        onSuccess: (data) => {
            setVotes({
                upvotes: data.upvotes,
                downvotes: data.downvotes,
                score: data.score,
                user_vote: data.user_vote,
            })
            onVoteChange?.(data)
            // Invalidate topic posts query to refresh
            queryClient.invalidateQueries({ queryKey: ['topicPosts'] })
        },
    })

    const removeMutation = useMutation({
        mutationFn: async () => {
            return removePostVote(postId)
        },
        onSuccess: (data) => {
            setVotes({
                upvotes: data.upvotes,
                downvotes: data.downvotes,
                score: data.score,
                user_vote: data.user_vote,
            })
            onVoteChange?.(data)
            queryClient.invalidateQueries({ queryKey: ['topicPosts'] })
        },
    })

    const handleVote = useCallback(
        (voteType: VoteType) => {
            if (disabled || !user) return

            // If user already voted the same way, remove the vote
            if (votes.user_vote === voteType) {
                removeMutation.mutate()
            } else {
                voteMutation.mutate({ voteType })
            }
        },
        [disabled, user, votes.user_vote, voteMutation, removeMutation]
    )

    const isLoading = voteMutation.isPending || removeMutation.isPending
    const isUpvoted = votes.user_vote === 'upvote'
    const isDownvoted = votes.user_vote === 'downvote'

    // Score color based on value
    const scoreColor =
        votes.score > 0
            ? 'text-green-400'
            : votes.score < 0
                ? 'text-red-400'
                : 'text-gray-400'

    if (vertical) {
        return (
            <div className="flex flex-col items-center gap-1">
                <button
                    onClick={() => handleVote('upvote')}
                    disabled={disabled || isLoading || !user}
                    className={clsx(
                        'p-1 rounded transition-colors',
                        isUpvoted
                            ? 'text-green-400 bg-green-500/20'
                            : 'text-gray-400 hover:text-green-400 hover:bg-green-500/10',
                        (disabled || !user) && 'opacity-50 cursor-not-allowed'
                    )}
                    title={user ? 'Upvote' : 'Log in to vote'}
                    aria-label="Upvote"
                >
                    <ArrowUp className="w-5 h-5" />
                </button>

                <span className={clsx('text-sm font-medium tabular-nums', scoreColor)}>
                    {votes.score}
                </span>

                <button
                    onClick={() => handleVote('downvote')}
                    disabled={disabled || isLoading || !user}
                    className={clsx(
                        'p-1 rounded transition-colors',
                        isDownvoted
                            ? 'text-red-400 bg-red-500/20'
                            : 'text-gray-400 hover:text-red-400 hover:bg-red-500/10',
                        (disabled || !user) && 'opacity-50 cursor-not-allowed'
                    )}
                    title={user ? 'Downvote' : 'Log in to vote'}
                    aria-label="Downvote"
                >
                    <ArrowDown className="w-5 h-5" />
                </button>
            </div>
        )
    }

    // Horizontal layout
    return (
        <div className="flex items-center gap-2">
            <button
                onClick={() => handleVote('upvote')}
                disabled={disabled || isLoading || !user}
                className={clsx(
                    'flex items-center gap-1 px-2 py-1 rounded transition-colors',
                    isUpvoted
                        ? 'text-green-400 bg-green-500/20'
                        : 'text-gray-400 hover:text-green-400 hover:bg-green-500/10',
                    (disabled || !user) && 'opacity-50 cursor-not-allowed'
                )}
                title={user ? 'Upvote' : 'Log in to vote'}
            >
                <ArrowUp className="w-4 h-4" />
                {!scoreOnly && <span className="text-xs">{votes.upvotes}</span>}
            </button>

            {scoreOnly && (
                <span className={clsx('text-sm font-medium tabular-nums', scoreColor)}>
                    {votes.score}
                </span>
            )}

            <button
                onClick={() => handleVote('downvote')}
                disabled={disabled || isLoading || !user}
                className={clsx(
                    'flex items-center gap-1 px-2 py-1 rounded transition-colors',
                    isDownvoted
                        ? 'text-red-400 bg-red-500/20'
                        : 'text-gray-400 hover:text-red-400 hover:bg-red-500/10',
                    (disabled || !user) && 'opacity-50 cursor-not-allowed'
                )}
                title={user ? 'Downvote' : 'Log in to vote'}
            >
                <ArrowDown className="w-4 h-4" />
                {!scoreOnly && <span className="text-xs">{votes.downvotes}</span>}
            </button>
        </div>
    )
}
