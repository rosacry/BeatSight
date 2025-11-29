/**
 * React Query hooks for API data fetching.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
    listJobs,
    getJob,
    cancelJob,
    retryJob,
    getQuota,
    listSongs,
    getSong,
} from '@/api/client'

// Query keys for cache management
export const queryKeys = {
    jobs: ['jobs'] as const,
    job: (id: string) => ['jobs', id] as const,
    quota: ['quota'] as const,
    songs: ['songs'] as const,
    song: (id: string) => ['songs', id] as const,
}

// --- Job Hooks ---

export function useJobs(songId?: string) {
    return useQuery({
        queryKey: songId ? [...queryKeys.jobs, { songId }] : queryKeys.jobs,
        queryFn: () => listJobs(songId),
        refetchInterval: 10000, // Poll every 10s
        staleTime: 5000,
    })
}

export function useJob(jobId: string | undefined) {
    return useQuery({
        queryKey: jobId ? queryKeys.job(jobId) : ['job-undefined'],
        queryFn: () => (jobId ? getJob(jobId) : Promise.reject('No job ID')),
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
}

export function useCancelJob() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: cancelJob,
        onSuccess: (_, jobId) => {
            queryClient.invalidateQueries({ queryKey: queryKeys.jobs })
            queryClient.invalidateQueries({ queryKey: queryKeys.job(jobId) })
        },
    })
}

export function useRetryJob() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: retryJob,
        onSuccess: (_, jobId) => {
            queryClient.invalidateQueries({ queryKey: queryKeys.jobs })
            queryClient.invalidateQueries({ queryKey: queryKeys.job(jobId) })
        },
    })
}

// --- Quota Hook ---

export function useQuota() {
    return useQuery({
        queryKey: queryKeys.quota,
        queryFn: getQuota,
        staleTime: 30000, // Cache for 30s
        refetchInterval: 60000, // Refresh every minute
    })
}

// --- Song Hooks ---

export function useSongs() {
    return useQuery({
        queryKey: queryKeys.songs,
        queryFn: listSongs,
        staleTime: 60000,
    })
}

export function useSong(songId: string | undefined) {
    return useQuery({
        queryKey: songId ? queryKeys.song(songId) : ['song-undefined'],
        queryFn: () => (songId ? getSong(songId) : Promise.reject('No song ID')),
        enabled: !!songId,
    })
}

// --- Vote Hooks ---

import { getMapVotes, getBulkVotes } from '@/api/votes'
import type { VoteCountsResponse, BulkVoteResponse } from '@/types/votes'

export const voteQueryKeys = {
    mapVotes: (mapId: string) => ['mapVotes', mapId] as const,
    bulkVotes: (mapIds: string[]) => ['bulkVotes', mapIds.sort().join(',')] as const,
}

export function useMapVotes(mapId: string | undefined) {
    return useQuery<VoteCountsResponse>({
        queryKey: mapId ? voteQueryKeys.mapVotes(mapId) : ['mapVotes-undefined'],
        queryFn: () => (mapId ? getMapVotes(mapId) : Promise.reject('No map ID')),
        enabled: !!mapId,
        staleTime: 30000, // Cache for 30s
    })
}

export function useBulkVotes(mapIds: string[]) {
    return useQuery<BulkVoteResponse>({
        queryKey: voteQueryKeys.bulkVotes(mapIds),
        queryFn: () => getBulkVotes(mapIds),
        enabled: mapIds.length > 0,
        staleTime: 30000,
    })
}
