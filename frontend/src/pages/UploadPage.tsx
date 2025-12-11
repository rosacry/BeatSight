import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { uploadFileWithProgress, createJob, getQuota } from '@/api/client'
import { QuotaDisplay } from '@/components/QuotaDisplay'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'

type UploadState = 'idle' | 'uploading' | 'processing' | 'complete' | 'error'

export function UploadPage() {
    useDocumentTitle('upload')
    const navigate = useNavigate()
    const queryClient = useQueryClient()
    const fileInputRef = useRef<HTMLInputElement>(null)

    const [file, setFile] = useState<File | null>(null)
    const [uploadState, setUploadState] = useState<UploadState>('idle')
    const [uploadProgress, setUploadProgress] = useState(0)
    const [errorMessage, setErrorMessage] = useState('')
    const [dragOver, setDragOver] = useState(false)

    const { data: quota } = useQuery({
        queryKey: ['quota'],
        queryFn: getQuota,
    })

    const uploadMutation = useMutation({
        mutationFn: async (file: File) => {
            setUploadState('uploading')
            setUploadProgress(0)

            // Real upload progress via XMLHttpRequest
            const result = await uploadFileWithProgress(file, 'audio', (percent) => {
                setUploadProgress(percent)
            })

            return result
        },
        onSuccess: async (data) => {
            setUploadState('processing')

            // Create job with uploaded file
            const job = await createJob({
                audio_key: data.key,
                priority: 50,
            })

            queryClient.invalidateQueries({ queryKey: ['jobs'] })
            queryClient.invalidateQueries({ queryKey: ['quota'] })

            setUploadState('complete')

            // Navigate to job detail page after short delay
            setTimeout(() => {
                navigate(`/jobs/${job.id}`)
            }, 1500)
        },
        onError: (error: Error) => {
            setUploadState('error')
            setErrorMessage(error.message || 'Upload failed. Please try again.')
        },
    })

    const handleFileSelect = (selectedFile: File | null) => {
        if (!selectedFile) return

        // Validate file type
        const validTypes = ['audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/ogg', 'audio/flac']
        if (!validTypes.includes(selectedFile.type)) {
            setErrorMessage('Please select a valid audio file (MP3, WAV, OGG, or FLAC)')
            return
        }

        // Validate file size (max 100MB)
        const maxSize = 100 * 1024 * 1024
        if (selectedFile.size > maxSize) {
            setErrorMessage('File size must be less than 100MB')
            return
        }

        setFile(selectedFile)
        setErrorMessage('')
    }

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault()
        setDragOver(false)

        const droppedFile = e.dataTransfer.files[0]
        handleFileSelect(droppedFile)
    }

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault()
        setDragOver(true)
    }

    const handleDragLeave = () => {
        setDragOver(false)
    }

    const handleUpload = () => {
        if (!file) return
        uploadMutation.mutate(file)
    }

    const handleReset = () => {
        setFile(null)
        setUploadState('idle')
        setUploadProgress(0)
        setErrorMessage('')
        if (fileInputRef.current) {
            fileInputRef.current.value = ''
        }
    }

    const isQuotaExceeded = quota && (
        quota.used_today >= quota.limit_day ||
        quota.used_this_month >= quota.limit_month
    )

    return (
        <div className="max-w-6xl mx-auto px-4 py-8">
            <h1 className="text-2xl sm:text-3xl font-bold text-white mb-8">Generate Beatmap</h1>

            {/* Quota warning */}
            {isQuotaExceeded && (
                <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/20">
                    <p className="text-red-400 text-sm sm:text-base">
                        Quota reached. Wait for reset or upgrade plan.
                    </p>
                </div>
            )}

            {/* Main content grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Left column - Upload area (takes 2 cols on lg) */}
                <div className="lg:col-span-2 space-y-6">
                    {/* Upload card */}
                    <div className="card bg-dark-400 border border-white/10">
                        <h2 className="text-lg font-semibold text-white mb-4">Upload Audio File</h2>

                        {uploadState === 'idle' && (
                            <>
                                <div
                                    onDrop={handleDrop}
                                    onDragOver={handleDragOver}
                                    onDragLeave={handleDragLeave}
                                    onClick={() => fileInputRef.current?.click()}
                                    className={`
                                        border-2 border-dashed rounded-xl p-8 sm:p-12 text-center cursor-pointer
                                        transition-all duration-200
                                        ${dragOver
                                            ? 'border-primary-500 bg-primary-500/10'
                                            : 'border-white/10 hover:border-white/20 hover:bg-white/5'
                                        }
                                    `}
                                >
                                    <input
                                        ref={fileInputRef}
                                        type="file"
                                        accept="audio/*"
                                        onChange={(e) => handleFileSelect(e.target.files?.[0] || null)}
                                        className="hidden"
                                    />

                                    <div className="mb-4">
                                        <svg className="w-16 h-16 mx-auto text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                                        </svg>
                                    </div>

                                    <p className="text-white font-medium text-lg mb-2">
                                        Drop audio here or click to browse
                                    </p>
                                    <p className="text-gray-500 text-sm">
                                        MP3, WAV, OGG, FLAC • Max 100MB
                                    </p>
                                </div>

                                {file && (
                                    <div className="mt-4 p-4 bg-dark-300 rounded-xl flex items-center justify-between border border-white/5">
                                        <div className="flex items-center gap-4">
                                            <div className="w-12 h-12 rounded-lg bg-primary-500/20 flex items-center justify-center">
                                                <svg className="w-6 h-6 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
                                                </svg>
                                            </div>
                                            <div>
                                                <p className="text-white font-medium">{file.name}</p>
                                                <p className="text-gray-500 text-sm">{formatFileSize(file.size)}</p>
                                            </div>
                                        </div>
                                        <button
                                            onClick={(e) => { e.stopPropagation(); handleReset() }}
                                            className="p-2 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                                        >
                                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                            </svg>
                                        </button>
                                    </div>
                                )}

                                {errorMessage && (
                                    <p className="mt-4 text-red-400 text-sm">{errorMessage}</p>
                                )}

                                <button
                                    onClick={handleUpload}
                                    disabled={!file || isQuotaExceeded}
                                    className="mt-6 w-full btn btn-primary py-3 text-base disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    Start Generation
                                </button>
                            </>
                        )}

                        {uploadState === 'uploading' && (
                            <div className="text-center py-12">
                                <div className="w-20 h-20 mx-auto mb-6 relative">
                                    <svg className="w-20 h-20 animate-spin text-primary-500" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                    </svg>
                                </div>
                                <p className="text-white font-medium text-lg mb-4">Uploading...</p>
                                <div className="max-w-xs mx-auto">
                                    <div className="w-full bg-white/10 rounded-full h-2">
                                        <div
                                            className="bg-primary-500 h-2 rounded-full transition-all"
                                            style={{ width: `${uploadProgress}%` }}
                                        />
                                    </div>
                                    <p className="text-gray-400 text-sm mt-2">{uploadProgress}%</p>
                                </div>
                            </div>
                        )}

                        {uploadState === 'processing' && (
                            <div className="text-center py-12">
                                <div className="w-20 h-20 mx-auto mb-6">
                                    <svg className="w-20 h-20 animate-pulse text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                                    </svg>
                                </div>
                                <p className="text-white font-medium text-lg mb-2">Creating job...</p>
                                <p className="text-gray-500 text-sm">This may take a moment</p>
                            </div>
                        )}

                        {uploadState === 'complete' && (
                            <div className="text-center py-12">
                                <div className="w-20 h-20 mx-auto mb-6">
                                    <svg className="w-20 h-20 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                    </svg>
                                </div>
                                <p className="text-white font-medium text-lg mb-2">Job created!</p>
                                <p className="text-gray-500 text-sm">Redirecting to job details...</p>
                            </div>
                        )}

                        {uploadState === 'error' && (
                            <div className="text-center py-12">
                                <div className="w-20 h-20 mx-auto mb-6">
                                    <svg className="w-20 h-20 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                    </svg>
                                </div>
                                <p className="text-white font-medium text-lg mb-2">Upload failed</p>
                                <p className="text-red-400 text-sm mb-6">{errorMessage}</p>
                                <button onClick={handleReset} className="btn btn-secondary">
                                    Try Again
                                </button>
                            </div>
                        )}
                    </div>

                    {/* How it works - below upload on larger screens */}
                    <div className="card bg-dark-400 border border-white/10">
                        <h3 className="text-lg font-semibold text-white mb-4">How it works</h3>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div className="flex items-start gap-3">
                                <div className="w-8 h-8 rounded-lg bg-primary-500/20 flex items-center justify-center flex-shrink-0">
                                    <span className="text-primary-400 font-semibold text-sm">1</span>
                                </div>
                                <p className="text-gray-400 text-sm">Upload your audio file (song you want to play)</p>
                            </div>
                            <div className="flex items-start gap-3">
                                <div className="w-8 h-8 rounded-lg bg-primary-500/20 flex items-center justify-center flex-shrink-0">
                                    <span className="text-primary-400 font-semibold text-sm">2</span>
                                </div>
                                <p className="text-gray-400 text-sm">Our AI analyzes the music and detects instruments</p>
                            </div>
                            <div className="flex items-start gap-3">
                                <div className="w-8 h-8 rounded-lg bg-primary-500/20 flex items-center justify-center flex-shrink-0">
                                    <span className="text-primary-400 font-semibold text-sm">3</span>
                                </div>
                                <p className="text-gray-400 text-sm">A beatmap is generated matching the drum patterns</p>
                            </div>
                            <div className="flex items-start gap-3">
                                <div className="w-8 h-8 rounded-lg bg-primary-500/20 flex items-center justify-center flex-shrink-0">
                                    <span className="text-primary-400 font-semibold text-sm">4</span>
                                </div>
                                <p className="text-gray-400 text-sm">Download and play in BeatSight!</p>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Right column - Quota display */}
                <div className="lg:col-span-1">
                    {quota && <QuotaDisplay quota={quota} />}
                </div>
            </div>
        </div>
    )
}

function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
