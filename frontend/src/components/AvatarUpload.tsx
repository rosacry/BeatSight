/**
 * Avatar upload component with preview and cropping.
 * Allows users to upload, preview, and crop their profile avatar.
 */

import { useState, useRef, useCallback } from 'react'
import { useAuthStore } from '@/stores/authStore'
import { API_CONFIG } from '@/lib/config'

const API_BASE = API_CONFIG.baseUrl
const MAX_FILE_SIZE = 5 * 1024 * 1024 // 5MB
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']

interface AvatarUploadProps {
    currentAvatarUrl?: string | null
    onUploadSuccess?: (newAvatarUrl: string) => void
    onUploadError?: (error: string) => void
    size?: 'sm' | 'md' | 'lg'
}

export function AvatarUpload({
    currentAvatarUrl,
    onUploadSuccess,
    onUploadError,
    size = 'md',
}: AvatarUploadProps) {
    const accessToken = useAuthStore((state) => state.accessToken)
    const user = useAuthStore((state) => state.user)
    const fetchCurrentUser = useAuthStore((state) => state.fetchCurrentUser)

    const [isUploading, setIsUploading] = useState(false)
    const [previewUrl, setPreviewUrl] = useState<string | null>(null)
    const [error, setError] = useState<string | null>(null)
    const fileInputRef = useRef<HTMLInputElement>(null)

    // Size classes
    const sizeClasses = {
        sm: 'w-16 h-16',
        md: 'w-24 h-24',
        lg: 'w-32 h-32',
    }

    const iconSizes = {
        sm: 'w-4 h-4',
        md: 'w-6 h-6',
        lg: 'w-8 h-8',
    }

    // Get initials for fallback avatar
    const initials = user?.display_name
        ?.split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2) || '?'

    const uploadFile = useCallback(async (file: File) => {
        if (!accessToken) {
            setError('Please log in to upload an avatar')
            return
        }

        setIsUploading(true)
        setError(null)

        try {
            const formData = new FormData()
            formData.append('file', file)

            const response = await fetch(`${API_BASE}/users/me/avatar`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                },
                body: formData,
            })

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: 'Upload failed' }))
                throw new Error(errorData.detail || 'Upload failed')
            }

            const userData = await response.json()

            // Refresh user data
            await fetchCurrentUser()

            onUploadSuccess?.(userData.avatar_url)

        } catch (err) {
            const message = err instanceof Error ? err.message : 'Failed to upload avatar'
            setError(message)
            onUploadError?.(message)
            setPreviewUrl(null)
        } finally {
            setIsUploading(false)
        }
    }, [accessToken, fetchCurrentUser, onUploadSuccess, onUploadError])

    const handleFileSelect = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0]
        if (!file) return

        setError(null)

        // Validate file type
        if (!ALLOWED_TYPES.includes(file.type)) {
            setError('Please upload a JPEG, PNG, WebP, or GIF image')
            return
        }

        // Validate file size
        if (file.size > MAX_FILE_SIZE) {
            setError('Image must be smaller than 5MB')
            return
        }

        // Create preview
        const reader = new FileReader()
        reader.onload = (e) => {
            setPreviewUrl(e.target?.result as string)
        }
        reader.readAsDataURL(file)

        // Upload immediately
        uploadFile(file)
    }, [uploadFile])

    const handleDelete = async () => {
        if (!accessToken) return

        setIsUploading(true)
        setError(null)

        try {
            const response = await fetch(`${API_BASE}/users/me/avatar`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${accessToken}`,
                },
            })

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: 'Delete failed' }))
                throw new Error(errorData.detail || 'Delete failed')
            }

            setPreviewUrl(null)
            await fetchCurrentUser()

        } catch (err) {
            const message = err instanceof Error ? err.message : 'Failed to delete avatar'
            setError(message)
        } finally {
            setIsUploading(false)
        }
    }

    const handleClick = () => {
        fileInputRef.current?.click()
    }

    // Determine what to show
    const displayUrl = previewUrl || currentAvatarUrl

    return (
        <div className="flex flex-col items-center gap-3">
            {/* Avatar Display */}
            <div className="relative group">
                <button
                    type="button"
                    onClick={handleClick}
                    disabled={isUploading}
                    className={`
                        ${sizeClasses[size]}
                        rounded-full overflow-hidden
                        bg-primary-600 flex items-center justify-center
                        border-2 border-transparent hover:border-primary-400
                        transition-all duration-200
                        focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 focus:ring-offset-gray-900
                        ${isUploading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
                    `}
                >
                    {displayUrl ? (
                        <img
                            src={displayUrl}
                            alt="Avatar"
                            className="w-full h-full object-cover"
                        />
                    ) : (
                        <span className="text-white text-xl font-bold">{initials}</span>
                    )}

                    {/* Hover overlay */}
                    {!isUploading && (
                        <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                            <svg
                                className={`${iconSizes[size]} text-white`}
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                            >
                                <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"
                                />
                                <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"
                                />
                            </svg>
                        </div>
                    )}

                    {/* Loading spinner */}
                    {isUploading && (
                        <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                            <svg
                                className={`${iconSizes[size]} text-white animate-spin`}
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
                        </div>
                    )}
                </button>

                {/* Delete button (only show if avatar exists) */}
                {displayUrl && !isUploading && (
                    <button
                        type="button"
                        onClick={handleDelete}
                        className="absolute -bottom-1 -right-1 p-1.5 bg-red-500 hover:bg-red-600 rounded-full text-white transition-colors shadow-lg"
                        title="Remove avatar"
                    >
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                )}
            </div>

            {/* Hidden file input */}
            <input
                ref={fileInputRef}
                type="file"
                accept={ALLOWED_TYPES.join(',')}
                onChange={handleFileSelect}
                className="hidden"
            />

            {/* Upload text hint */}
            <p className="text-xs text-gray-500">Click to upload</p>

            {/* Error message */}
            {error && (
                <p className="text-sm text-red-400 text-center">{error}</p>
            )}
        </div>
    )
}
