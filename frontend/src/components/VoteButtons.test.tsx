import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { VoteButtons } from './VoteButtons'
import type { VoteCountsResponse } from '@/types/votes'
import * as votesApi from '@/api/votes'

// Mock the API functions
vi.mock('@/api/votes', () => ({
    voteOnMap: vi.fn(),
    removeVote: vi.fn(),
}))

describe('VoteButtons', () => {
    let queryClient: QueryClient

    const defaultVotes: VoteCountsResponse = {
        map_id: 'map-123',
        upvotes: 10,
        downvotes: 2,
        score: 8,
        user_vote: null,
    }

    beforeEach(() => {
        queryClient = new QueryClient({
            defaultOptions: {
                queries: { retry: false },
                mutations: { retry: false },
            },
        })
        vi.clearAllMocks()
    })

    const renderVoteButtons = (props: Partial<Parameters<typeof VoteButtons>[0]> = {}) => {
        return render(
            <QueryClientProvider client={queryClient}>
                <VoteButtons mapId="map-123" initialVotes={defaultVotes} {...props} />
            </QueryClientProvider>
        )
    }

    it('renders upvote and downvote buttons', () => {
        renderVoteButtons()

        expect(screen.getByRole('button', { name: /upvote/i })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /downvote/i })).toBeInTheDocument()
    })

    it('displays the score', () => {
        renderVoteButtons()

        expect(screen.getByText('8')).toBeInTheDocument()
    })

    it('displays positive score in green', () => {
        renderVoteButtons()

        const scoreElement = screen.getByText('8')
        expect(scoreElement).toHaveClass('text-green-500')
    })

    it('displays negative score in red', () => {
        const negativeVotes: VoteCountsResponse = {
            ...defaultVotes,
            score: -3,
        }
        renderVoteButtons({ initialVotes: negativeVotes })

        const scoreElement = screen.getByText('-3')
        expect(scoreElement).toHaveClass('text-red-500')
    })

    it('displays zero score in gray', () => {
        const zeroVotes: VoteCountsResponse = {
            ...defaultVotes,
            score: 0,
        }
        renderVoteButtons({ initialVotes: zeroVotes })

        const scoreElement = screen.getByText('0')
        expect(scoreElement).toHaveClass('text-gray-500')
    })

    it('highlights upvote button when user has upvoted', () => {
        const upvotedVotes: VoteCountsResponse = {
            ...defaultVotes,
            user_vote: 'upvote',
        }
        renderVoteButtons({ initialVotes: upvotedVotes })

        const upvoteBtn = screen.getByRole('button', { name: /upvote/i })
        expect(upvoteBtn).toHaveClass('text-green-500')
    })

    it('highlights downvote button when user has downvoted', () => {
        const downvotedVotes: VoteCountsResponse = {
            ...defaultVotes,
            user_vote: 'downvote',
        }
        renderVoteButtons({ initialVotes: downvotedVotes })

        const downvoteBtn = screen.getByRole('button', { name: /downvote/i })
        expect(downvoteBtn).toHaveClass('text-red-500')
    })

    it('calls voteOnMap when upvote clicked', async () => {
        const newVotes: VoteCountsResponse = {
            ...defaultVotes,
            upvotes: 11,
            score: 9,
            user_vote: 'upvote',
        }
        vi.mocked(votesApi.voteOnMap).mockResolvedValue(newVotes)

        renderVoteButtons()

        const upvoteBtn = screen.getByRole('button', { name: /upvote/i })
        fireEvent.click(upvoteBtn)

        await waitFor(() => {
            expect(votesApi.voteOnMap).toHaveBeenCalledWith('map-123', 'upvote')
        })
    })

    it('calls voteOnMap when downvote clicked', async () => {
        const newVotes: VoteCountsResponse = {
            ...defaultVotes,
            downvotes: 3,
            score: 7,
            user_vote: 'downvote',
        }
        vi.mocked(votesApi.voteOnMap).mockResolvedValue(newVotes)

        renderVoteButtons()

        const downvoteBtn = screen.getByRole('button', { name: /downvote/i })
        fireEvent.click(downvoteBtn)

        await waitFor(() => {
            expect(votesApi.voteOnMap).toHaveBeenCalledWith('map-123', 'downvote')
        })
    })

    it('calls removeVote when clicking same vote again', async () => {
        const upvotedVotes: VoteCountsResponse = {
            ...defaultVotes,
            user_vote: 'upvote',
        }
        const removedVotes: VoteCountsResponse = {
            ...defaultVotes,
            user_vote: null,
        }
        vi.mocked(votesApi.removeVote).mockResolvedValue(removedVotes)

        renderVoteButtons({ initialVotes: upvotedVotes })

        const upvoteBtn = screen.getByRole('button', { name: /upvote/i })
        fireEvent.click(upvoteBtn)

        await waitFor(() => {
            expect(votesApi.removeVote).toHaveBeenCalledWith('map-123')
        })
    })

    it('disables buttons when disabled prop is true', () => {
        renderVoteButtons({ disabled: true })

        const upvoteBtn = screen.getByRole('button', { name: /upvote/i })
        const downvoteBtn = screen.getByRole('button', { name: /downvote/i })

        expect(upvoteBtn).toBeDisabled()
        expect(downvoteBtn).toBeDisabled()
    })

    it('does not call API when disabled', () => {
        renderVoteButtons({ disabled: true })

        const upvoteBtn = screen.getByRole('button', { name: /upvote/i })
        fireEvent.click(upvoteBtn)

        expect(votesApi.voteOnMap).not.toHaveBeenCalled()
    })

    it('calls onVoteChange callback after voting', async () => {
        const onVoteChange = vi.fn()
        const newVotes: VoteCountsResponse = {
            ...defaultVotes,
            upvotes: 11,
            score: 9,
            user_vote: 'upvote',
        }
        vi.mocked(votesApi.voteOnMap).mockResolvedValue(newVotes)

        renderVoteButtons({ onVoteChange })

        const upvoteBtn = screen.getByRole('button', { name: /upvote/i })
        fireEvent.click(upvoteBtn)

        await waitFor(() => {
            expect(onVoteChange).toHaveBeenCalledWith(newVotes)
        })
    })

    describe('compact mode', () => {
        it('renders compact layout', () => {
            const { container } = renderVoteButtons({ compact: true })

            // Compact mode uses flex-row layout
            const wrapper = container.firstChild
            expect(wrapper).toHaveClass('flex')
            expect(wrapper).toHaveClass('items-center')
        })

        it('uses smaller icons in compact mode', () => {
            const { container } = renderVoteButtons({ compact: true })

            const svgs = container.querySelectorAll('svg')
            svgs.forEach((svg) => {
                expect(svg).toHaveClass('w-4')
                expect(svg).toHaveClass('h-4')
            })
        })
    })

    it('initializes with default votes when no initialVotes provided', () => {
        render(
            <QueryClientProvider client={queryClient}>
                <VoteButtons mapId="map-456" />
            </QueryClientProvider>
        )

        // Default score should be 0
        expect(screen.getByText('0')).toBeInTheDocument()
    })

    it('shows tooltip with vote counts on score element', () => {
        renderVoteButtons()

        const scoreElement = screen.getByText('8')
        expect(scoreElement).toHaveAttribute('title', '10 upvotes, 2 downvotes')
    })
})
