/**
 * Banner upload component with preview.
 * Allows users to upload and change their profile banner (osu!-style).
 */

import { useState, useRef, useCallback } from 'react'
import { useAuthStore } from '@/stores/authStore'
import { API_CONFIG } from '@/lib/config'

const API_BASE = API_CONFIG.baseUrl
const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10MB
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']

interface BannerUploadProps {
    currentBannerUrl?: string | null
    onUploadSuccess?: (newBannerUrl: string | null) => void
    onUploadError?: (error: string) => void
    className?: string
}

export function BannerUpload({
    currentBannerUrl,
    onUploadSuccess,
    onUploadError,
    className = '',
}: BannerUploadProps) {
    const accessToken = useAuthStore((state) => state.accessToken)
    const fetchCurrentUser = useAuthStore((state) => state.fetchCurrentUser)

    const [isUploading, setIsUploading] = useState(false)
    const [previewUrl, setPreviewUrl] = useState<string | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [showMenu, setShowMenu] = useState(false)
    const fileInputRef = useRef<HTMLInputElement>(null)
    const menuRef = useRef<HTMLDivElement>(null)

    const uploadFile = useCallback(async (file: File) => {
        if (!accessToken) {
            setError('Please log in to upload a banner')
            return
        }

        setIsUploading(true)
        setError(null)

        try {
            const formData = new FormData()
            formData.append('file', file)

            const response = await fetch(`${API_BASE}/api/users/me/banner`, {
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

            setPreviewUrl(null)
            onUploadSuccess?.(userData.banner_url)

        } catch (err) {
            const message = err instanceof Error ? err.message : 'Failed to upload banner'
            setError(message)
            onUploadError?.(message)
            setPreviewUrl(null)
        } finally {
            setIsUploading(false)
            setShowMenu(false)
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
            setError('Image must be smaller than 10MB')
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
            const response = await fetch(`${API_BASE}/api/users/me/banner`, {
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
            onUploadSuccess?.(null)

        } catch (err) {
            const message = err instanceof Error ? err.message : 'Failed to delete banner'
            setError(message)
        } finally {
            setIsUploading(false)
            setShowMenu(false)
        }
    }

    const handleUploadClick = () => {
        fileInputRef.current?.click()
        setShowMenu(false)
    }

    // Determine what to show
    const displayUrl = previewUrl || currentBannerUrl

    // Close menu on outside click
    const handleBannerClick = () => {
        setShowMenu(!showMenu)
    }

    return (
        <div className={`relative group ${className}`}>
            {/* Hidden file input */}
            <input
                ref={fileInputRef}
                type="file"
                accept={ALLOWED_TYPES.join(',')}
                onChange={handleFileSelect}
                className="hidden"
            />

            {/* Banner Display with overlay on hover */}
            <div
                className="absolute inset-0 cursor-pointer"
                onClick={handleBannerClick}
            >
                {/* Hover overlay */}
                <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-all duration-200 flex items-center justify-center opacity-0 group-hover:opacity-100">
                    <div className="flex items-center gap-2 px-4 py-2 bg-dark-500/90 rounded-lg border border-white/20">
                        <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                        </svg>
                        <span className="text-sm font-medium text-white">Change Banner</span>
                    </div>
                </div>
            </div>

            {/* Dropdown menu */}
            {showMenu && (
                <div
                    ref={menuRef}
                    className="absolute top-full left-1/2 -translate-x-1/2 mt-2 z-50 bg-dark-400 border border-white/10 rounded-xl shadow-xl overflow-hidden"
                    style={{ animation: 'slideInFromTop 0.15s ease-out' }}
                >
                    <button
                        onClick={handleUploadClick}
                        disabled={isUploading}
                        className="w-full flex items-center gap-3 px-4 py-3 text-sm text-white hover:bg-dark-300 transition-colors"
                    >
                        <svg className="w-5 h-5 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                        </svg>
                        <span>Upload New Banner</span>
                    </button>

                    {displayUrl && (
                        <button
                            onClick={handleDelete}
                            disabled={isUploading}
                            className="w-full flex items-center gap-3 px-4 py-3 text-sm text-red-400 hover:bg-dark-300 transition-colors border-t border-white/5"
                        >
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                            <span>Remove Banner</span>
                        </button>
                    )}
                </div>
            )}

            {/* Loading overlay */}
            {isUploading && (
                <div className="absolute inset-0 bg-dark-600/80 flex items-center justify-center">
                    <div className="flex items-center gap-2 text-white">
                        <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        <span className="text-sm">Uploading...</span>
                    </div>
                </div>
            )}

            {/* Error toast */}
            {error && (
                <div className="absolute bottom-4 left-1/2 -translate-x-1/2 px-4 py-2 bg-red-500/90 text-white text-sm rounded-lg shadow-lg">
                    {error}
                </div>
            )}
        </div>
    )
}

export default BannerUpload
