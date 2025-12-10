/**
 * API client functions for community forums.
 */

import type {
    ForumCategory,
    Forum,
    Topic,
    ForumPost,
    TopicPoll,
    TopicListResponse,
    PostListResponse,
    CreateTopicRequest,
    CreatePostRequest,
    EditPostRequest,
    VoteResponse,
    VoteType,
    UserForumStats,
} from '@/types/forum'
import { getAccessToken } from '@/stores/authStore'
import { API_CONFIG } from '@/lib/config'

const API_BASE = API_CONFIG.baseUrl

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

// ============================================================================
// Categories & Forums
// ============================================================================

/**
 * Get all forum categories with their forums.
 */
export async function getForumCategories(): Promise<ForumCategory[]> {
    return request<ForumCategory[]>('/forum/categories')
}

/**
 * Get a single forum by ID or slug.
 */
export async function getForum(forumIdOrSlug: string): Promise<Forum> {
    return request<Forum>(`/forum/forums/${forumIdOrSlug}`)
}

// ============================================================================
// Topics
// ============================================================================

export interface GetTopicsParams {
    page?: number
    pageSize?: number
    sort?: 'newest' | 'oldest' | 'most_posts' | 'most_views'
}

/**
 * Get topics in a forum.
 */
export async function getForumTopics(
    forumIdOrSlug: string,
    params: GetTopicsParams = {}
): Promise<TopicListResponse> {
    const searchParams = new URLSearchParams()
    if (params.page) searchParams.set('offset', ((params.page - 1) * (params.pageSize || 25)).toString())
    if (params.pageSize) searchParams.set('limit', params.pageSize.toString())
    // Backend uses different sorting - map frontend sort options to backend
    // Backend sorts by: created_at, views, posts (no direction control from API)

    const query = searchParams.toString()
    return request<TopicListResponse>(`/forum/forums/${forumIdOrSlug}/topics${query ? `?${query}` : ''}`)
}

/**
 * Get a single topic by ID.
 */
export async function getTopic(topicId: string): Promise<Topic> {
    return request<Topic>(`/forum/topics/${topicId}`)
}

/**
 * Create a new topic in a forum.
 */
export async function createTopic(
    forumIdOrSlug: string,
    data: CreateTopicRequest
): Promise<Topic> {
    return request<Topic>(
        `/forum/forums/${forumIdOrSlug}/topics`,
        {
            method: 'POST',
            body: JSON.stringify(data),
        },
        true
    )
}

/**
 * Lock a topic (moderator only).
 */
export async function lockTopic(topicId: string): Promise<Topic> {
    return request<Topic>(
        `/forum/topics/${topicId}/lock`,
        { method: 'POST' },
        true
    )
}

/**
 * Unlock a topic (moderator only).
 */
export async function unlockTopic(topicId: string): Promise<Topic> {
    return request<Topic>(
        `/forum/topics/${topicId}/unlock`,
        { method: 'POST' },
        true
    )
}

/**
 * Pin a topic (moderator only).
 */
export async function pinTopic(topicId: string): Promise<Topic> {
    return request<Topic>(
        `/forum/topics/${topicId}/pin`,
        { method: 'POST' },
        true
    )
}

/**
 * Unpin a topic (moderator only).
 */
export async function unpinTopic(topicId: string): Promise<Topic> {
    return request<Topic>(
        `/forum/topics/${topicId}/unpin`,
        { method: 'POST' },
        true
    )
}

/**
 * Watch a topic for notifications.
 */
export async function watchTopic(topicId: string): Promise<void> {
    return request<void>(
        `/forum/topics/${topicId}/watch`,
        { method: 'POST' },
        true
    )
}

/**
 * Unwatch a topic.
 */
export async function unwatchTopic(topicId: string): Promise<void> {
    return request<void>(
        `/forum/topics/${topicId}/watch`,
        { method: 'DELETE' },
        true
    )
}

/**
 * Get recent/latest topics across all forums.
 */
export async function getRecentTopics(
    params: GetTopicsParams = {}
): Promise<TopicListResponse> {
    const searchParams = new URLSearchParams()
    if (params.page) searchParams.set('page', params.page.toString())
    if (params.pageSize) searchParams.set('page_size', params.pageSize.toString())

    const query = searchParams.toString()
    return request<TopicListResponse>(`/forum/topics/recent${query ? `?${query}` : ''}`)
}

