/**
 * Direct Messaging components.
 */

import { useState, useEffect, useRef, useMemo } from 'react'
import { Link, useParams } from 'react-router-dom'
import { clsx } from 'clsx'
import {
    useConversations,
    useMessages,
    useSendMessage,
    useMarkMessagesRead,
    useUnreadCount,
    useUserProfile,
} from '@/api/socialHooks'
import type { ConversationSummary, DirectMessage as DirectMessageType } from '@/api/social'
import { Avatar } from '@/components/ui/Avatar'
import { Button } from '@/components/ui/Button'
import { UsernameLink } from './UserProfile'
import { useAuthStore } from '@/stores/authStore'

// =============================================================================
// Conversation List
// =============================================================================

export function ConversationList() {
    const { data, isLoading } = useConversations()
    const { partnerId } = useParams<{ partnerId?: string }>()

    if (isLoading) {
        return (
            <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                    <div
                        key={i}
                        className="flex items-center gap-3 p-3 rounded-lg bg-dark-400 animate-pulse"
                    >
                        <div className="w-10 h-10 rounded-full bg-dark-300" />
                        <div className="flex-1">
                            <div className="w-24 h-4 bg-dark-300 rounded mb-2" />
                            <div className="w-32 h-3 bg-dark-300 rounded" />
                        </div>
                    </div>
                ))}
            </div>
        )
    }

    if (!data?.items.length) {
        return (
            <div className="text-center py-8 text-gray-400">
                <p className="mb-2">No conversations yet</p>
                <p className="text-sm">Start a conversation by messaging a user!</p>
            </div>
        )
    }

    return (
        <div className="space-y-1">
            {data.items.map((conversation) => (
                <ConversationItem
                    key={conversation.partner.id}
                    conversation={conversation}
                    isActive={partnerId === conversation.partner.id}
                />
            ))}
        </div>
    )
}

interface ConversationItemProps {
    conversation: ConversationSummary
    isActive: boolean
}

function ConversationItem({ conversation, isActive }: ConversationItemProps) {
    const { partner, last_message, unread_count } = conversation

    const timeAgo = last_message
        ? formatTimeAgo(new Date(last_message.created_at))
        : ''

    return (
        <Link
            to={`/messages/${partner.id}`}
            className={clsx(
                'flex items-center gap-3 p-3 rounded-lg transition-colors',
                isActive ? 'bg-primary-500/20' : 'hover:bg-white/5'
            )}
        >
            <Avatar
                src={partner.avatar_url || undefined}
                alt={partner.display_name}
                size="md"
            />
            <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                    <span className="font-medium text-white truncate">
                        {partner.display_name}
                    </span>
                    {timeAgo && (
                        <span className="text-xs text-gray-500 ml-2 flex-shrink-0">
                            {timeAgo}
                        </span>
                    )}
                </div>
                {last_message && (
                    <p className="text-sm text-gray-400 truncate">
                        {last_message.content}
                    </p>
                )}
            </div>
            {unread_count > 0 && (
                <span className="flex-shrink-0 w-5 h-5 rounded-full bg-primary-500 text-white text-xs flex items-center justify-center">
                    {unread_count > 9 ? '9+' : unread_count}
                </span>
            )}
        </Link>
    )
}

// =============================================================================
// Message Thread
// =============================================================================

interface MessageThreadProps {
    partnerId: string
}

