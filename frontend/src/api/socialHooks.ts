/**
 * React Query hooks for social features - messaging, blocking, reporting.
 */

import { useQuery, useMutation, useQueryClient, useInfiniteQuery } from '@tanstack/react-query'
import {
    searchUsers,
    getUserProfile,
    sendMessage,
    getConversations,
    getMessages,
    markMessagesRead,
    getUnreadCount,
    blockUser,
    unblockUser,
    getBlockedUsers,
    reportUser,
    getReports,
    getReport,
    updateReportStatus,
    // Friends
    addFriend,
    removeFriend,
    getFriends,
    getFriendshipStatus,
    // Subscriptions
    subscribeToUser,
    unsubscribeFromUser,
    getSubscriptions,
    getSubscriptionStatus,
    updateSubscription,
    type ReportType,
    type ReportStatus,
    type GetReportsParams,
} from './social'

// Query keys for cache management
export const socialQueryKeys = {
    userSearch: (query: string) => ['social', 'users', 'search', query] as const,
    userProfile: (userId: string) => ['social', 'users', userId] as const,
    conversations: ['social', 'conversations'] as const,
    messages: (partnerId: string) => ['social', 'messages', partnerId] as const,
    unreadCount: ['social', 'unreadCount'] as const,
    blockedUsers: ['social', 'blocked'] as const,
    adminReports: (status?: ReportStatus) => ['social', 'admin', 'reports', status] as const,
    adminReport: (reportId: string) => ['social', 'admin', 'reports', reportId] as const,
    friends: ['social', 'friends'] as const,
    friendshipStatus: (userId: string) => ['social', 'friendship', userId] as const,
    subscriptions: ['social', 'subscriptions'] as const,
    subscriptionStatus: (userId: string) => ['social', 'subscription', userId] as const,
}

// =============================================================================
// User Search & Profiles
// =============================================================================

export function useUserSearch(query: string, enabled = true) {
    return useQuery({
        queryKey: socialQueryKeys.userSearch(query),
        queryFn: () => searchUsers({ query }),
        enabled: enabled && query.length >= 1,
        staleTime: 30000, // 30 seconds
    })
}

export function useUserProfile(userId: string | undefined) {
    return useQuery({
        queryKey: userId ? socialQueryKeys.userProfile(userId) : ['profile-undefined'],
        queryFn: () => (userId ? getUserProfile(userId) : Promise.reject('No user ID')),
        enabled: !!userId,
        staleTime: 60000, // 1 minute
    })
}

// =============================================================================
// Direct Messaging
// =============================================================================

export function useConversations() {
    return useQuery({
        queryKey: socialQueryKeys.conversations,
        queryFn: () => getConversations(),
        staleTime: 30000,
        refetchInterval: 60000, // Poll every minute for new messages
    })
}

export function useMessages(partnerId: string | undefined) {
    return useInfiniteQuery({
        queryKey: partnerId ? socialQueryKeys.messages(partnerId) : ['messages-undefined'],
        queryFn: ({ pageParam }) =>
            partnerId
                ? getMessages(partnerId, { beforeId: pageParam, limit: 50 })
                : Promise.reject('No partner ID'),
        enabled: !!partnerId,
        getNextPageParam: (lastPage) => {
            if (!lastPage.has_more || lastPage.items.length === 0) return undefined
            return lastPage.items[lastPage.items.length - 1].id
        },
        initialPageParam: undefined as string | undefined,
        staleTime: 10000,
        refetchInterval: 15000, // Poll frequently for new messages
    })
}

export function useSendMessage() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ recipientId, content }: { recipientId: string; content: string }) =>
            sendMessage(recipientId, content),
        onSuccess: (_, { recipientId }) => {
            queryClient.invalidateQueries({ queryKey: socialQueryKeys.messages(recipientId) })
            queryClient.invalidateQueries({ queryKey: socialQueryKeys.conversations })
        },
    })
}

export function useMarkMessagesRead() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (partnerId: string) => markMessagesRead(partnerId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: socialQueryKeys.unreadCount })
            queryClient.invalidateQueries({ queryKey: socialQueryKeys.conversations })
        },
    })
}

export function useUnreadCount() {
    return useQuery({
        queryKey: socialQueryKeys.unreadCount,
        queryFn: getUnreadCount,
        staleTime: 30000,
        refetchInterval: 60000, // Poll every minute
    })
}

// =============================================================================
// User Blocking
// =============================================================================

export function useBlockedUsers() {
    return useQuery({
        queryKey: socialQueryKeys.blockedUsers,
        queryFn: getBlockedUsers,
        staleTime: 60000,
    })
}

export function useBlockUser() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({ userId, reason }: { userId: string; reason?: string }) =>
            blockUser(userId, reason),
        onSuccess: (_, { userId }) => {
            queryClient.invalidateQueries({ queryKey: socialQueryKeys.blockedUsers })
            queryClient.invalidateQueries({ queryKey: socialQueryKeys.conversations })
            // Remove cached profile and messages for blocked user
            queryClient.removeQueries({ queryKey: socialQueryKeys.userProfile(userId) })
            queryClient.removeQueries({ queryKey: socialQueryKeys.messages(userId) })
        },
    })
}

