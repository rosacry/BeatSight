/**
 * API client functions for map voting.
 */

import type { VoteAction, VoteCountsResponse, BulkVoteResponse } from '@/types/votes'
import { getAccessToken } from '@/stores/authStore'

const API_BASE = '/api'

class APIError extends Error {
    constructor(public status: number, message: string) {
        super(message)
        this.name = 'APIError'
    }
}

async function request<T>(
    endpoint: string,
    options: RequestInit = {},
    requireAuth: boolean = false
): Promise<T> {
    const url = `${API_BASE}${endpoint}`

    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
    }

    const token = getAccessToken()
    if (token) {
        headers['Authorization'] = `Bearer ${token}`
    } else if (requireAuth) {
        throw new APIError(401, 'Authentication required')
    }

    const response = await fetch(url, {
        ...options,
        headers: {
            ...headers,
            ...options.headers,
        },
    })

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
        throw new APIError(response.status, error.detail || 'Request failed')
    }

    return response.json()
}

/**
 * Get vote counts for a single map.
 */
export async function getMapVotes(mapId: string): Promise<VoteCountsResponse> {
    return request<VoteCountsResponse>(`/maps/${mapId}/votes`)
}

/**
 * Cast a vote on a map.
 */
export async function voteOnMap(
    mapId: string,
    action: VoteAction
): Promise<VoteCountsResponse> {
    return request<VoteCountsResponse>(
        `/maps/${mapId}/vote`,
        {
            method: 'POST',
            body: JSON.stringify({ action }),
        },
        true
    )
}

/**
 * Remove a vote from a map.
 */
export async function removeVote(mapId: string): Promise<VoteCountsResponse> {
    return request<VoteCountsResponse>(
        `/maps/${mapId}/vote`,
        { method: 'DELETE' },
        true
    )
}

/**
 * Get vote counts for multiple maps at once.
 */
export async function getBulkVotes(mapIds: string[]): Promise<BulkVoteResponse> {
    return request<BulkVoteResponse>('/maps/votes/bulk', {
        method: 'POST',
        body: JSON.stringify({ map_ids: mapIds }),
    })
}
