/**
 * User Profile components for social features.
 */

import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { clsx } from 'clsx'
import {
    useUserProfile,
    useBlockUser,
    useUnblockUser,
    useReportUser,
    useUserSearch,
} from '@/api/socialHooks'
import type { UserSearchResult, ReportType } from '@/api/social'
import { Avatar } from '@/components/ui/Avatar'
import { Button } from '@/components/ui/Button'
import { Modal, ModalHeader, ModalBody, ModalFooter } from '@/components/ui/Modal'
import { useAuthStore } from '@/stores/authStore'

// Icons
const MessageIcon = () => (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
        />
    </svg>
)

const BlockIcon = () => (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"
        />
    </svg>
)

const FlagIcon = () => (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M3 21v-4m0 0V5a2 2 0 012-2h6.5l1 1H21l-3 6 3 6h-8.5l-1-1H5a2 2 0 00-2 2zm9-13.5V9"
        />
    </svg>
)

const KarmaIcon = () => (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"
        />
    </svg>
)

// =============================================================================
// Clickable Username Link
// =============================================================================

interface UsernameLinkProps {
    user: UserSearchResult | { id: string; username: string; display_name?: string }
    showPopover?: boolean
    className?: string
    children?: ReactNode
}

export function UsernameLink({ user, showPopover = true, className, children }: UsernameLinkProps) {
    const [showProfileCard, setShowProfileCard] = useState(false)
    const currentUser = useAuthStore((s) => s.user)
    const isOwnProfile = currentUser?.id === user.id

    const displayName = 'display_name' in user ? user.display_name : user.username

    if (isOwnProfile) {
        // Don't show popover for own profile, just link to settings
        return (
            <Link
                to="/settings"
                className={clsx(
                    'font-medium text-primary-400 hover:text-primary-300 hover:underline cursor-pointer',
                    className
                )}
            >
                {children || displayName}
            </Link>
        )
    }

    // Link to the user's public profile page
    return (
        <>
            <Link
                to={`/user/${user.id}`}
                onClick={(e) => {
                    // If holding Ctrl/Cmd, let it open in new tab
                    // Otherwise, show the quick preview modal for convenience
                    if (!e.ctrlKey && !e.metaKey && showPopover) {
                        e.preventDefault()
                        setShowProfileCard(true)
                    }
                }}
                className={clsx(
                    'font-medium text-primary-400 hover:text-primary-300 hover:underline cursor-pointer',
                    className
                )}
            >
                {children || displayName}
            </Link>
            {showPopover && (
                <UserProfileModal
                    userId={user.id}
                    open={showProfileCard}
                    onClose={() => setShowProfileCard(false)}
                />
            )}
        </>
    )
}

// =============================================================================
// User Profile Modal
// =============================================================================

interface UserProfileModalProps {
    userId: string
    open: boolean
    onClose: () => void
}

