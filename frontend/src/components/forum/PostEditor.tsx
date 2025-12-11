/**
 * Post editor component for creating and replying to forum posts.
 */

import { useState } from 'react'
import clsx from 'clsx'
import { useAuthStore } from '@/stores/authStore'
import { Link } from 'react-router-dom'

interface PostEditorProps {
    /** Called when post is submitted */
    onSubmit: (content: string) => Promise<void>
    /** Placeholder text */
    placeholder?: string
    /** Submit button text */
    submitText?: string
    /** Whether the topic is locked */
    isLocked?: boolean
    /** Initial content (for editing) */
    initialContent?: string
    /** Whether to show cancel button */
    showCancel?: boolean
    /** Called when cancel is clicked */
    onCancel?: () => void
    /** Minimum height of textarea */
    minHeight?: number
    /** Auto-focus the textarea */
    autoFocus?: boolean
}

export function PostEditor({
    onSubmit,
    placeholder = 'Write your reply...',
    submitText = 'Post Reply',
    isLocked = false,
    initialContent = '',
    showCancel = false,
    onCancel,
    minHeight = 120,
    autoFocus = false,
}: PostEditorProps) {
    const user = useAuthStore((state) => state.user)
    const [content, setContent] = useState(initialContent)
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!content.trim() || isSubmitting) return

        setIsSubmitting(true)
        setError(null)

        try {
            await onSubmit(content.trim())
            setContent('')
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to post.')
        } finally {
            setIsSubmitting(false)
        }
    }

    // Not logged in
    if (!user) {
        return (
            <div className="card bg-gray-800/50 border border-gray-700 text-center py-8">
                <p className="text-gray-400 mb-4">Log in to reply.</p>
                <Link to="/login" className="btn btn-primary">
                    Log In
                </Link>
            </div>
        )
    }

    // Topic is locked
    if (isLocked) {
        return (
            <div className="card bg-gray-800/50 border border-gray-700 text-center py-8">
                <div className="flex items-center justify-center gap-2 text-gray-400">
                    <svg
                        className="w-5 h-5"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={2}
                    >
                        <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
                        />
                    </svg>
                    <span>This topic is locked. No new replies can be posted.</span>
                </div>
            </div>
        )
    }

    return (
        <form onSubmit={handleSubmit} className="card bg-gray-800/50 border border-gray-700">
            <div className="flex items-start gap-4">
                {/* User avatar */}
                <div className="flex-shrink-0 hidden sm:block">
                    {user.avatar_url ? (
                        <img
                            src={user.avatar_url}
                            alt={user.display_name}
                            className="w-10 h-10 rounded-full"
                        />
                    ) : (
                        <div className="w-10 h-10 rounded-full bg-purple-600 flex items-center justify-center text-white font-medium">
                            {user.display_name?.[0]?.toUpperCase() || '?'}
                        </div>
                    )}
                </div>

                {/* Editor */}
                <div className="flex-1 space-y-3">
                    <textarea
                        value={content}
                        onChange={(e) => setContent(e.target.value)}
                        placeholder={placeholder}
                        autoFocus={autoFocus}
                        className={clsx(
                            'w-full px-4 py-3 bg-gray-900 border border-gray-600 rounded-lg',
                            'text-white placeholder-gray-400',
                            'focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent',
                            'resize-y'
                        )}
                        style={{ minHeight }}
                        disabled={isSubmitting}
                    />

                    {/* Formatting help */}
                    <div className="text-xs text-gray-500">
                        Supports basic formatting: **bold**, *italic*, `code`, [link](url)
                    </div>

                    {/* Error message */}
                    {error && (
                        <div className="text-sm text-red-400 bg-red-500/10 px-3 py-2 rounded">
                            {error}
                        </div>
                    )}

                    {/* Actions */}
                    <div className="flex items-center justify-between">
                        <div className="text-sm text-gray-500">
                            {content.length > 0 && `${content.length} characters`}
                        </div>
                        <div className="flex gap-2">
                            {showCancel && onCancel && (
                                <button
                                    type="button"
                                    onClick={onCancel}
                                    disabled={isSubmitting}
                                    className="btn btn-secondary"
                                >
                                    Cancel
                                </button>
                            )}
                            <button
                                type="submit"
                                disabled={!content.trim() || isSubmitting}
                                className={clsx(
                                    'btn btn-primary',
                                    (!content.trim() || isSubmitting) &&
                                    'opacity-50 cursor-not-allowed'
                                )}
                            >
                                {isSubmitting ? (
                                    <>
                                        <svg
                                            className="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
                                            fill="none"
                                            viewBox="0 0 24 24"
                                        >
                                            <circle
                                                className="opacity-25"
                                                cx="12"
                                                cy="12"
                                                r="10"
                                                stroke="currentColor"
                                                strokeWidth="4"
                                            />
                                            <path
                                                className="opacity-75"
                                                fill="currentColor"
                                                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                                            />
                                        </svg>
                                        Posting...
                                    </>
                                ) : (
                                    submitText
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </form>
    )
}

/**
 * Create topic form with title, content, and optional poll.
 */
interface CreateTopicFormProps {
    forumId: string
    onSubmit: (data: {
        title: string
        content: string
        poll?: {
            title: string
            options: string[]
            maxOptions: number
            allowChange: boolean
            hideResults: boolean
            endsInDays?: number
        }
    }) => Promise<void>
    onCancel?: () => void
}

export function CreateTopicForm({ onSubmit, onCancel }: CreateTopicFormProps) {
    const user = useAuthStore((state) => state.user)
    const [title, setTitle] = useState('')
    const [content, setContent] = useState('')
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [error, setError] = useState<string | null>(null)

    // Poll state
    const [showPoll, setShowPoll] = useState(false)
    const [pollTitle, setPollTitle] = useState('')
    const [pollOptions, setPollOptions] = useState(['', ''])
    const [pollMaxOptions, setPollMaxOptions] = useState(1)
    const [pollAllowChange, setPollAllowChange] = useState(false)
    const [pollHideResults, setPollHideResults] = useState(false)
    const [pollDuration, setPollDuration] = useState<number | undefined>(undefined)

    const addPollOption = () => {
        if (pollOptions.length < 10) {
            setPollOptions([...pollOptions, ''])
        }
    }

    const removePollOption = (index: number) => {
        if (pollOptions.length > 2) {
            setPollOptions(pollOptions.filter((_, i) => i !== index))
        }
    }

    const updatePollOption = (index: number, value: string) => {
        const newOptions = [...pollOptions]
        newOptions[index] = value
        setPollOptions(newOptions)
    }

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!title.trim() || !content.trim() || isSubmitting) return

        setIsSubmitting(true)
        setError(null)

        try {
            const data: Parameters<typeof onSubmit>[0] = {
                title: title.trim(),
                content: content.trim(),
            }

            if (showPoll && pollTitle.trim()) {
                const validOptions = pollOptions.filter((o) => o.trim())
                if (validOptions.length >= 2) {
                    data.poll = {
                        title: pollTitle.trim(),
                        options: validOptions,
                        maxOptions: pollMaxOptions,
                        allowChange: pollAllowChange,
                        hideResults: pollHideResults,
                        endsInDays: pollDuration,
                    }
                }
            }

            await onSubmit(data)
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to create topic.')
        } finally {
            setIsSubmitting(false)
        }
    }

    if (!user) {
        return (
            <div className="card bg-gray-800/50 border border-gray-700 text-center py-8">
                <p className="text-gray-400 mb-4">Log in to create a topic.</p>
                <Link to="/login" className="btn btn-primary">
                    Log In
                </Link>
            </div>
        )
    }

    return (
        <form onSubmit={handleSubmit} className="space-y-6">
            {/* Title */}
            <div>
                <label htmlFor="title" className="block text-sm font-medium text-gray-300 mb-2">
                    Topic Title
                </label>
                <input
                    type="text"
                    id="title"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="Enter a descriptive title..."
                    className="w-full px-4 py-3 bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
                    disabled={isSubmitting}
                    maxLength={200}
                />
                <div className="text-xs text-gray-500 mt-1 text-right">
                    {title.length}/200
                </div>
            </div>

            {/* Content */}
            <div>
                <label htmlFor="content" className="block text-sm font-medium text-gray-300 mb-2">
                    Content
                </label>
                <textarea
                    id="content"
                    value={content}
                    onChange={(e) => setContent(e.target.value)}
                    placeholder="Write your post..."
                    className="w-full h-48 px-4 py-3 bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 resize-y"
                    disabled={isSubmitting}
                />
                <div className="text-xs text-gray-500 mt-1">
                    Supports basic formatting: **bold**, *italic*, `code`, [link](url)
                </div>
            </div>

            {/* Poll toggle */}
            <div>
                <button
                    type="button"
                    onClick={() => setShowPoll(!showPoll)}
                    className="flex items-center gap-2 text-sm text-purple-400 hover:text-purple-300 transition-colors"
                >
                    <svg
                        className={clsx('w-4 h-4 transition-transform', showPoll && 'rotate-90')}
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={2}
                    >
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                    </svg>
                    {showPoll ? 'Remove Poll' : 'Add Poll'}
                </button>

                {/* Poll options */}
                {showPoll && (
                    <div className="mt-4 p-4 bg-gray-800/50 rounded-lg border border-gray-700 space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-300 mb-2">
                                Poll Question
                            </label>
                            <input
                                type="text"
                                value={pollTitle}
                                onChange={(e) => setPollTitle(e.target.value)}
                                placeholder="What would you like to ask?"
                                className="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-300 mb-2">
                                Options
                            </label>
                            <div className="space-y-2">
                                {pollOptions.map((option, index) => (
                                    <div key={index} className="flex items-center gap-2">
                                        <input
                                            type="text"
                                            value={option}
                                            onChange={(e) =>
                                                updatePollOption(index, e.target.value)
                                            }
                                            placeholder={`Option ${index + 1}`}
                                            className="flex-1 px-3 py-2 bg-gray-900 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
                                        />
                                        {pollOptions.length > 2 && (
                                            <button
                                                type="button"
                                                onClick={() => removePollOption(index)}
                                                className="p-2 text-gray-400 hover:text-red-400 transition-colors"
                                            >
                                                <svg
                                                    className="w-4 h-4"
                                                    fill="none"
                                                    viewBox="0 0 24 24"
                                                    stroke="currentColor"
                                                    strokeWidth={2}
                                                >
                                                    <path
                                                        strokeLinecap="round"
                                                        strokeLinejoin="round"
                                                        d="M6 18L18 6M6 6l12 12"
                                                    />
                                                </svg>
                                            </button>
                                        )}
                                    </div>
                                ))}
                            </div>
                            {pollOptions.length < 10 && (
                                <button
                                    type="button"
                                    onClick={addPollOption}
                                    className="mt-2 text-sm text-purple-400 hover:text-purple-300"
                                >
                                    + Add Option
                                </button>
                            )}
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-300 mb-2">
                                    Max selections
                                </label>
                                <select
                                    value={pollMaxOptions}
                                    onChange={(e) =>
                                        setPollMaxOptions(parseInt(e.target.value, 10))
                                    }
                                    className="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                                >
                                    {[1, 2, 3, 4, 5].map((n) => (
                                        <option key={n} value={n}>
                                            {n === 1 ? 'Single choice' : `Up to ${n}`}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-300 mb-2">
                                    Duration
                                </label>
                                <select
                                    value={pollDuration ?? ''}
                                    onChange={(e) =>
                                        setPollDuration(
                                            e.target.value
                                                ? parseInt(e.target.value, 10)
                                                : undefined
                                        )
                                    }
                                    className="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                                >
                                    <option value="">No limit</option>
                                    <option value="1">1 day</option>
                                    <option value="3">3 days</option>
                                    <option value="7">1 week</option>
                                    <option value="14">2 weeks</option>
                                    <option value="30">1 month</option>
                                </select>
                            </div>
                        </div>

                        <div className="flex items-center gap-6">
                            <label className="flex items-center gap-2 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={pollAllowChange}
                                    onChange={(e) => setPollAllowChange(e.target.checked)}
                                    className="w-4 h-4 rounded border-gray-600 bg-gray-900 text-purple-500 focus:ring-purple-500"
                                />
                                <span className="text-sm text-gray-300">
                                    Allow vote changes
                                </span>
                            </label>
                            <label className="flex items-center gap-2 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={pollHideResults}
                                    onChange={(e) => setPollHideResults(e.target.checked)}
                                    className="w-4 h-4 rounded border-gray-600 bg-gray-900 text-purple-500 focus:ring-purple-500"
                                />
                                <span className="text-sm text-gray-300">
                                    Hide results until voted
                                </span>
                            </label>
                        </div>
                    </div>
                )}
            </div>

            {/* Error message */}
            {error && (
                <div className="text-sm text-red-400 bg-red-500/10 px-3 py-2 rounded">
                    {error}
                </div>
            )}

            {/* Actions */}
            <div className="flex justify-end gap-3">
                {onCancel && (
                    <button
                        type="button"
                        onClick={onCancel}
                        disabled={isSubmitting}
                        className="btn btn-secondary"
                    >
                        Cancel
                    </button>
                )}
                <button
                    type="submit"
                    disabled={!title.trim() || !content.trim() || isSubmitting}
                    className={clsx(
                        'btn btn-primary',
                        (!title.trim() || !content.trim() || isSubmitting) &&
                        'opacity-50 cursor-not-allowed'
                    )}
                >
                    {isSubmitting ? 'Creating...' : 'Create Topic'}
                </button>
            </div>
        </form>
    )
}
