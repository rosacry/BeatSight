/**
 * Global Search API - unified search across users, maps, forum, and docs.
 * Inspired by osu!'s search experience.
 */

import { API_CONFIG } from '@/lib/config'
import { getAccessToken } from '@/stores/authStore'

const API_BASE = API_CONFIG.baseUrl

// =============================================================================
// Types
// =============================================================================

export interface UserSearchItem {
    id: string
    display_name: string
    username: string
    avatar_url: string | null
    karma_score: number
}

export interface MapSearchItem {
    id: string
    song_id: string
    title: string
    artist: string
    creator_name: string
    creator_id: string
    is_verified: boolean
    difficulty_rating: number | null
    cover_url: string | null
}

export interface ForumSearchItem {
    id: string
    title: string
    content_preview: string
    author_name: string
    author_id: string
    forum_name: string
    forum_slug: string
    post_count: number
    created_at: string
}

export interface GlobalSearchResponse {
    query: string
    users: UserSearchItem[]
    users_total: number
    maps: MapSearchItem[]
    maps_total: number
    forum_topics: ForumSearchItem[]
    forum_topics_total: number
}

export interface PaginatedUsersResponse {
    items: UserSearchItem[]
    total: number
    page: number
    page_size: number
    has_next: boolean
}

export interface PaginatedMapsResponse {
    items: MapSearchItem[]
    total: number
    page: number
    page_size: number
    has_next: boolean
}

// =============================================================================
// API Error
// =============================================================================

class APIError extends Error {
    constructor(
        public status: number,
        message: string
    ) {
        super(message)
        this.name = 'APIError'
    }
}

async function request<T>(
    endpoint: string,
    options: RequestInit = {},
    requireAuth: boolean = false
): Promise<T> {
    const url = `${API_BASE}/api${endpoint}`

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

// =============================================================================
// Search API Functions
// =============================================================================

/**
 * Global search across all content types.
 */
export async function globalSearch(
    query: string,
    limit: number = 5
): Promise<GlobalSearchResponse> {
    const params = new URLSearchParams({
        q: query,
        limit: String(limit),
    })
    return request<GlobalSearchResponse>(`/search/global?${params}`)
}

/**
 * Extended user search with pagination.
 */
export async function searchUsersExtended(
    query: string,
    page: number = 1,
    pageSize: number = 20
): Promise<PaginatedUsersResponse> {
    const params = new URLSearchParams({
        q: query,
        page: String(page),
        page_size: String(pageSize),
    })
    return request<PaginatedUsersResponse>(`/search/users?${params}`)
}

/**
 * Extended map search with pagination.
 */
export async function searchMapsExtended(
    query: string,
    verifiedOnly: boolean = false,
    page: number = 1,
    pageSize: number = 20
): Promise<PaginatedMapsResponse> {
    const params = new URLSearchParams({
        q: query,
        page: String(page),
        page_size: String(pageSize),
        verified_only: String(verifiedOnly),
    })
    return request<PaginatedMapsResponse>(`/search/maps?${params}`)
}
