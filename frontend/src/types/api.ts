/**
 * API types matching backend schemas.
 */

export type AIJobState = 'queued' | 'processing' | 'complete' | 'failed' | 'cancelled'
export type AIJobPriority = 'standard' | 'priority'

export interface AIJob {
    id: string
    song_id: string
    state: AIJobState
    priority: AIJobPriority
    error_message: string | null
    requested_by_id: string | null
    started_at: string | null
    finished_at: string | null
    created_at: string
    worker_id: string | null
    last_heartbeat: string | null
    progress_percent: number | null
    progress_message: string | null
    retry_count?: number
    max_retries?: number
}

export interface QuotaStatus {
    plan: string | null
    used_this_month: number
    used_today: number
    remaining_month: number
    remaining_today: number
    limit_month: number
    limit_day: number
    resets_at: string | null
    priority: number
}

export interface AIJobEnqueueResponse {
    job: AIJob
    queue_position: number | null
    estimated_wait_minutes: number | null
    quota: QuotaStatus
}

export interface ProgressUpdate {
    job_id: string
    percent: number
    message: string | null
    stage: string | null
    timestamp: string
}

export interface Song {
    id: string
    title: string
    artist: string
    bpm: number | null
    status: string
    canonical_map_id: string | null
    created_at: string
    updated_at: string
}

export interface APIError {
    detail: string
}
