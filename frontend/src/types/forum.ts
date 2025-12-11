/**
 * Types for the community forum API.
 */

// Enums
export type TopicType = 'normal' | 'sticky' | 'announcement'
export type VoteType = 'upvote' | 'downvote'
export type ModeratorPermission = 'pin' | 'lock' | 'delete' | 'move' | 'ban'

// Base user reference for forum content
export interface ForumUser {
    id: string
    user_number: number
    display_name: string
    avatar_url: string | null
    karma: number
    role: string
    post_count: number
    joined_at: string
}

// Category (top-level grouping)
export interface ForumCategory {
    id: string
    name: string
    description: string | null
    display_order?: number
    position?: number
    icon?: string | null
    color?: string | null
    is_visible?: boolean
    forums: Forum[]
    created_at?: string
    updated_at?: string
}

// Forum (within a category) - matches ForumSummaryResponse from backend
export interface Forum {
    id: string
    category_id?: string
    name: string
    slug?: string
    description: string | null
    icon?: string | null
    color?: string | null
    position?: number
    is_visible: boolean
    allow_topics: boolean
    topic_count: number
    post_count: number
    last_post?: ForumPost | null
    last_post_at?: string | null
    created_at?: string
    updated_at?: string
}

// Topic (thread within a forum)
export interface Topic {
    id: string
    forum_id: string
    user_id: string
    title: string
    topic_type: TopicType
    is_locked: boolean
    is_pinned: boolean
    view_count: number
    post_count: number
    first_post_id: string | null
    last_post_id: string | null
    first_post: ForumPost | null
    last_post: ForumPost | null
    author: ForumUser | null
    poll: TopicPoll | null
    is_watched: boolean
    is_read: boolean
    created_at: string
    updated_at: string
}

// Post (message within a topic)
export interface ForumPost {
    id: string
    topic_id: string
    user_id: string
    content: string
    content_html: string | null
    edit_count: number
    edit_reason: string | null
    edited_by_id: string | null
    is_deleted: boolean
    upvotes: number
    downvotes: number
    score: number
    user_vote: VoteType | null
    author: ForumUser | null
    created_at: string
    updated_at: string
}

// Poll attached to a topic
export interface TopicPoll {
    topic_id: string
    title: string
    options: PollOption[]
    max_options: number
    allow_change: boolean
    hide_results: boolean
    ends_at: string | null
    total_votes: number
    has_voted: boolean
    user_votes: string[] // option IDs the user voted for
    created_at: string
}

// Poll option
export interface PollOption {
    id: string
    poll_topic_id: string
    text: string
    vote_count: number
    position: number
    percentage: number // calculated client-side
}

// User forum statistics
export interface UserForumStats {
    user_id: string
    post_count: number
    topic_count: number
    upvotes_received: number
    downvotes_received: number
    helpful_count: number
}

// Request/Response types

export interface CreateTopicRequest {
    title: string
    content: string
    poll?: CreatePollRequest
}

export interface CreatePollRequest {
    title: string
    options: string[]
    max_options?: number
    allow_change?: boolean
    hide_results?: boolean
    ends_in_days?: number
}

export interface CreatePostRequest {
    content: string
}

export interface EditPostRequest {
    content: string
    edit_reason?: string
}

export interface VoteRequest {
    vote_type: VoteType
}

export interface PollVoteRequest {
    option_ids: string[]
}

// API response types
export interface TopicListResponse {
    items: Topic[]
    total: number
    page: number
    page_size: number
    total_pages: number
    has_next: boolean
    has_prev: boolean
}

export interface PostListResponse {
    items: ForumPost[]
    total: number
    page: number
    page_size: number
    total_pages: number
    has_next: boolean
    has_prev: boolean
}

export interface VoteResponse {
    post_id: string
    upvotes: number
    downvotes: number
    score: number
    user_vote: VoteType | null
}

// Moderation types
export interface ModeratorInfo {
    user_id: string
    forum_id: string
    permissions: ModeratorPermission[]
    appointed_at: string
}

export interface TopicLog {
    id: string
    topic_id: string
    user_id: string
    action: string
    details: string | null
    created_at: string
}

export interface UserForumBan {
    user_id: string
    forum_id: string | null // null = global ban
    reason: string | null
    banned_by_id: string
    expires_at: string | null
    created_at: string
}