export function UserProfileModal({ userId, open, onClose }: UserProfileModalProps) {
    const { data: profile, isLoading, error } = useUserProfile(userId)
    const blockUser = useBlockUser()
    const unblockUser = useUnblockUser()
    const [showReportModal, setShowReportModal] = useState(false)
    const [isBlocked, setIsBlocked] = useState(false)

    const handleBlock = async () => {
        try {
            await blockUser.mutateAsync({ userId })
            setIsBlocked(true)
        } catch (err) {
            console.error('Failed to block user:', err)
        }
    }

    const handleUnblock = async () => {
        try {
            await unblockUser.mutateAsync(userId)
            setIsBlocked(false)
        } catch (err) {
            console.error('Failed to unblock user:', err)
        }
    }

    if (!open) return null

    return (
        <>
            <Modal open={open} onClose={onClose} size="sm">
                <ModalHeader title="User Profile" />
                <ModalBody>
                    {isLoading && (
                        <div className="flex justify-center py-8">
                            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
                        </div>
                    )}

                    {error && (
                        <div className="text-center py-8 text-gray-400">
                            <p>Unable to load profile</p>
                            <p className="text-sm mt-1">This user may not exist or has blocked you.</p>
                        </div>
                    )}

                    {profile && (
                        <div className="space-y-4">
                            {/* User Info */}
                            <div className="flex items-center gap-4">
                                <Avatar
                                    src={profile.avatar_url || undefined}
                                    alt={profile.display_name}
                                    size="lg"
                                />
                                <div>
                                    <h3 className="text-lg font-semibold text-white">
                                        {profile.display_name}
                                    </h3>
                                    <p className="text-sm text-gray-400">@{profile.username}</p>
                                </div>
                            </div>

                            {/* Stats */}
                            <div className="flex items-center gap-6 py-3 border-y border-white/10">
                                <div className="flex items-center gap-2 text-yellow-500">
                                    <KarmaIcon />
                                    <span className="font-medium">{profile.karma_score}</span>
                                    <span className="text-sm text-gray-400">karma</span>
                                </div>
                                <div className="text-sm text-gray-400">
                                    Joined{' '}
                                    {new Date(profile.created_at).toLocaleDateString('en-US', {
                                        month: 'short',
                                        year: 'numeric',
                                    })}
                                </div>
                            </div>

                            {/* Actions */}
                            <div className="flex flex-wrap gap-2">
                                <Link to={`/user/${userId}`} onClick={onClose}>
                                    <Button variant="primary" size="sm">
                                        View Full Profile
                                    </Button>
                                </Link>

                                <Link to={`/messages/${userId}`}>
                                    <Button variant="outline" size="sm">
                                        <MessageIcon />
                                        <span className="ml-1">Message</span>
                                    </Button>
                                </Link>

                                {isBlocked ? (
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={handleUnblock}
                                        disabled={unblockUser.isPending}
                                    >
                                        <BlockIcon />
                                        <span className="ml-1">Unblock</span>
                                    </Button>
                                ) : (
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={handleBlock}
                                        disabled={blockUser.isPending}
                                        className="hover:text-red-400 hover:border-red-400/50"
                                    >
                                        <BlockIcon />
                                        <span className="ml-1">Block</span>
                                    </Button>
                                )}

                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => setShowReportModal(true)}
                                    className="hover:text-red-400 hover:border-red-400/50"
                                >
                                    <FlagIcon />
                                    <span className="ml-1">Report</span>
                                </Button>
                            </div>
                        </div>
                    )}
                </ModalBody>
            </Modal>

            <ReportUserModal
                userId={userId}
                username={profile?.username || 'User'}
                open={showReportModal}
                onClose={() => setShowReportModal(false)}
            />
        </>
    )
}

// =============================================================================
// Report User Modal
// =============================================================================

interface ReportUserModalProps {
    userId: string
    username: string
    open: boolean
    onClose: () => void
}

const REPORT_TYPES: { value: ReportType; label: string; description: string }[] = [
    { value: 'spam', label: 'Spam', description: 'Repetitive or unwanted content' },
    { value: 'harassment', label: 'Harassment', description: 'Bullying or threatening behavior' },
    {
        value: 'inappropriate_content',
        label: 'Inappropriate Content',
        description: 'Offensive or inappropriate material',
    },
    { value: 'cheating', label: 'Cheating', description: 'Exploiting or gaming the system' },
    { value: 'impersonation', label: 'Impersonation', description: 'Pretending to be someone else' },
    { value: 'copyright', label: 'Copyright', description: 'Unauthorized use of copyrighted material' },
    { value: 'other', label: 'Other', description: 'Something else not listed above' },
]

