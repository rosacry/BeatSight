/**
 * Vote buttons component for map upvote/downvote.
 * 
 * Displays upvote and downvote buttons with counts.
 * Clicking the same vote again removes it.
 */

import { useState, useCallback } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { voteOnMap, removeVote } from '@/api/votes'
import type { VoteAction, VoteCountsResponse } from '@/types/votes'

// Simple chevron icons as inline SVG
function ChevronUp({ className }: { className?: string }) {
    return (
        <svg
            className={className}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
        >
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" />
        </svg>
    )
}

function ChevronDown({ className }: { className?: string }) {
    return (
        <svg
            className={className}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
        >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
    )
}

interface VoteButtonsProps {
    mapId: string
    initialVotes?: VoteCountsResponse
    /** Compact mode for inline display */
    compact?: boolean
    /** Disable voting (e.g., for own maps) */
    disabled?: boolean
    /** Callback when vote changes */
    onVoteChange?: (votes: VoteCountsResponse) => void
}

export function VoteButtons({
    mapId,
    initialVotes,
    compact = false,
    disabled = false,
    onVoteChange,
}: VoteButtonsProps) {
    const queryClient = useQueryClient()

    const [votes, setVotes] = useState<VoteCountsResponse>(
        initialVotes ?? {
            map_id: mapId,
            upvotes: 0,
            downvotes: 0,
            score: 0,
            user_vote: null,
        }
    )

    const voteMutation = useMutation({
        mutationFn: async ({ action }: { action: VoteAction }) => {
            return voteOnMap(mapId, action)
        },
        onSuccess: (data) => {
            setVotes(data)
            onVoteChange?.(data)
            // Invalidate any cached vote queries
            queryClient.invalidateQueries({ queryKey: ['mapVotes', mapId] })
        },
    })

    const removeMutation = useMutation({
        mutationFn: async () => {
            return removeVote(mapId)
        },
        onSuccess: (data) => {
            setVotes(data)
            onVoteChange?.(data)
            queryClient.invalidateQueries({ queryKey: ['mapVotes', mapId] })
        },
    })

    const handleVote = useCallback(
        (action: VoteAction) => {
            if (disabled) return

            // If user already voted the same way, remove the vote
            if (votes.user_vote === action) {
                removeMutation.mutate()
            } else {
                voteMutation.mutate({ action })
            }
        },
        [votes.user_vote, disabled, voteMutation, removeMutation]
    )

    const isLoading = voteMutation.isPending || removeMutation.isPending

    if (compact) {
        return (
            <div className="flex items-center gap-1 text-sm">
                <button
                    onClick={() => handleVote('upvote')}
                    disabled={disabled || isLoading}
                    className={clsx(
                        'p-0.5 rounded transition-colors',
                        votes.user_vote === 'upvote'
                            ? 'text-green-500 bg-green-500/10'
                            : 'text-gray-400 hover:text-green-500 hover:bg-green-500/10',
                        (disabled || isLoading) && 'opacity-50 cursor-not-allowed'
                    )}
                    title="Upvote"
                    aria-label="Upvote map"
                >
                    <ChevronUp className="w-4 h-4" />
                </button>
                <span
                    className={clsx(
                        'min-w-[2ch] text-center font-medium',
                        votes.score > 0 && 'text-green-500',
                        votes.score < 0 && 'text-red-500',
                        votes.score === 0 && 'text-gray-400'
                    )}
                >
                    {votes.score}
                </span>
                <button
                    onClick={() => handleVote('downvote')}
                    disabled={disabled || isLoading}
                    className={clsx(
                        'p-0.5 rounded transition-colors',
                        votes.user_vote === 'downvote'
                            ? 'text-red-500 bg-red-500/10'
                            : 'text-gray-400 hover:text-red-500 hover:bg-red-500/10',
                        (disabled || isLoading) && 'opacity-50 cursor-not-allowed'
                    )}
                    title="Downvote"
                    aria-label="Downvote map"
                >
                    <ChevronDown className="w-4 h-4" />
                </button>
            </div>
        )
    }

    return (
        <div className="flex flex-col items-center gap-0.5">
            <button
                onClick={() => handleVote('upvote')}
                disabled={disabled || isLoading}
                className={clsx(
                    'p-1 rounded-md transition-all',
                    votes.user_vote === 'upvote'
                        ? 'text-green-500 bg-green-500/20 shadow-sm'
                        : 'text-gray-400 hover:text-green-500 hover:bg-green-500/10',
                    (disabled || isLoading) && 'opacity-50 cursor-not-allowed'
                )}
                title="Upvote"
                aria-label="Upvote map"
            >
                <ChevronUp className="w-5 h-5" />
            </button>

            <span
                className={clsx(
                    'text-sm font-semibold min-w-[3ch] text-center',
                    votes.score > 0 && 'text-green-500',
                    votes.score < 0 && 'text-red-500',
                    votes.score === 0 && 'text-gray-500'
                )}
                title={`${votes.upvotes} upvotes, ${votes.downvotes} downvotes`}
            >
                {votes.score}
            </span>

            <button
                onClick={() => handleVote('downvote')}
                disabled={disabled || isLoading}
                className={clsx(
                    'p-1 rounded-md transition-all',
                    votes.user_vote === 'downvote'
                        ? 'text-red-500 bg-red-500/20 shadow-sm'
                        : 'text-gray-400 hover:text-red-500 hover:bg-red-500/10',
                    (disabled || isLoading) && 'opacity-50 cursor-not-allowed'
                )}
                title="Downvote"
                aria-label="Downvote map"
            >
                <ChevronDown className="w-5 h-5" />
            </button>
        </div>
    )
}