// ============================================================================
// Posts
// ============================================================================

export interface GetPostsParams {
    page?: number
    pageSize?: number
}

/**
 * Get posts in a topic.
 */
export async function getTopicPosts(
    topicId: string,
    params: GetPostsParams = {}
): Promise<PostListResponse> {
    const searchParams = new URLSearchParams()
    if (params.page) searchParams.set('page', params.page.toString())
    if (params.pageSize) searchParams.set('page_size', params.pageSize.toString())

    const query = searchParams.toString()
    return request<PostListResponse>(`/forum/topics/${topicId}/posts${query ? `?${query}` : ''}`)
}

/**
 * Get a single post by ID.
 */
export async function getPost(postId: string): Promise<ForumPost> {
    return request<ForumPost>(`/forum/posts/${postId}`)
}

/**
 * Create a new post (reply) in a topic.
 */
export async function createPost(
    topicId: string,
    data: CreatePostRequest
): Promise<ForumPost> {
    return request<ForumPost>(
        `/forum/topics/${topicId}/posts`,
        {
            method: 'POST',
            body: JSON.stringify(data),
        },
        true
    )
}

/**
 * Edit an existing post.
 */
export async function editPost(
    postId: string,
    data: EditPostRequest
): Promise<ForumPost> {
    return request<ForumPost>(
        `/forum/posts/${postId}`,
        {
            method: 'PUT',
            body: JSON.stringify(data),
        },
        true
    )
}

/**
 * Delete a post (soft delete).
 */
export async function deletePost(postId: string): Promise<void> {
    return request<void>(
        `/forum/posts/${postId}`,
        { method: 'DELETE' },
        true
    )
}

// ============================================================================
// Voting
// ============================================================================

/**
 * Vote on a post (upvote or downvote).
 */
export async function voteOnPost(
    postId: string,
    voteType: VoteType
): Promise<VoteResponse> {
    return request<VoteResponse>(
        `/forum/posts/${postId}/vote`,
        {
            method: 'POST',
            body: JSON.stringify({ vote_type: voteType }),
        },
        true
    )
}

/**
 * Remove vote from a post.
 */
export async function removePostVote(postId: string): Promise<VoteResponse> {
    return request<VoteResponse>(
        `/forum/posts/${postId}/vote`,
        { method: 'DELETE' },
        true
    )
}

// ============================================================================
// Polls
// ============================================================================

/**
 * Vote on a poll.
 */
export async function voteOnPoll(
    topicId: string,
    optionIds: string[]
): Promise<TopicPoll> {
    return request<TopicPoll>(
        `/forum/topics/${topicId}/poll/vote`,
        {
            method: 'POST',
            body: JSON.stringify({ option_ids: optionIds }),
        },
        true
    )
}

/**
 * Get poll results (if visible).
 */
export async function getPollResults(topicId: string): Promise<TopicPoll> {
    return request<TopicPoll>(`/forum/topics/${topicId}/poll`)
}

// ============================================================================
// User Stats
// ============================================================================

/**
 * Get a user's forum statistics.
 */
export async function getUserForumStats(userId: string): Promise<UserForumStats> {
    return request<UserForumStats>(`/forum/users/${userId}/stats`)
}

/**
 * Get the current user's forum statistics.
 */
export async function getMyForumStats(): Promise<UserForumStats> {
    return request<UserForumStats>('/forum/me/stats', {}, true)
}

// ============================================================================
// Search
// ============================================================================

export interface SearchParams {
    query: string
    forumId?: string
    page?: number
    pageSize?: number
}

/**
 * Search forum posts and topics.
 */
export async function searchForum(params: SearchParams): Promise<TopicListResponse> {
    const searchParams = new URLSearchParams()
    searchParams.set('q', params.query)
    if (params.forumId) searchParams.set('forum_id', params.forumId)
    if (params.page) searchParams.set('page', params.page.toString())
    if (params.pageSize) searchParams.set('page_size', params.pageSize.toString())

    return request<TopicListResponse>(`/forum/search?${searchParams.toString()}`)
}
