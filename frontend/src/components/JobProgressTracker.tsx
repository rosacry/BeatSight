import { useEffect, useState, useCallback, useRef } from 'react'
import type { AIJob } from '@/types/api'
import { subscribeToJobProgress, type JobProgressUpdate, type JobCompleteEvent } from '@/api/client'
import { ProgressBar } from './ProgressBar'
import { JobStatusBadge } from './JobStatusBadge'

interface JobProgressTrackerProps {
    job: AIJob
    onComplete?: (beatmapId?: string) => void
}

interface ProgressState {
    percent: number
    message: string | null
    stage: string | null
}

export function JobProgressTracker({ job, onComplete }: JobProgressTrackerProps) {
    const [progress, setProgress] = useState<ProgressState>({
        percent: job.progress_percent ?? 0,
        message: job.progress_message,
        stage: null,
    })
    const [connectionStatus, setConnectionStatus] = useState<'connected' | 'disconnected' | 'error'>('disconnected')
    const [errorMessage, setErrorMessage] = useState<string | null>(null)

    // Use refs to store latest callbacks to avoid re-subscription on callback changes
    const onCompleteRef = useRef(onComplete)
    useEffect(() => {
        onCompleteRef.current = onComplete
    }, [onComplete])

    const handleProgress = useCallback((update: JobProgressUpdate) => {
        setProgress({
            percent: update.percent,
            message: update.message,
            stage: update.stage,
        })
        setConnectionStatus('connected')
        setErrorMessage(null)
    }, [])

    const handleComplete = useCallback((event?: JobCompleteEvent) => {
        setConnectionStatus('disconnected')
        onCompleteRef.current?.(event?.beatmap_id)
    }, [])

    const handleError = useCallback((error: Error) => {
        setConnectionStatus('error')
        setErrorMessage(error.message)
    }, [])

    useEffect(() => {
        // Only subscribe if job is processing
        if (job.state !== 'processing') {
            return
        }

        // Track if effect is still active (for cleanup race conditions)
        let isActive = true

        const unsubscribe = subscribeToJobProgress(
            job.id,
            (update) => {
                if (isActive) handleProgress(update)
            },
            (event) => {
                if (isActive) handleComplete(event)
            },
            (error) => {
                if (isActive) handleError(error)
            }
        )

        setConnectionStatus('connected')

        return () => {
            isActive = false
            unsubscribe()
            setConnectionStatus('disconnected')
        }
    }, [job.id, job.state, handleProgress, handleComplete, handleError])

    if (job.state !== 'processing') {
        return (
            <div className="card">
                <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-medium text-white">Job Status</h3>
                    <JobStatusBadge state={job.state} />
                </div>

                {job.state === 'complete' && (
                    <p className="text-green-400">
                        Generation complete! Beatmap ready.
                    </p>
                )}

                {job.state === 'failed' && (
                    <div className="text-red-400">
                        <p className="font-medium">Generation failed</p>
                        {job.error_message && (
                            <p className="text-sm mt-1 text-red-300">{job.error_message}</p>
                        )}
                    </div>
                )}

                {job.state === 'queued' && (
                    <p className="text-yellow-400">
                        Waiting in queue... Your job will start soon.
                    </p>
                )}

                {job.state === 'cancelled' && (
                    <p className="text-gray-400">
                        This job was cancelled.
                    </p>
                )}
            </div>
        )
    }

    return (
        <div className="card">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium text-white">Processing</h3>
                <div className="flex items-center gap-2">
                    <span
                        className={`w-2 h-2 rounded-full ${connectionStatus === 'connected'
                            ? 'bg-green-400 animate-pulse'
                            : connectionStatus === 'error'
                                ? 'bg-red-400'
                                : 'bg-gray-400'
                            }`}
                    />
                    <span className="text-xs text-gray-400">
                        {connectionStatus === 'connected' && 'Live'}
                        {connectionStatus === 'disconnected' && 'Offline'}
                        {connectionStatus === 'error' && 'Connection error'}
                    </span>
                </div>
            </div>

            <ProgressBar
                percent={progress.percent}
                message={progress.message}
                stage={progress.stage}
                className="mb-4"
            />

            <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                    <span className="text-gray-400">Stage</span>
                    <p className="text-white font-medium">
                        {progress.stage || 'Initializing...'}
                    </p>
                </div>
                <div>
                    <span className="text-gray-400">Progress</span>
                    <p className="text-white font-medium">{progress.percent}%</p>
                </div>
            </div>

            {progress.message && (
                <div className="mt-4 p-3 bg-dark-300/50 rounded-lg">
                    <p className="text-sm text-gray-300">{progress.message}</p>
                </div>
            )}

            {connectionStatus === 'error' && errorMessage && (
                <div className="mt-4 p-3 bg-red-900/50 rounded-lg border border-red-500/50">
                    <p className="text-sm text-red-300">{errorMessage}</p>
                    <p className="text-xs text-red-400 mt-1">The connection will retry automatically.</p>
                </div>
            )}
        </div>
    )
}