export function ReportUserModal({ userId, username, open, onClose }: ReportUserModalProps) {
    const [reportType, setReportType] = useState<ReportType>('other')
    const [description, setDescription] = useState('')
    const [submitted, setSubmitted] = useState(false)
    const reportUser = useReportUser()

    const handleSubmit = async () => {
        if (description.length < 10) return

        try {
            await reportUser.mutateAsync({ userId, reportType, description })
            setSubmitted(true)
        } catch (err) {
            console.error('Failed to submit report:', err)
        }
    }

    const handleClose = () => {
        setReportType('other')
        setDescription('')
        setSubmitted(false)
        onClose()
    }

    if (!open) return null

    return (
        <Modal open={open} onClose={handleClose} size="md">
            <ModalHeader title={`Report @${username}`} />
            <ModalBody>
                {submitted ? (
                    <div className="text-center py-6">
                        <div className="w-12 h-12 rounded-full bg-green-500/20 flex items-center justify-center mx-auto mb-4">
                            <svg
                                className="w-6 h-6 text-green-500"
                                fill="none"
                                viewBox="0 0 24 24"
                                stroke="currentColor"
                            >
                                <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M5 13l4 4L19 7"
                                />
                            </svg>
                        </div>
                        <h3 className="text-lg font-medium text-white mb-2">Report Submitted</h3>
                        <p className="text-gray-400">
                            Thank you for your report. Our team will review it.
                        </p>
                    </div>
                ) : (
                    <div className="space-y-4">
                        <p className="text-sm text-gray-400">
                            Please select the reason for reporting this user and provide details.
                        </p>

                        {/* Report Type Selection */}
                        <div className="space-y-2">
                            <label className="block text-sm font-medium text-gray-300">
                                Reason for Report
                            </label>
                            <div className="grid gap-2">
                                {REPORT_TYPES.map((type) => (
                                    <label
                                        key={type.value}
                                        className={clsx(
                                            'flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors',
                                            reportType === type.value
                                                ? 'border-primary-500 bg-primary-500/10'
                                                : 'border-white/10 hover:border-white/20'
                                        )}
                                    >
                                        <input
                                            type="radio"
                                            name="reportType"
                                            value={type.value}
                                            checked={reportType === type.value}
                                            onChange={(e) =>
                                                setReportType(e.target.value as ReportType)
                                            }
                                            className="mt-1"
                                        />
                                        <div>
                                            <div className="font-medium text-white">{type.label}</div>
                                            <div className="text-sm text-gray-400">
                                                {type.description}
                                            </div>
                                        </div>
                                    </label>
                                ))}
                            </div>
                        </div>

                        {/* Description */}
                        <div className="space-y-2">
                            <label className="block text-sm font-medium text-gray-300">
                                Description <span className="text-red-400">*</span>
                            </label>
                            <textarea
                                value={description}
                                onChange={(e) => setDescription(e.target.value)}
                                placeholder="Please describe the issue in detail (minimum 10 characters)..."
                                rows={4}
                                className="w-full px-3 py-2 bg-dark-500 border border-white/10 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500 resize-none"
                            />
                            <p className="text-xs text-gray-500">{description.length}/2000</p>
                        </div>
                    </div>
                )}
            </ModalBody>
            {!submitted && (
                <ModalFooter>
                    <Button variant="ghost" onClick={handleClose}>
                        Cancel
                    </Button>
                    <Button
                        variant="danger"
                        onClick={handleSubmit}
                        disabled={description.length < 10 || reportUser.isPending}
                    >
                        {reportUser.isPending ? 'Submitting...' : 'Submit Report'}
                    </Button>
                </ModalFooter>
            )}
        </Modal>
    )
}

// =============================================================================
// User Search Component
// =============================================================================

interface UserSearchProps {
    onSelect?: (user: UserSearchResult) => void
    placeholder?: string
    className?: string
}

export function UserSearch({ onSelect, placeholder = 'Search users...', className }: UserSearchProps) {
    const [query, setQuery] = useState('')
    const [showResults, setShowResults] = useState(false)
    const { data, isLoading } = useUserSearch(query, query.length >= 1)

    const handleSelect = (user: UserSearchResult) => {
        onSelect?.(user)
        setQuery('')
        setShowResults(false)
    }

    return (
        <div className={clsx('relative', className)}>
            <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onFocus={() => setShowResults(true)}
                onBlur={() => setTimeout(() => setShowResults(false), 200)}
                placeholder={placeholder}
                className="w-full px-4 py-2 bg-dark-500 border border-white/10 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500"
            />

            {showResults && query.length >= 1 && (
                <div className="absolute top-full left-0 right-0 mt-2 bg-dark-400 border border-white/10 rounded-lg shadow-xl max-h-64 overflow-auto z-50">
                    {isLoading && (
                        <div className="p-4 text-center text-gray-400">Searching...</div>
                    )}

                    {!isLoading && data?.items.length === 0 && (
                        <div className="p-4 text-center text-gray-400">No users found</div>
                    )}

                    {!isLoading &&
                        data?.items.map((user) => (
                            <button
                                key={user.id}
                                onClick={() => handleSelect(user)}
                                className="w-full flex items-center gap-3 p-3 hover:bg-white/5 transition-colors text-left"
                            >
                                <Avatar
                                    src={user.avatar_url || undefined}
                                    alt={user.display_name}
                                    size="sm"
                                />
                                <div>
                                    <div className="font-medium text-white">
                                        {user.display_name}
                                    </div>
                                    <div className="text-sm text-gray-400">@{user.username}</div>
                                </div>
                            </button>
                        ))}
                </div>
            )}
        </div>
    )
}
