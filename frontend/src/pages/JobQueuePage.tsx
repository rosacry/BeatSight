import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { listJobs, getQuota } from '@/api/client'
import { JobCard } from '@/components/JobCard'
import { QuotaDisplay } from '@/components/QuotaDisplay'
import type { AIJobState } from '@/types/api'

type FilterState = 'all' | AIJobState

export function JobQueuePage() {
    const [filter, setFilter] = useState<FilterState>('all')

    const { data: jobs, isLoading, error } = useQuery({
        queryKey: ['jobs'],
        queryFn: () => listJobs(),
        refetchInterval: 10000, // Refresh every 10s
    })

    const { data: quota } = useQuery({
        queryKey: ['quota'],
        queryFn: getQuota,
    })

    const filteredJobs = jobs?.filter((job) => {
        if (filter === 'all') return true
        return job.state === filter
    }) ?? []

    const filterCounts = {
        all: jobs?.length ?? 0,
        queued: jobs?.filter((j) => j.state === 'queued').length ?? 0,
        processing: jobs?.filter((j) => j.state === 'processing').length ?? 0,
        complete: jobs?.filter((j) => j.state === 'complete').length ?? 0,
        failed: jobs?.filter((j) => j.state === 'failed').length ?? 0,
        cancelled: jobs?.filter((j) => j.state === 'cancelled').length ?? 0,
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-2xl font-bold text-white">Job Queue</h1>
                <button className="btn btn-primary">New Generation</button>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                {/* Main content */}
                <div className="lg:col-span-3 space-y-4">
                    {/* Filters */}
                    <div className="flex flex-wrap gap-2">
                        {(['all', 'queued', 'processing', 'complete', 'failed'] as const).map((state) => (
                            <button
                                key={state}
                                onClick={() => setFilter(state)}
                                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${filter === state
                                        ? 'bg-primary-600 text-white'
                                        : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                                    }`}
                            >
                                {state.charAt(0).toUpperCase() + state.slice(1)}
                                <span className="ml-1.5 text-xs opacity-75">
                                    ({filterCounts[state]})
                                </span>
                            </button>
                        ))}
                    </div>

                    {/* Job list */}
                    {isLoading ? (
                        <div className="space-y-4">
                            {[1, 2, 3].map((i) => (
                                <div key={i} className="card animate-pulse">
                                    <div className="h-4 bg-gray-700 rounded w-1/4 mb-3" />
                                    <div className="h-3 bg-gray-700 rounded w-1/2 mb-2" />
                                    <div className="h-3 bg-gray-700 rounded w-1/3" />
                                </div>
                            ))}
                        </div>
                    ) : error ? (
                        <div className="card bg-red-500/10 border border-red-500/20">
                            <p className="text-red-400">Failed to load jobs. Please try again.</p>
                        </div>
                    ) : filteredJobs.length === 0 ? (
                        <div className="card text-center py-12">
                            <p className="text-gray-400">No jobs found</p>
                            {filter !== 'all' && (
                                <button
                                    onClick={() => setFilter('all')}
                                    className="mt-2 text-primary-400 hover:text-primary-300"
                                >
                                    Clear filter
                                </button>
                            )}
                        </div>
                    ) : (
                        <div className="space-y-4">
                            {filteredJobs.map((job) => (
                                <JobCard key={job.id} job={job} />
                            ))}
                        </div>
                    )}
                </div>

                {/* Sidebar */}
                <div className="space-y-4">
                    {quota && <QuotaDisplay quota={quota} />}

                    {/* Quick stats */}
                    <div className="card">
                        <h3 className="text-lg font-medium text-white mb-4">Queue Stats</h3>
                        <div className="space-y-3">
                            <div className="flex justify-between">
                                <span className="text-gray-400">Processing</span>
                                <span className="text-blue-400 font-medium">{filterCounts.processing}</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-gray-400">Queued</span>
                                <span className="text-yellow-400 font-medium">{filterCounts.queued}</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-gray-400">Completed</span>
                                <span className="text-green-400 font-medium">{filterCounts.complete}</span>
                            </div>
                            <div className="flex justify-between">
                                <span className="text-gray-400">Failed</span>
                                <span className="text-red-400 font-medium">{filterCounts.failed}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}
