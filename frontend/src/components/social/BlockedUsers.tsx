/**
 * Blocked Users settings component.
 */

import { useBlockedUsers, useUnblockUser } from '@/api/socialHooks'
import { Avatar } from '@/components/ui/Avatar'
import { Button } from '@/components/ui/Button'

export function BlockedUsersSettings() {
    const { data, isLoading, error } = useBlockedUsers()
    const unblockUser = useUnblockUser()

    const handleUnblock = async (userId: string) => {
        try {
            await unblockUser.mutateAsync(userId)
        } catch (err) {
            console.error('Failed to unblock user:', err)
        }
    }

    if (isLoading) {
        return (
            <div className="space-y-3">
                {[1, 2].map((i) => (
                    <div
                        key={i}
                        className="flex items-center gap-3 p-4 bg-dark-400 rounded-lg animate-pulse"
                    >
                        <div className="w-10 h-10 rounded-full bg-dark-300" />
                        <div className="flex-1">
                            <div className="w-32 h-4 bg-dark-300 rounded mb-2" />
                            <div className="w-20 h-3 bg-dark-300 rounded" />
                        </div>
                    </div>
                ))}
            </div>
        )
    }

    if (error) {
        return (
            <div className="text-center py-8 text-gray-400">
                <p>Unable to load blocked users</p>
            </div>
        )
    }

    if (!data?.items.length) {
        return (
            <div className="text-center py-8 text-gray-400">
                <p className="mb-2">No blocked users</p>
                <p className="text-sm">When you block someone, they'll appear here.</p>
            </div>
        )
    }

    return (
        <div className="space-y-3">
            {data.items.map((block) => (
                <div
                    key={block.id}
                    className="flex items-center gap-3 p-4 bg-dark-400 rounded-lg"
                >
                    <Avatar
                        src={undefined}
                        alt={block.blocked_display_name}
                        size="md"
                    />
                    <div className="flex-1 min-w-0">
                        <div className="font-medium text-white">
                            {block.blocked_display_name}
                        </div>
                        <div className="text-sm text-gray-400">
                            @{block.blocked_username}
                        </div>
                        {block.reason && (
                            <div className="text-xs text-gray-500 mt-1">
                                Reason: {block.reason}
                            </div>
                        )}
                    </div>
                    <div className="text-xs text-gray-500">
                        Blocked {new Date(block.created_at).toLocaleDateString()}
                    </div>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleUnblock(block.blocked_id)}
                        disabled={unblockUser.isPending}
                    >
                        Unblock
                    </Button>
                </div>
            ))}
        </div>
    )
}
