/**
 * Types for the map voting API.
 */

export type VoteAction = 'upvote' | 'downvote'
export type UserVote = 'upvote' | 'downvote' | null

export interface VoteCountsResponse {
    map_id: string
    upvotes: number
    downvotes: number
    score: number
    user_vote: UserVote
}

export interface BulkVoteResponse {
    votes: Record<string, VoteCountsResponse>
}
