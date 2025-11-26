import { Link } from 'react-router-dom'
import { formatDistanceToNow } from 'date-fns'
import type { AIJob } from '@/types/api'
import { JobStatusBadge } from './JobStatusBadge'
import { ProgressBar } from './ProgressBar'

interface JobCardProps {
    job: AIJob
    showProgress?: boolean
}

export function JobCard({ job, showProgress = true }: JobCardProps) {
    const createdAt = new Date(job.created_at)

    return (
        <Link
            to={`/jobs/${job.id}`}
            className="card hover:bg-gray-750 transition-colors block"
        >
            <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                        <JobStatusBadge state={job.state} />
                        {job.priority === 'priority' && (
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-accent-500/20 text-accent-400 border border-accent-500/30">
                                Priority
                            </span>
                        )}
                    </div>

                    <p className="text-sm text-gray-400 truncate">
                        Song ID: {job.song_id.slice(0, 8)}...
                    </p>

                    <p className="text-xs text-gray-500 mt-1">
                        Created {formatDistanceToNow(createdAt, { addSuffix: true })}
                    </p>
                </div>

                <div className="text-right text-sm">
                    {job.state === 'processing' && job.progress_percent !== null && (
                        <span className="text-primary-400 font-medium">
                            {job.progress_percent}%
                        </span>
                    )}
                    {job.retry_count !== undefined && job.retry_count > 0 && (
                        <span className="text-yellow-400 text-xs block">
                            Retry {job.retry_count}/{job.max_retries}
                        </span>
                    )}
                </div>
            </div>

            {showProgress && job.state === 'processing' && job.progress_percent !== null && (
                <div className="mt-4">
                    <ProgressBar
                        percent={job.progress_percent}
                        message={job.progress_message}
                        showLabel={false}
                    />
                </div>
            )}

            {job.state === 'failed' && job.error_message && (
                <div className="mt-3 p-2 bg-red-500/10 border border-red-500/20 rounded text-sm text-red-400">
                    {job.error_message.slice(0, 100)}
                    {job.error_message.length > 100 && '...'}
                </div>
            )}
        </Link>
    )
}
