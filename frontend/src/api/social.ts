/**
 * API client functions for social features - messaging, blocking, reporting.
 */

import { getAccessToken } from '@/stores/authStore'
import { API_CONFIG } from '@/lib/config'

const API_BASE = API_CONFIG.baseUrl

// =============================================================================
// Types
// =============================================================================

export interface UserPublicProfile {
    id: string
    user_number: number
    display_name: string
    avatar_url: string | null
    karma_score: number
    created_at: string
}

export interface UserSearchResult {
    id: string
    user_number: number
    display_name: string
    avatar_url: string | null
}

export interface UserSearchResponse {
    items: UserSearchResult[]
    total: number
    page: number
    page_size: number
    has_next: boolean
}

export interface DirectMessage {
    id: string
    sender_id: string
    recipient_id: string
    content: string
    read_at: string | null
    created_at: string
}

export interface ConversationSummary {
    partner: UserSearchResult
    last_message: DirectMessage | null
    unread_count: number
}

export interface ConversationListResponse {
    items: ConversationSummary[]
}

export interface MessagesResponse {
    items: DirectMessage[]
    has_more: boolean
}

export interface BlockedUser {
    id: string
    blocked_id: string
    blocked_username: string
    blocked_display_name: string
    reason: string | null
    created_at: string
}

export interface BlockedUsersResponse {
    items: BlockedUser[]
}

export type ReportType =
    | 'spam'
    | 'harassment'
    | 'inappropriate_content'
    | 'cheating'
    | 'impersonation'
    | 'copyright'
    | 'other'

export type ReportStatus = 'pending' | 'under_review' | 'resolved' | 'dismissed'

export interface AdminReport {
    id: string
    reporter: UserSearchResult
    reported_user: UserSearchResult
    report_type: ReportType
    description: string
    status: ReportStatus
    admin_notes: string | null
    reviewed_by: UserSearchResult | null
    created_at: string
    reviewed_at: string | null
}