export function MessageThread({ partnerId }: MessageThreadProps) {
    const currentUser = useAuthStore((s) => s.user)
    const { data: partner, isLoading: loadingPartner } = useUserProfile(partnerId)
    const {
        data: messagesData,
        isLoading: loadingMessages,
        fetchNextPage,
        hasNextPage,
        isFetchingNextPage,
    } = useMessages(partnerId)
    const sendMessage = useSendMessage()
    const { mutate: markMessagesRead } = useMarkMessagesRead()
    const [newMessage, setNewMessage] = useState('')
    const messagesEndRef = useRef<HTMLDivElement>(null)
    const containerRef = useRef<HTMLDivElement>(null)

    // Flatten messages from all pages
    const messages = useMemo(() => {
        if (!messagesData?.pages) return []
        return messagesData.pages.flatMap((page) => page.items).reverse()
    }, [messagesData])

    // Mark messages as read when viewing
    useEffect(() => {
        if (partnerId && messages.some((m) => m.sender_id === partnerId && !m.read_at)) {
            markMessagesRead(partnerId)
        }
    }, [partnerId, messages, markMessagesRead])

    // Scroll to bottom on new messages
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages.length])

    const handleSend = async () => {
        if (!newMessage.trim()) return

        try {
            await sendMessage.mutateAsync({
                recipientId: partnerId,
                content: newMessage.trim(),
            })
            setNewMessage('')
        } catch (err) {
            console.error('Failed to send message:', err)
        }
    }

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSend()
        }
    }

    // Load more messages when scrolling to top
    const handleScroll = () => {
        if (!containerRef.current || !hasNextPage || isFetchingNextPage) return

        const { scrollTop } = containerRef.current
        if (scrollTop === 0) {
            fetchNextPage()
        }
    }

    if (loadingPartner) {
        return (
            <div className="flex items-center justify-center h-full text-gray-400">
                Loading...
            </div>
        )
    }

    if (!partner) {
        return (
            <div className="flex items-center justify-center h-full text-gray-400">
                Unable to load conversation
            </div>
        )
    }

    return (
        <div className="flex flex-col h-full">
            {/* Header */}
            <div className="flex items-center gap-3 p-4 border-b border-white/10">
                <Avatar
                    src={partner.avatar_url || undefined}
                    alt={partner.display_name}
                    size="md"
                />
                <div>
                    <UsernameLink
                        user={{
                            id: partner.id,
                            user_number: partner.user_number,
                            username: partner.display_name,
                            display_name: partner.display_name,
                        }}
                        className="text-lg font-semibold"
                    />
                    <p className="text-sm text-gray-400">@{partner.display_name}</p>
                </div>
            </div>

            {/* Messages */}
            <div
                ref={containerRef}
                onScroll={handleScroll}
                className="flex-1 overflow-y-auto p-4 space-y-4"
            >
                {isFetchingNextPage && (
                    <div className="text-center py-2">
                        <span className="text-sm text-gray-400">Loading older messages...</span>
                    </div>
                )}

                {loadingMessages && messages.length === 0 && (
                    <div className="flex justify-center py-8">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
                    </div>
                )}

                {!loadingMessages && messages.length === 0 && (
                    <div className="text-center py-8 text-gray-400">
                        <p>No messages yet</p>
                        <p className="text-sm mt-1">Send a message to start the conversation!</p>
                    </div>
                )}

                {messages.map((message) => (
                    <MessageBubble
                        key={message.id}
                        message={message}
                        isOwn={message.sender_id === currentUser?.id}
                    />
                ))}

                <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="p-4 border-t border-white/10">
                <div className="flex gap-2">
                    <textarea
                        value={newMessage}
                        onChange={(e) => setNewMessage(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Type a message..."
                        rows={1}
                        className="flex-1 px-4 py-2 bg-dark-500 border border-white/10 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500 resize-none"
                    />
                    <Button
                        onClick={handleSend}
                        disabled={!newMessage.trim() || sendMessage.isPending}
                    >
                        {sendMessage.isPending ? (
                            <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        ) : (
                            <svg
                                className="w-5 h-5"
                                fill="none"
                                viewBox="0 0 24 24"
                                stroke="currentColor"
                            >
                                <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                                />
                            </svg>
                        )}
                    </Button>
                </div>
            </div>
        </div>
    )
}

// =============================================================================
// Message Bubble
// =============================================================================

interface MessageBubbleProps {
    message: DirectMessageType
    isOwn: boolean
}

function MessageBubble({ message, isOwn }: MessageBubbleProps) {
    return (
        <div className={clsx('flex', isOwn ? 'justify-end' : 'justify-start')}>
            <div
                className={clsx(
                    'max-w-[70%] rounded-2xl px-4 py-2',
                    isOwn
                        ? 'bg-primary-500 text-white rounded-br-md'
                        : 'bg-dark-400 text-white rounded-bl-md'
                )}
            >
                <p className="whitespace-pre-wrap break-words">{message.content}</p>
                <p
                    className={clsx(
                        'text-xs mt-1',
                        isOwn ? 'text-white/70' : 'text-gray-500'
                    )}
                >
                    {formatTime(new Date(message.created_at))}
                    {isOwn && message.read_at && (
                        <span className="ml-2">✓</span>
                    )}
                </p>
            </div>
        </div>
    )
}

// =============================================================================
// Unread Badge (for navigation)
// =============================================================================

export function UnreadMessagesBadge() {
    const { data } = useUnreadCount()

    if (!data?.count) return null

    return (
        <span className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-red-500 text-white text-xs flex items-center justify-center">
            {data.count > 9 ? '9+' : data.count}
        </span>
    )
}

// =============================================================================
// Helpers
// =============================================================================

function formatTime(date: Date): string {
    return date.toLocaleTimeString('en-US', {
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
    })
}

function formatTimeAgo(date: Date): string {
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return 'now'
    if (diffMins < 60) return `${diffMins}m`
    if (diffHours < 24) return `${diffHours}h`
    if (diffDays < 7) return `${diffDays}d`

    return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
    })
}
