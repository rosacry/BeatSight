import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getJob, cancelJob, retryJob } from '@/api/client'
import { JobStatusBadge } from '@/components/JobStatusBadge'
import { JobProgressTracker } from '@/components/JobProgressTracker'

export function JobDetailPage() {
    const { jobId } = useParams<{ jobId: string }>()
    const navigate = useNavigate()
    const queryClient = useQueryClient()

    const { data: job, isLoading, error } = useQuery({
        queryKey: ['job', jobId],
        queryFn: () => getJob(jobId!),
        enabled: !!jobId,
        refetchInterval: (query) => {
            const state = query.state.data?.state
            // Poll more frequently for active jobs
            if (state === 'processing' || state === 'queued') {
                return 5000
            }
            return false
        },
    })

    const cancelMutation = useMutation({
        mutationFn: () => cancelJob(jobId!),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['job', jobId] })
            queryClient.invalidateQueries({ queryKey: ['jobs'] })
        },
    })

    const retryMutation = useMutation({
        mutationFn: () => retryJob(jobId!),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['job', jobId] })
            queryClient.invalidateQueries({ queryKey: ['jobs'] })
        },
    })

    if (isLoading) {
        return (
            <div className="space-y-6 animate-pulse">
                <div className="h-8 bg-gray-700 rounded w-1/3" />
                <div className="card">
                    <div className="h-4 bg-gray-700 rounded w-1/2 mb-4" />
                    <div className="h-20 bg-gray-700 rounded" />
                </div>
            </div>
        )
    }

    if (error || !job) {
        return (
            <div className="card bg-red-500/10 border border-red-500/20">
                <h2 className="text-lg font-medium text-red-400 mb-2">Job Not Found</h2>
                <p className="text-gray-400 mb-4">The requested job could not be found.</p>
                <button onClick={() => navigate('/queue')} className="btn btn-secondary">
                    Back to Queue
                </button>
            </div>
        )
    }

    const canCancel = job.state === 'queued' || job.state === 'processing'
    const canRetry = job.state === 'failed' || job.state === 'cancelled'

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <button
                        onClick={() => navigate('/queue')}
                        className="text-gray-400 hover:text-white transition-colors"
                    >
                        ← Back
                    </button>
                    <h1 className="text-2xl font-bold text-white">Job Details</h1>
                </div>
                <div className="flex items-center gap-2">
                    {canCancel && (
                        <button
                            onClick={() => cancelMutation.mutate()}
                            disabled={cancelMutation.isPending}
                            className="btn btn-danger"
                        >
                            {cancelMutation.isPending ? 'Cancelling...' : 'Cancel Job'}
                        </button>
                    )}
                    {canRetry && (
                        <button
                            onClick={() => retryMutation.mutate()}
                            disabled={retryMutation.isPending}
                            className="btn btn-primary"
                        >
                            {retryMutation.isPending ? 'Retrying...' : 'Retry Job'}
                        </button>
                    )}
                </div>
            </div>

            {/* Progress tracker for active jobs */}
            {(job.state === 'queued' || job.state === 'processing') && (
                <JobProgressTracker job={job} />
            )}

            {/* Job info */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="card">
                    <h2 className="text-lg font-medium text-white mb-4">Job Information</h2>
                    <dl className="space-y-4">
                        <div className="flex justify-between">
                            <dt className="text-gray-400">Status</dt>
                            <dd><JobStatusBadge state={job.state} /></dd>
                        </div>
                        <div className="flex justify-between">
                            <dt className="text-gray-400">Job ID</dt>
                            <dd className="text-white font-mono text-sm">{job.id}</dd>
                        </div>
                        <div className="flex justify-between">
                            <dt className="text-gray-400">Priority</dt>
                            <dd className={`font-medium ${job.priority === 'priority' ? 'text-yellow-400' : 'text-green-400'}`}>
                                {job.priority === 'priority' ? 'Priority' : 'Standard'}
                            </dd>
                        </div>
                        {job.progress_percent !== null && job.progress_percent !== undefined && (
                            <div className="flex justify-between">
                                <dt className="text-gray-400">Progress</dt>
                                <dd className="text-white">{Math.round(job.progress_percent)}%</dd>
                            </div>
                        )}
                    </dl>
                </div>

                <div className="card">
                    <h2 className="text-lg font-medium text-white mb-4">Timestamps</h2>
                    <dl className="space-y-4">
                        <div className="flex justify-between">
                            <dt className="text-gray-400">Created</dt>
                            <dd className="text-white">{formatTimestamp(job.created_at)}</dd>
                        </div>
                        {job.started_at && (
                            <div className="flex justify-between">
                                <dt className="text-gray-400">Started</dt>
                                <dd className="text-white">{formatTimestamp(job.started_at)}</dd>
                            </div>
                        )}
                        {job.finished_at && (
                            <div className="flex justify-between">
                                <dt className="text-gray-400">Completed</dt>
                                <dd className="text-white">{formatTimestamp(job.finished_at)}</dd>
                            </div>
                        )}
                        {job.started_at && (job.finished_at || job.state === 'processing') && (
                            <div className="flex justify-between">
                                <dt className="text-gray-400">Duration</dt>
                                <dd className="text-white">
                                    {formatDuration(job.started_at, job.finished_at || new Date().toISOString())}
                                </dd>
                            </div>
                        )}
                    </dl>
                </div>
            </div>

            {/* Error info for failed jobs */}
            {job.state === 'failed' && job.error_message && (
                <div className="card bg-red-500/10 border border-red-500/20">
                    <h2 className="text-lg font-medium text-red-400 mb-2">Error Details</h2>
                    <pre className="text-sm text-gray-300 whitespace-pre-wrap font-mono bg-gray-800 rounded p-4">
                        {job.error_message}
                    </pre>
                </div>
            )}

            {/* Results for completed jobs */}
            {job.state === 'complete' && (
                <div className="card bg-green-500/10 border border-green-500/20">
                    <h2 className="text-lg font-medium text-green-400 mb-4">Generation Complete!</h2>
                    <p className="text-gray-300 mb-4">
                        Your beatmap has been generated successfully. View it on the song page.
                    </p>
                    <button
                        onClick={() => navigate(`/songs/${job.song_id}`)}
                        className="btn btn-primary inline-flex items-center gap-2"
                    >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
                        </svg>
                        View Beatmap
                    </button>
                </div>
            )}
        </div>
    )
}

function formatTimestamp(iso: string): string {
    const date = new Date(iso)
    return date.toLocaleString()
}

function formatDuration(start: string, end: string): string {
    const startDate = new Date(start)
    const endDate = new Date(end)
    const seconds = Math.floor((endDate.getTime() - startDate.getTime()) / 1000)

    if (seconds < 60) return `${seconds}s`
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`
}
