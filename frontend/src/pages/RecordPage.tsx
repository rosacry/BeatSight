/**
 * Record Page
 * 
 * A mobile-first page for recording live drum performances.
 * Allows users to record audio directly and send it for AI beatmap generation.
 */

import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { LiveRecorder } from '@/components'
import { useAuthStore } from '@/stores/authStore'
import { useToast } from '@/components/Toast'

interface RecordingMetadata {
    duration: number
    bpm: number
    sampleRate: number
    channels: number
    timestamp: Date
    deviceInfo: string
}

export function RecordPage() {
    const navigate = useNavigate()
    const user = useAuthStore((state) => state.user)
    const accessToken = useAuthStore((state) => state.accessToken)
    const { error: showError, success: showSuccess } = useToast()

    const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null)
    const [metadata, setMetadata] = useState<RecordingMetadata | null>(null)
    const [isUploading, setIsUploading] = useState(false)
    const [songTitle, setSongTitle] = useState('')
    const [artist, setArtist] = useState('')

    // Handle recording completion
    const handleRecordingComplete = useCallback((blob: Blob, meta: RecordingMetadata) => {
        setRecordedBlob(blob)
        setMetadata(meta)

        // Auto-generate a title based on date/time
        const now = new Date()
        setSongTitle(`Recording ${now.toLocaleDateString()} ${now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`)
        setArtist(user?.display_name || 'Unknown Artist')
    }, [user])

    // Upload recording
    const handleUpload = useCallback(async () => {
        if (!recordedBlob || !accessToken || !songTitle) {
            showError('Please provide a title for your recording')
            return
        }

        setIsUploading(true)

        try {
            // First, get a presigned upload URL
            const uploadUrlResponse = await fetch('/api/storage/upload-url', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${accessToken}`,
                },
                body: JSON.stringify({
                    filename: `${Date.now()}-recording.webm`,
                    content_type: 'audio/webm',
                }),
            })

            if (!uploadUrlResponse.ok) {
                throw new Error('Failed to get upload URL')
            }

            const { upload_url, storage_key } = await uploadUrlResponse.json()

            // Upload the audio file
            const uploadResponse = await fetch(upload_url, {
                method: 'PUT',
                body: recordedBlob,
                headers: {
                    'Content-Type': 'audio/webm',
                },
            })

            if (!uploadResponse.ok) {
                throw new Error('Failed to upload audio file')
            }

            // Create the song record
            const songResponse = await fetch('/api/songs', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${accessToken}`,
                },
                body: JSON.stringify({
                    title: songTitle,
                    artist: artist || 'Unknown Artist',
                    storage_key,
                    duration_ms: (metadata?.duration || 0) * 1000,
                    bpm: metadata?.bpm || 120,
                    source: 'live_recording',
                }),
            })

            if (!songResponse.ok) {
                throw new Error('Failed to create song record')
            }

            const song = await songResponse.json()

            // Optionally start AI job
            showSuccess('Recording uploaded successfully!')

            // Navigate to the song or job page
            navigate(`/library/${song.id}`)

        } catch (error) {
            console.error('Upload error:', error)
            showError(error instanceof Error ? error.message : 'Failed to upload recording')
        } finally {
            setIsUploading(false)
        }
    }, [recordedBlob, accessToken, songTitle, artist, metadata, showError, showSuccess, navigate])

    // Discard recording
    const handleDiscard = useCallback(() => {
        setRecordedBlob(null)
        setMetadata(null)
        setSongTitle('')
        setArtist('')
    }, [])

    // Download recording locally
    const handleDownload = useCallback(() => {
        if (!recordedBlob) return

        const url = URL.createObjectURL(recordedBlob)
        const a = document.createElement('a')
        a.href = url
        a.download = `${songTitle || 'recording'}.webm`
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        URL.revokeObjectURL(url)
    }, [recordedBlob, songTitle])

    // Format file size
    const formatSize = (bytes: number) => {
        if (bytes < 1024) return `${bytes} B`
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    }

    return (
        <div className="max-w-2xl mx-auto px-4 py-6">
            {/* Header */}
            <div className="mb-6">
                <h1 className="text-2xl font-bold text-white">Record Drums</h1>
                <p className="text-gray-400 mt-1">
                    Record your drum performance and get an AI-generated beatmap
                </p>
            </div>

            {!recordedBlob ? (
                /* Recording Interface */
                <LiveRecorder
                    onRecordingComplete={handleRecordingComplete}
                    initialBpm={120}
                    maxDuration={300} // 5 minutes max
                    showMetronome={true}
                />
            ) : (
                /* Post-Recording Interface */
                <div className="bg-gray-900 rounded-xl p-6 space-y-6">
                    {/* Recording Preview */}
                    <div className="bg-gray-800 rounded-lg p-4">
                        <div className="flex items-center gap-4">
                            <div className="w-16 h-16 bg-primary-500/20 rounded-lg flex items-center justify-center">
                                <svg className="w-8 h-8 text-primary-500" fill="currentColor" viewBox="0 0 24 24">
                                    <path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z" />
                                </svg>
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className="text-white font-medium">Recording Complete</div>
                                <div className="text-gray-400 text-sm flex items-center gap-3 mt-1">
                                    <span>{Math.floor((metadata?.duration || 0) / 60)}:{((metadata?.duration || 0) % 60).toString().padStart(2, '0')}</span>
                                    <span>•</span>
                                    <span>{metadata?.bpm} BPM</span>
                                    <span>•</span>
                                    <span>{formatSize(recordedBlob.size)}</span>
                                </div>
                            </div>
                        </div>

                        {/* Audio Player */}
                        <audio
                            src={URL.createObjectURL(recordedBlob)}
                            controls
                            className="w-full mt-4"
                        />
                    </div>

                    {/* Song Details Form */}
                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-300 mb-2">
                                Title *
                            </label>
                            <input
                                type="text"
                                value={songTitle}
                                onChange={(e) => setSongTitle(e.target.value)}
                                placeholder="My Drum Recording"
                                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white placeholder-gray-500 focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-300 mb-2">
                                Artist
                            </label>
                            <input
                                type="text"
                                value={artist}
                                onChange={(e) => setArtist(e.target.value)}
                                placeholder="Unknown Artist"
                                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white placeholder-gray-500 focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
                            />
                        </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex flex-col sm:flex-row gap-3">
                        <button
                            onClick={handleUpload}
                            disabled={isUploading || !songTitle}
                            className="flex-1 px-6 py-3 bg-primary-500 hover:bg-primary-600 disabled:bg-gray-700 text-white rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
                        >
                            {isUploading ? (
                                <>
                                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                    Uploading...
                                </>
                            ) : (
                                <>
                                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                                    </svg>
                                    Upload & Generate Beatmap
                                </>
                            )}
                        </button>

                        <button
                            onClick={handleDownload}
                            className="px-6 py-3 bg-gray-800 hover:bg-gray-700 text-white rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
                        >
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                            </svg>
                            Download
                        </button>

                        <button
                            onClick={handleDiscard}
                            className="px-6 py-3 bg-gray-800 hover:bg-red-500/20 text-gray-400 hover:text-red-400 rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
                        >
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                            Discard
                        </button>
                    </div>
                </div>
            )}

            {/* Tips Section */}
            <div className="mt-8 bg-gray-800/50 rounded-lg p-4">
                <h3 className="text-sm font-medium text-white mb-3">Recording Tips</h3>
                <ul className="space-y-2 text-sm text-gray-400">
                    <li className="flex items-start gap-2">
                        <span className="text-primary-500">•</span>
                        <span>Position your device 2-3 feet from your kit at ear level</span>
                    </li>
                    <li className="flex items-start gap-2">
                        <span className="text-primary-500">•</span>
                        <span>Use the metronome to keep tempo consistent for better detection</span>
                    </li>
                    <li className="flex items-start gap-2">
                        <span className="text-primary-500">•</span>
                        <span>Play cleanly - avoid hitting multiple drums simultaneously when starting out</span>
                    </li>
                    <li className="flex items-start gap-2">
                        <span className="text-primary-500">•</span>
                        <span>Studio quality mode uses more storage but produces better results</span>
                    </li>
                </ul>
            </div>
        </div>
    )
}

export default RecordPage
