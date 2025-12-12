/**
 * Banner upload component with preview.
 * Allows users to upload and change their profile banner (osu!-style).
 * 
 * Features:
 * - Drag and drop support
 * - Click to upload
 * - Visual feedback on hover/drag
 * - Preview before upload completes
 * - Delete functionality
 */

import { useState, useRef, useCallback, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
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
    /** Mode: 'overlay' for profile page, 'standalone' for settings page */
    mode?: 'overlay' | 'standalone'
}

export function BannerUpload({
    currentBannerUrl,
    onUploadSuccess,
    onUploadError,
    className = '',
    mode = 'overlay',
}: BannerUploadProps) {
    const accessToken = useAuthStore((state) => state.accessToken)
    const fetchCurrentUser = useAuthStore((state) => state.fetchCurrentUser)

    const [isUploading, setIsUploading] = useState(false)
    const [previewUrl, setPreviewUrl] = useState<string | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [showMenu, setShowMenu] = useState(false)
    const [isDragOver, setIsDragOver] = useState(false)
    const fileInputRef = useRef<HTMLInputElement>(null)
    const menuRef = useRef<HTMLDivElement>(null)
    const dropZoneRef = useRef<HTMLDivElement>(null)

    // Close menu on outside click
    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
                setShowMenu(false)
            }
        }
        if (showMenu) {
            document.addEventListener('mousedown', handleClickOutside)
            return () => document.removeEventListener('mousedown', handleClickOutside)
        }
    }, [showMenu])

    // Clear error after 5 seconds
    useEffect(() => {
        if (error) {
            const timer = setTimeout(() => setError(null), 5000)
            return () => clearTimeout(timer)
        }
    }, [error])

    const validateFile = useCallback((file: File): string | null => {
        if (!ALLOWED_TYPES.includes(file.type)) {
            return 'Please upload a JPEG, PNG, WebP, or GIF image'
        }
        if (file.size > MAX_FILE_SIZE) {
            return 'Image must be smaller than 10MB'
        }
        return null
    }, [])

    const uploadFile = useCallback(async (file: File) => {
        if (!accessToken) {
            const msg = 'Please log in to upload a banner'
            setError(msg)
            onUploadError?.(msg)
            return
        }

        // Validate file
        const validationError = validateFile(file)
        if (validationError) {
            setError(validationError)
            onUploadError?.(validationError)
            return
        }

        // Create preview immediately
        const reader = new FileReader()
        reader.onload = (e) => {
            setPreviewUrl(e.target?.result as string)
        }
        reader.readAsDataURL(file)

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
    }, [accessToken, fetchCurrentUser, onUploadSuccess, onUploadError, validateFile])

    const handleFileSelect = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0]
        if (!file) return
        // Reset input so same file can be selected again
        event.target.value = ''
        uploadFile(file)
    }, [uploadFile])

    // Drag and drop handlers
    const handleDragEnter = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        e.stopPropagation()
        setIsDragOver(true)
    }, [])

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        e.stopPropagation()
        // Only set to false if we're actually leaving the drop zone
        if (dropZoneRef.current && !dropZoneRef.current.contains(e.relatedTarget as Node)) {
            setIsDragOver(false)
        }
    }, [])

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        e.stopPropagation()
    }, [])

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        e.stopPropagation()
        setIsDragOver(false)

        const file = e.dataTransfer.files?.[0]
        if (file) {
            uploadFile(file)
        }
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
            onUploadError?.(message)
        } finally {
            setIsUploading(false)
            setShowMenu(false)
        }
    }

    const handleUploadClick = (e: React.MouseEvent) => {
        e.preventDefault()
        e.stopPropagation()
        fileInputRef.current?.click()
        setShowMenu(false)
    }

    // Determine what to show
    const displayUrl = previewUrl || currentBannerUrl

    const handleBannerClick = (e: React.MouseEvent) => {
        e.preventDefault()
        e.stopPropagation()
        if (mode === 'standalone') {
            // In standalone mode, just open file picker directly
            fileInputRef.current?.click()
        } else {
            // In overlay mode, show menu
            setShowMenu(!showMenu)
        }
    }

    // Standalone mode for settings page - simpler, cleaner design
    if (mode === 'standalone') {
        return (
            <div className={`relative ${className}`}>
                {/* Hidden file input */}
                <input
                    ref={fileInputRef}
                    type="file"
                    accept={ALLOWED_TYPES.join(',')}
                    onChange={handleFileSelect}
                    className="hidden"
                />

                {/* Drop zone container */}
                <div
                    ref={dropZoneRef}
                    onDragEnter={handleDragEnter}
                    onDragLeave={handleDragLeave}
                    onDragOver={handleDragOver}
                    onDrop={handleDrop}
                    onClick={handleBannerClick}
                    className={`
                        relative h-32 md:h-40 rounded-xl overflow-hidden cursor-pointer
                        transition-all duration-200 group
                        ${isDragOver
                            ? 'ring-2 ring-primary-500 ring-offset-2 ring-offset-dark-400'
                            : 'hover:ring-2 hover:ring-white/20'
                        }
                    `}
                >
                    {/* Background image or gradient */}
                    {displayUrl ? (
                        <img
                            src={displayUrl}
                            alt="Profile banner"
                            className="absolute inset-0 w-full h-full object-cover"
                        />
                    ) : (
                        <div className="absolute inset-0 bg-gradient-to-br from-primary-600/30 via-dark-400 to-accent-600/30" />
                    )}

                    {/* Hover/drag overlay */}
                    <AnimatePresence>
                        {(isDragOver || !displayUrl) && (
                            <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                exit={{ opacity: 0 }}
                                className={`
                                    absolute inset-0 flex flex-col items-center justify-center
                                    ${isDragOver ? 'bg-primary-500/30' : 'bg-dark-500/60'}
                                    backdrop-blur-sm
                                `}
                            >
                                <motion.div
                                    initial={{ scale: 0.9 }}
                                    animate={{ scale: 1 }}
                                    className="flex flex-col items-center gap-2"
                                >
                                    <div className={`
                                        w-12 h-12 rounded-xl flex items-center justify-center
                                        ${isDragOver ? 'bg-primary-500' : 'bg-white/10'}
                                    `}>
                                        <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                        </svg>
                                    </div>
                                    <p className="text-white font-medium text-sm">
                                        {isDragOver ? 'Drop image here' : 'Click or drag to upload'}
                                    </p>
                                    <p className="text-gray-400 text-xs">
                                        JPEG, PNG, WebP, GIF • Max 10MB
                                    </p>
                                </motion.div>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* Normal hover overlay when image exists */}
                    {displayUrl && !isDragOver && (
                        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/50 transition-all duration-200 flex items-center justify-center opacity-0 group-hover:opacity-100">
                            <div className="flex items-center gap-3">
                                <button
                                    onClick={handleUploadClick}
                                    className="flex items-center gap-2 px-4 py-2 bg-white/10 hover:bg-white/20 rounded-lg text-white text-sm font-medium transition-colors"
                                >
                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                                    </svg>
                                    Change
                                </button>
                                <button
                                    onClick={(e) => { e.stopPropagation(); handleDelete(); }}
                                    disabled={isUploading}
                                    className="flex items-center gap-2 px-4 py-2 bg-red-500/20 hover:bg-red-500/30 rounded-lg text-red-400 text-sm font-medium transition-colors"
                                >
                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                    </svg>
                                    Remove
                                </button>
                            </div>
                        </div>
                    )}
                </div>

                {/* Loading overlay */}
                <AnimatePresence>
                    {isUploading && (
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="absolute inset-0 bg-dark-600/90 rounded-xl flex items-center justify-center z-20"
                        >
                            <div className="flex flex-col items-center gap-3 text-white">
                                <svg className="animate-spin h-8 w-8" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                </svg>
                                <span className="text-sm font-medium">Uploading...</span>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Error toast */}
                <AnimatePresence>
                    {error && (
                        <motion.div
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: 10 }}
                            className="absolute bottom-2 left-2 right-2 px-3 py-2 bg-red-500/90 text-white text-sm rounded-lg shadow-lg z-30"
                        >
                            {error}
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        )
    }

    // Overlay mode for profile page banner
    return (
        <div
            ref={dropZoneRef}
            className={`relative group ${className}`}
            onDragEnter={handleDragEnter}
            onDragLeave={handleDragLeave}
            onDragOver={handleDragOver}
            onDrop={handleDrop}
        >
            {/* Hidden file input */}
            <input
                ref={fileInputRef}
                type="file"
                accept={ALLOWED_TYPES.join(',')}
                onChange={handleFileSelect}
                className="hidden"
            />

            {/* Clickable overlay area */}
            <div
                className="absolute inset-0 cursor-pointer"
                onClick={handleBannerClick}
            >
                {/* Drag over indicator */}
                <AnimatePresence>
                    {isDragOver && (
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="absolute inset-0 bg-primary-500/30 backdrop-blur-sm z-50 flex items-center justify-center"
                        >
                            <div className="flex flex-col items-center gap-3">
                                <motion.div
                                    initial={{ scale: 0.8 }}
                                    animate={{ scale: 1 }}
                                    className="w-16 h-16 rounded-2xl bg-primary-500 flex items-center justify-center"
                                >
                                    <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                                    </svg>
                                </motion.div>
                                <span className="text-white font-semibold text-lg">Drop to upload</span>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Hover overlay - only show when not dragging */}
                {!isDragOver && (
                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/50 transition-all duration-200 flex items-center justify-center opacity-0 group-hover:opacity-100">
                        <div className="flex items-center gap-2 px-5 py-3 bg-dark-500/95 rounded-xl border border-white/20 shadow-xl">
                            <svg className="w-5 h-5 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                            </svg>
                            <span className="text-sm font-semibold text-white">Click to Change Banner</span>
                        </div>
                    </div>
                )}
            </div>

            {/* Floating menu - positioned in center of banner */}
            <AnimatePresence>
                {showMenu && (
                    <motion.div
                        ref={menuRef}
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.95 }}
                        transition={{ duration: 0.15 }}
                        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-[100] bg-dark-500 border border-white/10 rounded-xl shadow-2xl overflow-hidden min-w-[220px]"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="p-3 border-b border-white/10 bg-dark-400">
                            <p className="text-sm text-white font-medium text-center">Profile Banner</p>
                        </div>
                        <div className="p-2">
                            <button
                                onClick={handleUploadClick}
                                disabled={isUploading}
                                className="w-full flex items-center gap-3 px-4 py-3 text-sm text-white hover:bg-white/10 rounded-lg transition-colors"
                            >
                                <div className="w-8 h-8 rounded-lg bg-primary-500/20 flex items-center justify-center">
                                    <svg className="w-4 h-4 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                                    </svg>
                                </div>
                                <span>Upload New Banner</span>
                            </button>

                            {displayUrl && (
                                <button
                                    onClick={(e) => { e.stopPropagation(); handleDelete(); }}
                                    disabled={isUploading}
                                    className="w-full flex items-center gap-3 px-4 py-3 text-sm text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                                >
                                    <div className="w-8 h-8 rounded-lg bg-red-500/20 flex items-center justify-center">
                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                        </svg>
                                    </div>
                                    <span>Remove Banner</span>
                                </button>
                            )}
                        </div>
                        <div className="p-2 border-t border-white/10">
                            <button
                                onClick={(e) => { e.stopPropagation(); setShowMenu(false); }}
                                className="w-full text-xs text-gray-500 hover:text-gray-300 py-2 transition-colors"
                            >
                                Cancel
                            </button>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Loading overlay */}
            <AnimatePresence>
                {isUploading && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="absolute inset-0 bg-dark-600/90 flex items-center justify-center z-[90]"
                    >
                        <div className="flex flex-col items-center gap-3 text-white">
                            <svg className="animate-spin h-8 w-8" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                            </svg>
                            <span className="text-sm font-medium">Uploading banner...</span>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Error toast */}
            <AnimatePresence>
                {error && (
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 10 }}
                        className="absolute bottom-4 left-1/2 -translate-x-1/2 px-4 py-2 bg-red-500/90 text-white text-sm rounded-lg shadow-lg z-[100]"
                    >
                        {error}
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    )
}

export default BannerUpload