export function useUnblockUser() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (userId: string) => unblockUser(userId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: socialQueryKeys.blockedUsers })
        },
    })
}

// =============================================================================
// User Reporting
// =============================================================================

export function useReportUser() {
    return useMutation({
        mutationFn: ({
            userId,
            reportType,
            description,
        }: {
            userId: string
            reportType: ReportType
            description: string
        }) => reportUser(userId, reportType, description),
    })
}

// =============================================================================
// Admin: Reports Management
// =============================================================================

export function useAdminReports(params?: GetReportsParams) {
    return useQuery({
        queryKey: socialQueryKeys.adminReports(params?.status),
        queryFn: () => getReports(params),
        staleTime: 30000,
    })
}

export function useAdminReport(reportId: string | undefined) {
    return useQuery({
        queryKey: reportId ? socialQueryKeys.adminReport(reportId) : ['report-undefined'],
        queryFn: () => (reportId ? getReport(reportId) : Promise.reject('No report ID')),
        enabled: !!reportId,
        staleTime: 30000,
    })
}

export function useUpdateReportStatus() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({
            reportId,
            status,
            adminNotes,
        }: {
            reportId: string
            status: ReportStatus
            adminNotes?: string
        }) => updateReportStatus(reportId, status, adminNotes),
        onSuccess: (updatedReport) => {
            queryClient.invalidateQueries({
                queryKey: socialQueryKeys.adminReports(undefined),
            })
            queryClient.setQueryData(
                socialQueryKeys.adminReport(updatedReport.id),
                updatedReport
            )
        },
    })
}

// =============================================================================
// User Friendships (osu!-style)
// =============================================================================

export function useFriends() {
    return useQuery({
        queryKey: socialQueryKeys.friends,
        queryFn: getFriends,
        staleTime: 60000,
    })
}

export function useFriendshipStatus(userId: string | undefined) {
    return useQuery({
        queryKey: userId ? socialQueryKeys.friendshipStatus(userId) : ['friendship-undefined'],
        queryFn: () => (userId ? getFriendshipStatus(userId) : Promise.reject('No user ID')),
        enabled: !!userId,
        staleTime: 30000,
    })
}

export function useAddFriend() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (userId: string) => addFriend(userId),
        onSuccess: (_, userId) => {
            queryClient.invalidateQueries({ queryKey: socialQueryKeys.friends })
            queryClient.invalidateQueries({ queryKey: socialQueryKeys.friendshipStatus(userId) })
        },
    })
}

export function useRemoveFriend() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (userId: string) => removeFriend(userId),
        onSuccess: (_, userId) => {
            queryClient.invalidateQueries({ queryKey: socialQueryKeys.friends })
            queryClient.invalidateQueries({ queryKey: socialQueryKeys.friendshipStatus(userId) })
        },
    })
}

// =============================================================================
// User Subscriptions (Bell notifications)
// =============================================================================

export function useSubscriptions() {
    return useQuery({
        queryKey: socialQueryKeys.subscriptions,
        queryFn: getSubscriptions,
        staleTime: 60000,
    })
}

export function useSubscriptionStatus(userId: string | undefined) {
    return useQuery({
        queryKey: userId ? socialQueryKeys.subscriptionStatus(userId) : ['subscription-undefined'],
        queryFn: () => (userId ? getSubscriptionStatus(userId) : Promise.reject('No user ID')),
        enabled: !!userId,
        staleTime: 30000,
    })
}

export function useSubscribeToUser() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({
            userId,
            options,
        }: {
            userId: string
            options?: { notify_on_map_upload?: boolean; notify_on_map_ranked?: boolean }
        }) => subscribeToUser(userId, options),
        onSuccess: (_, { userId }) => {
            queryClient.invalidateQueries({ queryKey: socialQueryKeys.subscriptions })
            queryClient.invalidateQueries({ queryKey: socialQueryKeys.subscriptionStatus(userId) })
        },
    })
}

export function useUnsubscribeFromUser() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (userId: string) => unsubscribeFromUser(userId),
        onSuccess: (_, userId) => {
            queryClient.invalidateQueries({ queryKey: socialQueryKeys.subscriptions })
            queryClient.invalidateQueries({ queryKey: socialQueryKeys.subscriptionStatus(userId) })
        },
    })
}

export function useUpdateSubscription() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: ({
            userId,
            options,
        }: {
            userId: string
            options: { notify_on_map_upload?: boolean; notify_on_map_ranked?: boolean }
        }) => updateSubscription(userId, options),
        onSuccess: (_, { userId }) => {
            queryClient.invalidateQueries({ queryKey: socialQueryKeys.subscriptions })
            queryClient.invalidateQueries({ queryKey: socialQueryKeys.subscriptionStatus(userId) })
        },
    })
}