export interface AdminReportsResponse {
    items: AdminReport[]
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
    requireAuth: boolean = true
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
// User Search & Profiles
// =============================================================================

export interface SearchUsersParams {
    query: string
    page?: number
    pageSize?: number
}

/**
 * Search for users by username.
 */
export async function searchUsers(params: SearchUsersParams): Promise<UserSearchResponse> {
    const searchParams = new URLSearchParams({
        q: params.query,
        page: String(params.page ?? 1),
        page_size: String(params.pageSize ?? 20),
    })
    return request<UserSearchResponse>(`/social/users/search?${searchParams}`)
}

/**
 * Get a user's public profile.
 */
export async function getUserProfile(userId: string): Promise<UserPublicProfile> {
    return request<UserPublicProfile>(`/social/users/${userId}`)
}

// =============================================================================
// Direct Messaging
// =============================================================================

/**
 * Send a direct message to a user.
 */
export async function sendMessage(
    recipientId: string,
    content: string
): Promise<DirectMessage> {
    return request<DirectMessage>('/social/messages', {
        method: 'POST',
        body: JSON.stringify({
            recipient_id: recipientId,
            content,
        }),
    })
}

/**
 * Get list of conversations.
 */
export async function getConversations(params?: {
    page?: number
    pageSize?: number
}): Promise<ConversationListResponse> {
    const searchParams = new URLSearchParams({
        page: String(params?.page ?? 1),
        page_size: String(params?.pageSize ?? 20),
    })
    return request<ConversationListResponse>(`/social/messages/conversations?${searchParams}`)
}

/**
 * Get messages with a specific user.
 */
export async function getMessages(
    partnerId: string,
    params?: { beforeId?: string; limit?: number }
): Promise<MessagesResponse> {
    const searchParams = new URLSearchParams()
    if (params?.beforeId) searchParams.set('before_id', params.beforeId)
    if (params?.limit) searchParams.set('limit', String(params.limit))

    const query = searchParams.toString() ? `?${searchParams}` : ''
    return request<MessagesResponse>(`/social/messages/${partnerId}${query}`)
}

/**
 * Mark messages from a user as read.
 */
export async function markMessagesRead(partnerId: string): Promise<{ marked_count: number }> {
    return request<{ marked_count: number }>(`/social/messages/${partnerId}/read`, {
        method: 'POST',
    })
}

/**
 * Get total unread message count.
 */
export async function getUnreadCount(): Promise<{ count: number }> {
    return request<{ count: number }>('/social/messages/unread/count')
}

// =============================================================================
// User Blocking
// =============================================================================

/**
 * Block a user.
 */
export async function blockUser(
    userId: string,
    reason?: string
): Promise<BlockedUser> {
    return request<BlockedUser>(`/social/users/${userId}/block`, {
        method: 'POST',
        body: JSON.stringify({ reason }),
    })
}

/**
 * Unblock a user.
 */
export async function unblockUser(userId: string): Promise<{ message: string }> {
    return request<{ message: string }>(`/social/users/${userId}/block`, {
        method: 'DELETE',
    })
}

/**
 * Get list of blocked users.
 */
export async function getBlockedUsers(): Promise<BlockedUsersResponse> {
    return request<BlockedUsersResponse>('/social/blocked')
}

// =============================================================================
// User Reporting
// =============================================================================

/**
 * Report a user.
 */
export async function reportUser(
    userId: string,
    reportType: ReportType,
    description: string
): Promise<{ id: string; message: string }> {
    return request<{ id: string; message: string }>(`/social/users/${userId}/report`, {
        method: 'POST',
        body: JSON.stringify({
            report_type: reportType,
            description,
        }),
    })
}

// =============================================================================
// Admin: Reports Management
// =============================================================================

export interface GetReportsParams {
    status?: ReportStatus
    page?: number
    pageSize?: number
}

/**
 * Get user reports (admin only).
 */
export async function getReports(params?: GetReportsParams): Promise<AdminReportsResponse> {
    const searchParams = new URLSearchParams({
        page: String(params?.page ?? 1),
        page_size: String(params?.pageSize ?? 20),
    })
    if (params?.status) searchParams.set('status', params.status)
    return request<AdminReportsResponse>(`/social/admin/reports?${searchParams}`)
}

/**
 * Get a single report (admin only).
 */
export async function getReport(reportId: string): Promise<AdminReport> {
    return request<AdminReport>(`/social/admin/reports/${reportId}`)
}

/**
 * Update a report's status (admin only).
 */
export async function updateReportStatus(
    reportId: string,
    status: ReportStatus,
    adminNotes?: string
): Promise<AdminReport> {
    return request<AdminReport>(`/social/admin/reports/${reportId}`, {
        method: 'PATCH',
        body: JSON.stringify({
            status,
            admin_notes: adminNotes,
        }),
    })
}

// =============================================================================
// User Friendships (osu!-style)
// =============================================================================

export interface FriendResponse {
    id: string
    friend_id: string
    friend_display_name: string
    friend_avatar_url: string | null
    friend_user_number: number
    is_mutual: boolean
    created_at: string
}

export interface FriendsListResponse {
    items: FriendResponse[]
    total: number
}

export interface FriendshipStatusResponse {
    is_following: boolean
    is_followed_by: boolean
    is_mutual: boolean
}

export interface AddFriendResponse {
    id: string
    friend_id: string
    is_mutual: boolean
    message: string
}

/**
 * Add a user as a friend (follow them).
 */
export async function addFriend(userId: string): Promise<AddFriendResponse> {
    return request<AddFriendResponse>(`/social/users/${userId}/friend`, {
        method: 'POST',
    })
}

/**
 * Remove a user from friends (unfollow them).
 */
export async function removeFriend(userId: string): Promise<{ message: string }> {
    return request<{ message: string }>(`/social/users/${userId}/friend`, {
        method: 'DELETE',
    })
}

/**
 * Get list of users you are following.
 */
export async function getFriends(): Promise<FriendsListResponse> {
    return request<FriendsListResponse>('/social/friends')
}

/**
 * Check friendship status with a user.
 */
export async function getFriendshipStatus(userId: string): Promise<FriendshipStatusResponse> {
    return request<FriendshipStatusResponse>(`/social/users/${userId}/friendship`)
}

// =============================================================================
// User Subscriptions (Bell notifications)
// =============================================================================

export interface SubscriptionResponse {
    id: string
    target_user_id: string
    target_user_display_name: string
    target_user_avatar_url: string | null
    target_user_number: number
    notify_on_map_upload: boolean
    notify_on_map_ranked: boolean
    created_at: string
}

export interface SubscriptionsListResponse {
    items: SubscriptionResponse[]
    total: number
}

export interface SubscriptionStatusResponse {
    is_subscribed: boolean
    notify_on_map_upload: boolean
    notify_on_map_ranked: boolean
}

export interface CreateSubscriptionRequest {
    notify_on_map_upload?: boolean
    notify_on_map_ranked?: boolean
}

/**
 * Subscribe to a user's beatmap uploads.
 */
export async function subscribeToUser(
    userId: string,
    options?: CreateSubscriptionRequest
): Promise<{ id: string; target_user_id: string; message: string }> {
    return request<{ id: string; target_user_id: string; message: string }>(
        `/social/users/${userId}/subscribe`,
        {
            method: 'POST',
            body: JSON.stringify(options || {}),
        }
    )
}

/**
 * Unsubscribe from a user's notifications.
 */
export async function unsubscribeFromUser(userId: string): Promise<{ message: string }> {
    return request<{ message: string }>(`/social/users/${userId}/subscribe`, {
        method: 'DELETE',
    })
}

/**
 * Update subscription notification preferences.
 */
export async function updateSubscription(
    userId: string,
    options: { notify_on_map_upload?: boolean; notify_on_map_ranked?: boolean }
): Promise<SubscriptionResponse> {
    return request<SubscriptionResponse>(`/social/users/${userId}/subscribe`, {
        method: 'PATCH',
        body: JSON.stringify(options),
    })
}

/**
 * Get list of users you are subscribed to.
 */
export async function getSubscriptions(): Promise<SubscriptionsListResponse> {
    return request<SubscriptionsListResponse>('/social/subscriptions')
}

/**
 * Check subscription status for a user.
 */
export async function getSubscriptionStatus(userId: string): Promise<SubscriptionStatusResponse> {
    return request<SubscriptionStatusResponse>(`/social/users/${userId}/subscription`)
}
