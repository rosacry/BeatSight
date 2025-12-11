/**
 * Messages page - Direct messaging between users.
 */

import { useParams, Navigate } from 'react-router-dom'
import { ConversationList, MessageThread, UserSearch } from '@/components/social'
import { useAuthStore } from '@/stores/authStore'
import type { UserSearchResult } from '@/api/social'
import { useNavigate } from 'react-router-dom'

export default function MessagesPage() {
    const { partnerId } = useParams<{ partnerId?: string }>()
    const { isAuthenticated } = useAuthStore()
    const navigate = useNavigate()

    // Redirect to login if not authenticated
    if (!isAuthenticated) {
        return <Navigate to="/login" replace />
    }

    const handleUserSelect = (user: UserSearchResult) => {
        navigate(`/messages/${user.id}`)
    }

    return (
        <div className="min-h-[calc(100vh-4rem)] bg-dark-600">
            <div className="max-w-6xl mx-auto h-[calc(100vh-4rem)] flex">
                {/* Sidebar - Conversations */}
                <div className="w-80 border-r border-white/10 flex flex-col">
                    <div className="p-4 border-b border-white/10">
                        <h1 className="text-xl font-bold text-white mb-4">Messages</h1>
                        <UserSearch
                            onSelect={handleUserSelect}
                            placeholder="Start a new conversation..."
                        />
                    </div>
                    <div className="flex-1 overflow-y-auto p-2">
                        <ConversationList />
                    </div>
                </div>

                {/* Main Content - Message Thread */}
                <div className="flex-1 flex flex-col">
                    {partnerId ? (
                        <MessageThread partnerId={partnerId} />
                    ) : (
                        <div className="flex-1 flex items-center justify-center text-gray-400">
                            <div className="text-center">
                                <svg
                                    className="w-16 h-16 mx-auto mb-4 opacity-50"
                                    fill="none"
                                    viewBox="0 0 24 24"
                                    stroke="currentColor"
                                >
                                    <path
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        strokeWidth={1.5}
                                        d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
                                    />
                                </svg>
                                <p className="text-lg">Select a conversation</p>
                                <p className="text-sm mt-1">
                                    Or search for a user to start a new conversation
                                </p>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
