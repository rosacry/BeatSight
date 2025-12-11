import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { listJobs, getQuota } from '@/api/client'
import { JobCard } from '@/components/JobCard'
import { QuotaDisplay } from '@/components/QuotaDisplay'
import type { AIJobState } from '@/types/api'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'

type FilterState = 'all' | AIJobState

export function JobQueuePage() {
    useDocumentTitle('queue')
    const [filter, setFilter] = useState<FilterState>('all')

    const { data: jobs, isLoading, error } = useQuery({
        queryKey: ['jobs'],
        queryFn: () => listJobs({ pageSize: 100 }),
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

    // PERF: Single pass through jobs array instead of 5 separate .filter() calls
    const filterCounts = useMemo(() => {
        if (!jobs) {
            return { all: 0, queued: 0, processing: 0, complete: 0, failed: 0, cancelled: 0 }
        }

        const counts = { all: jobs.length, queued: 0, processing: 0, complete: 0, failed: 0, cancelled: 0 }
        for (const job of jobs) {
            const state = job.state as keyof typeof counts
            if (state in counts) {
                counts[state]++
            }
        }
        return counts
    }, [jobs])

    return (
        <div className="max-w-6xl mx-auto px-4 py-6 sm:py-8 space-y-6">
            <div>
                <h1 className="text-xl sm:text-2xl font-bold text-white">Job Queue</h1>
                <p className="text-gray-400 text-sm mt-1">Track your AI beatmap generation jobs</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 sm:gap-6">
                {/* Main content */}
                <div className="lg:col-span-3 space-y-4">
                    {/* Filters */}
                    <div className="flex flex-wrap gap-1.5 sm:gap-2">
                        {(['all', 'queued', 'processing', 'complete', 'failed'] as const).map((state) => (
                            <button
                                key={state}
                                onClick={() => setFilter(state)}
                                className={`px-3 sm:px-4 py-1.5 sm:py-2 rounded-lg text-xs sm:text-sm font-medium transition-all ${filter === state
                                    ? 'bg-primary-500 text-white'
                                    : 'bg-dark-400 text-gray-400 hover:bg-dark-300 hover:text-white'
                                    }`}
                            >
                                {state.charAt(0).toUpperCase() + state.slice(1)}
                                <span className="ml-1 sm:ml-1.5 text-xs opacity-75">
                                    ({filterCounts[state]})
                                </span>
                            </button>
                        ))}
                    </div>

                    {/* Job list */}
                    {isLoading ? (
                        <div className="space-y-4">
                            {[1, 2, 3].map((i) => (
                                <div key={i} className="bg-dark-400 rounded-xl border border-dark-300 p-4 animate-pulse">
                                    <div className="h-4 bg-dark-300 rounded w-1/4 mb-3" />
                                    <div className="h-3 bg-dark-300 rounded w-1/2 mb-2" />
                                    <div className="h-3 bg-dark-300 rounded w-1/3" />
                                </div>
                            ))}
                        </div>
                    ) : error ? (
                        <div className="bg-red-500/10 border border-red-500/20 rounded-xl text-center py-8">
                            <svg className="w-12 h-12 mx-auto text-red-400 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                            <p className="text-red-400 mb-2">Failed to load jobs</p>
                            <p className="text-gray-500 text-sm">Please check your connection and try again.</p>
                        </div>
                    ) : filteredJobs.length === 0 ? (
                        <div className="bg-dark-400 rounded-xl border border-dark-300 text-center py-12">
                            <svg className="w-16 h-16 mx-auto text-gray-600 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                            </svg>
                            <h3 className="text-lg font-medium text-white mb-2">
                                {filter === 'all' ? 'No AI jobs yet' : `No ${filter} jobs`}
                            </h3>
                            <p className="text-gray-400 mb-6">
                                {filter === 'all'
                                    ? 'Upload a song to start generating beatmaps with AI'
                                    : 'Try viewing all jobs to see your processing history'}
                            </p>
                            {filter !== 'all' ? (
                                <button
                                    onClick={() => setFilter('all')}
                                    className="px-5 py-2.5 bg-dark-300 text-white rounded-lg font-medium hover:bg-dark-200 transition-all"
                                >
                                    View All Jobs
                                </button>
                            ) : (
                                <a href="/upload" className="inline-flex items-center gap-2 px-5 py-2.5 bg-primary-500 hover:bg-primary-600 text-white rounded-lg font-medium transition-all">
                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                                    </svg>
                                    Upload Your First Song
                                </a>
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
                    <div className="bg-dark-400 rounded-xl border border-dark-300 p-4">
                        <h3 className="text-lg font-medium text-white mb-4">Queue Stats</h3>
                        <div className="space-y-3">
                            <div className="flex justify-between">
                                <span className="text-gray-400">Processing</span>
                                <span className="text-primary-400 font-medium">{filterCounts.processing}</span>
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
