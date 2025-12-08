/**
 * Poll component for forum topic polls.
 *
 * Displays poll options, handles voting, and shows results.
 */

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { voteOnPoll } from '@/api/forum'
import type { TopicPoll, PollOption } from '@/types/forum'
import { useAuthStore } from '@/stores/authStore'
import { format, isPast } from 'date-fns'

interface ForumPollProps {
    poll: TopicPoll
    topicId: string
    /** Whether the topic is locked */
    isLocked?: boolean
}

export function ForumPoll({ poll, topicId, isLocked = false }: ForumPollProps) {
    const queryClient = useQueryClient()
    const user = useAuthStore((state) => state.user)

    const [selectedOptions, setSelectedOptions] = useState<Set<string>>(
        new Set(poll.user_votes || [])
    )
    const [showResults, setShowResults] = useState(poll.has_voted || !poll.hide_results)

    const isExpired = poll.ends_at ? isPast(new Date(poll.ends_at)) : false
    const canVote = user && !poll.has_voted && !isExpired && !isLocked
    const canChangeVote = user && poll.has_voted && poll.allow_change && !isExpired && !isLocked

    const voteMutation = useMutation({
        mutationFn: async (optionIds: string[]) => {
            return voteOnPoll(topicId, optionIds)
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['topic', topicId] })
            setShowResults(true)
        },
    })

    const handleOptionToggle = (optionId: string) => {
        if (!canVote && !canChangeVote) return

        setSelectedOptions((prev) => {
            const next = new Set(prev)
            if (next.has(optionId)) {
                next.delete(optionId)
            } else {
                // If single choice (max_options = 1), clear others first
                if (poll.max_options === 1) {
                    next.clear()
                }
                // Check if we can add more
                if (next.size < poll.max_options) {
                    next.add(optionId)
                }
            }
            return next
        })
    }

    const handleVote = () => {
        if (selectedOptions.size === 0) return
        voteMutation.mutate(Array.from(selectedOptions))
    }

    const getPercentage = (option: PollOption): number => {
        if (poll.total_votes === 0) return 0
        return Math.round((option.vote_count / poll.total_votes) * 100)
    }

    return (
        <div className="card bg-gray-800/50 border border-gray-700">
            {/* Poll Header */}
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-white">{poll.title}</h3>
                {poll.ends_at && (
                    <span
                        className={clsx(
                            'text-xs px-2 py-1 rounded',
                            isExpired
                                ? 'bg-red-500/20 text-red-400'
                                : 'bg-blue-500/20 text-blue-400'
                        )}
                    >
                        {isExpired
                            ? 'Poll ended'
                            : `Ends ${format(new Date(poll.ends_at), 'MMM d, yyyy')}`}
                    </span>
                )}
            </div>

            {/* Poll Options */}
            <div className="space-y-2">
                {poll.options.map((option) => {
                    const isSelected = selectedOptions.has(option.id)
                    const percentage = getPercentage(option)
                    const isWinning =
                        showResults &&
                        option.vote_count ===
                        Math.max(...poll.options.map((o) => o.vote_count)) &&
                        option.vote_count > 0

                    return (
                        <div key={option.id} className="relative">
                            {/* Result bar (shown behind the option) */}
                            {showResults && (
                                <div
                                    className={clsx(
                                        'absolute inset-0 rounded transition-all',
                                        isWinning ? 'bg-purple-500/30' : 'bg-gray-600/30'
                                    )}
                                    style={{ width: `${percentage}%` }}
                                />
                            )}

                            <button
                                onClick={() => handleOptionToggle(option.id)}
                                disabled={!canVote && !canChangeVote}
                                className={clsx(
                                    'relative w-full flex items-center justify-between px-4 py-3 rounded border transition-all',
                                    isSelected
                                        ? 'border-purple-500 bg-purple-500/10'
                                        : 'border-gray-600 hover:border-gray-500',
                                    (!canVote && !canChangeVote) && 'cursor-default'
                                )}
                            >
                                <div className="flex items-center gap-3">
                                    {/* Checkbox/Radio indicator */}
                                    {(canVote || canChangeVote) && (
                                        <div
                                            className={clsx(
                                                'w-5 h-5 border-2 flex items-center justify-center transition-colors',
                                                poll.max_options === 1
                                                    ? 'rounded-full'
                                                    : 'rounded',
                                                isSelected
                                                    ? 'border-purple-500 bg-purple-500'
                                                    : 'border-gray-500'
                                            )}
                                        >
                                            {isSelected && (
                                                <svg
                                                    className="w-3 h-3 text-white"
                                                    fill="currentColor"
                                                    viewBox="0 0 20 20"
                                                >
                                                    <path
                                                        fillRule="evenodd"
                                                        d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                                                        clipRule="evenodd"
                                                    />
                                                </svg>
                                            )}
                                        </div>
                                    )}
                                    <span className="text-white">{option.text}</span>
                                </div>

                                {showResults && (
                                    <div className="flex items-center gap-2 text-sm">
                                        <span className="text-gray-400">
                                            {option.vote_count} vote
                                            {option.vote_count !== 1 ? 's' : ''}
                                        </span>
                                        <span
                                            className={clsx(
                                                'font-medium',
                                                isWinning ? 'text-purple-400' : 'text-gray-300'
                                            )}
                                        >
                                            {percentage}%
                                        </span>
                                    </div>
                                )}
                            </button>
                        </div>
                    )
                })}
            </div>

            {/* Poll Footer */}
            <div className="mt-4 flex items-center justify-between">
                <div className="text-sm text-gray-400">
                    {poll.total_votes} total vote{poll.total_votes !== 1 ? 's' : ''}
                    {poll.max_options > 1 && (
                        <span className="ml-2">
                            (Select up to {poll.max_options} option
                            {poll.max_options !== 1 ? 's' : ''})
                        </span>
                    )}
                </div>

                <div className="flex items-center gap-2">
                    {/* Toggle results visibility */}
                    {!poll.has_voted && poll.hide_results && !isExpired && (
                        <button
                            onClick={() => setShowResults(!showResults)}
                            className="text-sm text-gray-400 hover:text-white transition-colors"
                        >
                            {showResults ? 'Hide results' : 'Show results'}
                        </button>
                    )}

                    {/* Vote button */}
                    {(canVote || canChangeVote) && (
                        <button
                            onClick={handleVote}
                            disabled={
                                selectedOptions.size === 0 || voteMutation.isPending
                            }
                            className={clsx(
                                'btn btn-primary text-sm',
                                (selectedOptions.size === 0 || voteMutation.isPending) &&
                                'opacity-50 cursor-not-allowed'
                            )}
                        >
                            {voteMutation.isPending
                                ? 'Voting...'
                                : canChangeVote
                                    ? 'Change Vote'
                                    : 'Vote'}
                        </button>
                    )}
                </div>
            </div>

            {/* User's vote indicator */}
            {poll.has_voted && !canChangeVote && (
                <div className="mt-2 text-sm text-green-400">✓ You have voted</div>
            )}
        </div>
    )
}
