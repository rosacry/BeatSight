/**
 * Record Page
 * 
 * A mobile-first page for recording live drum performances.
 * Allows users to record audio directly and send it for AI beatmap generation.
 * 
 * Uses Web Audio API and MediaRecorder for browser-based audio capture.
 */

import { useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { LiveRecorder } from '@/components'
import { useAuthStore } from '@/stores/authStore'
import { useToast } from '@/components/Toast'
import { createLogger } from '@/lib/logger'

const logger = createLogger('RecordPage')

/**
 * Check if the browser supports audio recording
 */
function checkRecordingSupport(): { supported: boolean; reason?: string } {
    // Check for secure context (required for getUserMedia)
    if (!window.isSecureContext) {
        return {
            supported: false,
            reason: 'Audio recording requires a secure connection (HTTPS).'
        }
    }

    // Check for MediaDevices API
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        return {
            supported: false,
            reason: 'Your browser does not support audio recording. Please use a modern browser like Chrome, Firefox, or Safari.'
        }
    }

    // Check for MediaRecorder API
    if (typeof MediaRecorder === 'undefined') {
        return {
            supported: false,
            reason: 'Your browser does not support the MediaRecorder API. Please update your browser.'
        }
    }

    // Check for AudioContext
    if (typeof AudioContext === 'undefined' && typeof (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext === 'undefined') {
        return {
            supported: false,
            reason: 'Your browser does not support the Web Audio API.'
        }
    }

    return { supported: true }
}

interface RecordingMetadata {
    duration: number
    bpm: number
    sampleRate: number
    channels: number
    timestamp: Date
    deviceInfo: string
}

type PermissionState = 'prompt' | 'granted' | 'denied' | 'checking'

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

    // Browser support and permission state
    const [browserSupport] = useState(() => checkRecordingSupport())
    const [permissionState, setPermissionState] = useState<PermissionState>('checking')
    const [permissionError, setPermissionError] = useState<string | null>(null)

    // Check microphone permission on mount
    useEffect(() => {
        async function checkPermission() {
            try {
                // Try to query permission status (not supported in all browsers)
                if (navigator.permissions && navigator.permissions.query) {
                    const result = await navigator.permissions.query({ name: 'microphone' as PermissionName })
                    setPermissionState(result.state as PermissionState)

                    // Listen for permission changes
                    result.addEventListener('change', () => {
                        setPermissionState(result.state as PermissionState)
                    })
                } else {
                    // Browser doesn't support permission query, assume prompt needed
                    setPermissionState('prompt')
                }
            } catch {
                // Permission query not supported, assume prompt needed
                setPermissionState('prompt')
            }
        }

        if (browserSupport.supported) {
            checkPermission()
        }
    }, [browserSupport.supported])

    // Request microphone permission
    const requestPermission = useCallback(async () => {
        try {
            setPermissionError(null)
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
            // Permission granted, stop the stream immediately
            stream.getTracks().forEach(track => track.stop())
            setPermissionState('granted')
        } catch (error) {
            logger.error('Microphone permission error:', error)
            if (error instanceof DOMException) {
                if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
                    setPermissionState('denied')
                    setPermissionError('Microphone access was denied. Please allow microphone access in your browser settings.')
                } else if (error.name === 'NotFoundError') {
                    setPermissionError('No microphone found. Please connect a microphone and try again.')
                } else {
                    setPermissionError(`Could not access microphone: ${error.message}`)
                }
            } else {
                setPermissionError('An unexpected error occurred while accessing the microphone.')
            }
        }
    }, [])

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
            logger.error('Upload error:', error)
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

    // Browser not supported
    if (!browserSupport.supported) {
        return (
            <div className="max-w-2xl mx-auto px-4 py-6">
                <div className="mb-6">
                    <h1 className="text-2xl font-bold text-white">Record Drums</h1>
                    <p className="text-gray-400 mt-1">
                        Record your drum performance and get an AI-generated beatmap
                    </p>
                </div>

                <div className="bg-red-900/20 border border-red-500/30 rounded-xl p-8 text-center">
                    <div className="w-16 h-16 mx-auto mb-4 bg-red-500/20 rounded-full flex items-center justify-center">
                        <svg className="w-8 h-8 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                    </div>
                    <h2 className="text-xl font-bold text-white mb-2">Browser Not Supported</h2>
                    <p className="text-gray-300 mb-6">{browserSupport.reason}</p>

                    <div className="border-t border-gray-700 pt-6">
                        <p className="text-gray-400 text-sm mb-4">
                            You can still upload existing audio files:
                        </p>
                        <button
                            onClick={() => navigate('/upload')}
                            className="inline-flex items-center gap-2 px-6 py-3 bg-primary-500 hover:bg-primary-600 text-white rounded-lg font-medium transition-colors"
                        >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                            </svg>
                            Upload Audio File
                        </button>
                    </div>
                </div>
            </div>
        )
    }

    // Microphone permission denied
    if (permissionState === 'denied') {
        return (
            <div className="max-w-2xl mx-auto px-4 py-6">
                <div className="mb-6">
                    <h1 className="text-2xl font-bold text-white">Record Drums</h1>
                    <p className="text-gray-400 mt-1">
                        Record your drum performance and get an AI-generated beatmap
                    </p>
                </div>

                <div className="bg-yellow-900/20 border border-yellow-500/30 rounded-xl p-8 text-center">
                    <div className="w-16 h-16 mx-auto mb-4 bg-yellow-500/20 rounded-full flex items-center justify-center">
                        <svg className="w-8 h-8 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                        </svg>
                    </div>
                    <h2 className="text-xl font-bold text-white mb-2">Microphone Access Required</h2>
                    <p className="text-gray-300 mb-4">
                        Microphone permission was denied. To record audio, you'll need to enable microphone access in your browser settings.
                    </p>

                    <div className="bg-gray-800/50 rounded-lg p-4 text-left text-sm text-gray-400 mb-6">
                        <p className="font-medium text-white mb-2">How to enable microphone:</p>
                        <ol className="list-decimal list-inside space-y-1">
                            <li>Click the lock/info icon in your browser's address bar</li>
                            <li>Find "Microphone" in the site settings</li>
                            <li>Change the permission to "Allow"</li>
                            <li>Refresh this page</li>
                        </ol>
                    </div>

                    <div className="flex flex-col sm:flex-row gap-3 justify-center">
                        <button
                            onClick={() => window.location.reload()}
                            className="px-6 py-3 bg-primary-500 hover:bg-primary-600 text-white rounded-lg font-medium transition-colors"
                        >
                            Refresh Page
                        </button>
                        <button
                            onClick={() => navigate('/upload')}
                            className="px-6 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg font-medium transition-colors"
                        >
                            Upload Instead
                        </button>
                    </div>
                </div>
            </div>
        )
    }

    // Microphone permission not yet granted - show request UI
    if (permissionState === 'prompt' || permissionState === 'checking') {
        return (
            <div className="max-w-2xl mx-auto px-4 py-6">
                <div className="mb-6">
                    <h1 className="text-2xl font-bold text-white">Record Drums</h1>
                    <p className="text-gray-400 mt-1">
                        Record your drum performance and get an AI-generated beatmap
                    </p>
                </div>

                <div className="bg-gradient-to-br from-primary-900/40 to-gray-900 rounded-xl border border-primary-500/30 p-8">
                    <div className="text-center">
                        <div className="w-20 h-20 mx-auto mb-6 relative">
                            <div className="absolute inset-0 bg-primary-500/20 rounded-full animate-pulse" />
                            <div className="relative w-20 h-20 bg-gray-800 rounded-full flex items-center justify-center border-2 border-primary-500/50">
                                <svg className="w-10 h-10 text-primary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                                </svg>
                            </div>
                        </div>

                        <h2 className="text-2xl font-bold text-white mb-3">Enable Microphone Access</h2>
                        <p className="text-gray-300 mb-6 max-w-md mx-auto">
                            BeatSight needs access to your microphone to record your drum performances.
                            Click below to grant permission.
                        </p>

                        {permissionError && (
                            <div className="bg-red-900/30 border border-red-500/30 rounded-lg p-4 mb-6 text-red-300 text-sm">
                                {permissionError}
                            </div>
                        )}

                        <button
                            onClick={requestPermission}
                            disabled={permissionState === 'checking'}
                            className="inline-flex items-center gap-2 px-8 py-4 bg-primary-500 hover:bg-primary-600 disabled:bg-gray-600 text-white rounded-lg font-medium text-lg transition-colors"
                        >
                            {permissionState === 'checking' ? (
                                <>
                                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                    Checking...
                                </>
                            ) : (
                                <>
                                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                                    </svg>
                                    Allow Microphone Access
                                </>
                            )}
                        </button>

                        <p className="text-gray-500 text-xs mt-4">
                            Your browser will ask for permission. Click "Allow" to continue.
                        </p>

                        {/* Feature highlights */}
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-8 text-left">
                            <div className="bg-gray-800/50 rounded-lg p-4">
                                <div className="text-primary-400 font-medium mb-1">🎤 Live Recording</div>
                                <p className="text-gray-400 text-sm">Record directly from your microphone</p>
                            </div>
                            <div className="bg-gray-800/50 rounded-lg p-4">
                                <div className="text-primary-400 font-medium mb-1">🎵 Metronome</div>
                                <p className="text-gray-400 text-sm">Built-in click track with tap tempo</p>
                            </div>
                            <div className="bg-gray-800/50 rounded-lg p-4">
                                <div className="text-primary-400 font-medium mb-1">🤖 AI Analysis</div>
                                <p className="text-gray-400 text-sm">Get beatmaps in seconds</p>
                            </div>
                        </div>

                        {/* Alternative */}
                        <div className="border-t border-gray-700 pt-6 mt-8">
                            <p className="text-gray-400 text-sm mb-4">
                                Or upload an existing audio file:
                            </p>
                            <button
                                onClick={() => navigate('/upload')}
                                className="inline-flex items-center gap-2 px-6 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg font-medium transition-colors"
                            >
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                                </svg>
                                Upload Audio File
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        )
    }

    // Permission granted - show recording UI
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
