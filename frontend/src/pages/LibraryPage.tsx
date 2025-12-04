/**
 * User's song library page.
 * Shows uploaded songs and their processing status.
 */

import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { listSongs, listJobs } from '@/api/client'
import { JobStatusBadge } from '@/components/JobStatusBadge'
import type { Song, AIJob } from '@/types/api'

type SortOption = 'recent' | 'title' | 'artist' | 'status'
type FilterOption = 'all' | 'complete' | 'processing' | 'failed'

export function LibraryPage() {
    const [sortBy, setSortBy] = useState<SortOption>('recent')
    const [filterBy, setFilterBy] = useState<FilterOption>('all')
    const [searchQuery, setSearchQuery] = useState('')

    const { data: songs, isLoading: songsLoading } = useQuery({
        queryKey: ['songs'],
        queryFn: () => listSongs({ pageSize: 100 }),
    })

    const { data: jobs } = useQuery({
        queryKey: ['jobs'],
        queryFn: () => listJobs({ pageSize: 100 }),
    })

    // Create a map of song ID to latest job
    // PERF: Memoized to avoid recomputing on every render
    const songJobMap = useMemo(() => {
        const map = new Map<string, AIJob>()
        if (!jobs) return map

        // Sort jobs by created_at descending once, then just take first per song
        // This avoids creating Date objects for every comparison
        const sortedJobs = [...jobs].sort((a, b) =>
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        )

        for (const job of sortedJobs) {
            if (!map.has(job.song_id)) {
                map.set(job.song_id, job)
            }
        }
        return map
    }, [jobs])

    // Filter and sort songs
    // PERF: Memoized with all dependencies to avoid expensive filter/sort on every render
    const filteredSongs = useMemo(() => {
        const queryLower = searchQuery.toLowerCase()

        return (songs || [])
            .filter((song) => {
                // Search filter
                if (searchQuery) {
                    const titleMatch = song.title.toLowerCase().includes(queryLower)
                    const artistMatch = song.artist.toLowerCase().includes(queryLower)
                    if (!titleMatch && !artistMatch) {
                        return false
                    }
                }

                // Status filter
                if (filterBy !== 'all') {
                    const job = songJobMap.get(song.id)
                    if (filterBy === 'complete' && job?.state !== 'complete') return false
                    if (filterBy === 'processing' && job?.state !== 'processing' && job?.state !== 'queued') return false
                    if (filterBy === 'failed' && job?.state !== 'failed') return false
                }

                return true
            })
            .sort((a, b) => {
                switch (sortBy) {
                    case 'title':
                        return a.title.localeCompare(b.title)
                    case 'artist':
                        return a.artist.localeCompare(b.artist)
                    case 'status': {
                        const jobA = songJobMap.get(a.id)
                        const jobB = songJobMap.get(b.id)
                        const statusOrder = { complete: 0, processing: 1, queued: 2, failed: 3 }
                        const orderA = jobA ? statusOrder[jobA.state as keyof typeof statusOrder] ?? 4 : 4
                        const orderB = jobB ? statusOrder[jobB.state as keyof typeof statusOrder] ?? 4 : 4
                        return orderA - orderB
                    }
                    case 'recent':
                    default:
                        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
                }
            })
    }, [songs, searchQuery, filterBy, sortBy, songJobMap])

    if (songsLoading) {
        return (
            <div className="flex items-center justify-center min-h-[60vh]">
                <div className="flex flex-col items-center gap-4">
                    <svg className="animate-spin h-8 w-8 text-primary-500" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    <p className="text-gray-400">Loading your library...</p>
                </div>
            </div>
        )
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-white">My Library</h1>
                    <p className="text-gray-400 mt-1">
                        {filteredSongs.length} {filteredSongs.length === 1 ? 'song' : 'songs'}
                    </p>
                </div>
                <Link to="/upload" className="btn btn-primary flex items-center gap-2 w-fit">
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    Upload Song
                </Link>
            </div>

            {/* Filters */}
            <div className="flex flex-col sm:flex-row gap-4">
                {/* Search */}
                <div className="flex-1">
                    <input
                        type="text"
                        placeholder="Search by title or artist..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="input"
                    />
                </div>

                {/* Sort */}
                <select
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value as SortOption)}
                    className="input w-full sm:w-40"
                >
                    <option value="recent">Most Recent</option>
                    <option value="title">Title</option>
                    <option value="artist">Artist</option>
                    <option value="status">Status</option>
                </select>

                {/* Filter */}
                <select
                    value={filterBy}
                    onChange={(e) => setFilterBy(e.target.value as FilterOption)}
                    className="input w-full sm:w-40"
                >
                    <option value="all">All Songs</option>
                    <option value="complete">Complete</option>
                    <option value="processing">Processing</option>
                    <option value="failed">Failed</option>
                </select>
            </div>

            {/* Song List */}
            {filteredSongs.length === 0 ? (
                <div className="card text-center py-12">
                    <svg className="w-16 h-16 mx-auto text-gray-600 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
                    </svg>
                    <h3 className="text-lg font-medium text-white mb-2">No songs found</h3>
                    <p className="text-gray-400 mb-6">
                        {searchQuery || filterBy !== 'all'
                            ? 'Try adjusting your search or filters'
                            : 'Upload your first song to get started'}
                    </p>
                    {!searchQuery && filterBy === 'all' && (
                        <Link to="/upload" className="btn btn-primary">
                            Upload Song
                        </Link>
                    )}
                </div>
            ) : (
                <div className="grid gap-4">
                    {filteredSongs.map((song) => (
                        <SongCard key={song.id} song={song} job={songJobMap.get(song.id)} />
                    ))}
                </div>
            )}
        </div>
    )
}

interface SongCardProps {
    song: Song
    job?: AIJob
}

function SongCard({ song, job }: SongCardProps) {
    return (
        <div className="card hover:bg-gray-750 transition-colors">
            <div className="flex items-center gap-4">
                {/* Album art placeholder */}
                <div className="w-16 h-16 bg-gray-700 rounded-lg flex items-center justify-center flex-shrink-0">
                    <svg className="w-8 h-8 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
                    </svg>
                </div>

                {/* Song info */}
                <div className="flex-1 min-w-0">
                    <h3 className="text-white font-medium truncate">{song.title}</h3>
                    <p className="text-gray-400 text-sm truncate">{song.artist}</p>
                    {song.bpm && (
                        <p className="text-gray-500 text-xs mt-1">{song.bpm} BPM</p>
                    )}
                </div>

                {/* Status and actions */}
                <div className="flex items-center gap-4">
                    {job && <JobStatusBadge state={job.state} />}

                    {job?.state === 'complete' ? (
                        <Link
                            to={`/jobs/${job.id}`}
                            className="btn btn-secondary text-sm"
                        >
                            View Beatmap
                        </Link>
                    ) : job?.state === 'processing' || job?.state === 'queued' ? (
                        <Link
                            to={`/jobs/${job.id}`}
                            className="btn btn-secondary text-sm"
                        >
                            View Progress
                        </Link>
                    ) : (
                        <Link
                            to={`/upload?song=${song.id}`}
                            className="btn btn-primary text-sm"
                        >
                            Generate
                        </Link>
                    )}
                </div>
            </div>
        </div>
    )
}
