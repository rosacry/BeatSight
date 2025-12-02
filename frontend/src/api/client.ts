/**
 * API client for BeatSight backend.
 */

import type { AIJob, AIJobEnqueueResponse, QuotaStatus, Song } from '@/types/api'
import { getAccessToken } from '@/stores/authStore'

const API_BASE = '/api'

class APIError extends Error {
    constructor(public status: number, message: string) {
        super(message)
        this.name = 'APIError'
    }
}

async function request<T>(
    endpoint: string,
    options: RequestInit = {},
    requireAuth: boolean = false
): Promise<T> {
    const url = `${API_BASE}${endpoint}`

    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
    }

    // Add auth header if available
    const token = getAccessToken()
    if (token) {
        headers['Authorization'] = `Bearer ${token}`
    } else if (requireAuth) {
        throw new APIError(401, 'Authentication required')
    }

    const response = await fetch(url, {
        ...options,
        headers: {
            ...headers,
            ...options.headers,
        },
    })

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
        throw new APIError(response.status, error.detail || 'Request failed')
    }

    return response.json()
}

// --- AI Jobs API ---

export async function listJobs(songId?: string): Promise<AIJob[]> {
    const params = songId ? `?song_id=${songId}` : ''
    return request<AIJob[]>(`/ai-jobs${params}`)
}

export async function getJob(jobId: string): Promise<AIJob> {
    return request<AIJob>(`/ai-jobs/${jobId}`)
}

export async function enqueueJob(
    songId: string,
    priority: 'standard' | 'priority' = 'standard'
): Promise<AIJobEnqueueResponse> {
    return request<AIJobEnqueueResponse>('/ai-jobs', {
        method: 'POST',
        body: JSON.stringify({ song_id: songId, priority }),
    })
}

export async function cancelJob(jobId: string): Promise<void> {
    await request(`/ai-jobs/${jobId}/cancel`, { method: 'POST' })
}

export async function getQuota(): Promise<QuotaStatus> {
    return request<QuotaStatus>('/ai-jobs/quota')
}

export async function getQueueLength(): Promise<{ queue_length: number }> {
    return request<{ queue_length: number }>('/ai-jobs/queue-length')
}

export async function retryJob(jobId: string): Promise<AIJob> {
    return request<AIJob>(`/ai-jobs/${jobId}/retry`, { method: 'POST' })
}

export interface CreateJobRequest {
    audio_key: string
    priority?: number
}

export async function createJob(data: CreateJobRequest): Promise<AIJob> {
    return request<AIJob>('/ai-jobs', {
        method: 'POST',
        body: JSON.stringify(data),
    })
}

// --- Storage API ---

export interface UploadResponse {
    key: string
    url: string
    size: number
}

export async function uploadFile(file: File, category: string): Promise<UploadResponse> {
    const formData = new FormData()
    formData.append('file', file)

    const headers: Record<string, string> = {}
    const token = getAccessToken()
    if (token) {
        headers['Authorization'] = `Bearer ${token}`
    }

    const response = await fetch(`${API_BASE}/storage/upload/${category}`, {
        method: 'POST',
        body: formData,
        headers,
    })

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Upload failed' }))
        throw new APIError(response.status, error.detail || 'Upload failed')
    }

    return response.json()
}

/**
 * Upload file with real progress tracking via XMLHttpRequest.
 * Use this when you need accurate upload progress feedback.
 */
export function uploadFileWithProgress(
    file: File,
    category: string,
    onProgress: (percent: number) => void
): Promise<UploadResponse> {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest()
        const formData = new FormData()
        formData.append('file', file)

        // Track upload progress
        xhr.upload.addEventListener('progress', (event) => {
            if (event.lengthComputable) {
                const percentComplete = Math.round((event.loaded / event.total) * 100)
                onProgress(percentComplete)
            }
        })

        // Handle completion
        xhr.addEventListener('load', () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                try {
                    const response = JSON.parse(xhr.responseText)
                    resolve(response)
                } catch {
                    reject(new APIError(xhr.status, 'Invalid response format'))
                }
            } else {
                try {
                    const error = JSON.parse(xhr.responseText)
                    reject(new APIError(xhr.status, error.detail || 'Upload failed'))
                } catch {
                    reject(new APIError(xhr.status, 'Upload failed'))
                }
            }
        })

        // Handle errors
        xhr.addEventListener('error', () => {
            reject(new APIError(0, 'Network error during upload'))
        })

        xhr.addEventListener('abort', () => {
            reject(new APIError(0, 'Upload cancelled'))
        })

        // Configure and send request
        xhr.open('POST', `${API_BASE}/storage/upload/${category}`)

        const token = getAccessToken()
        if (token) {
            xhr.setRequestHeader('Authorization', `Bearer ${token}`)
        }

        xhr.send(formData)
    })
}

export async function getPresignedUploadUrl(
    category: string,
    filename: string,
    contentType: string
): Promise<{ url: string; key: string }> {
    return request<{ url: string; key: string }>('/storage/presigned-upload', {
        method: 'POST',
        body: JSON.stringify({ category, filename, content_type: contentType }),
    })
}

export async function getPresignedDownloadUrl(key: string): Promise<{ url: string }> {
    return request<{ url: string }>('/storage/presigned-download', {
        method: 'POST',
        body: JSON.stringify({ key }),
    })
}

// --- Songs API ---

export async function listSongs(): Promise<Song[]> {
    return request<Song[]>('/songs')
}

export async function getSong(songId: string): Promise<Song> {
    return request<Song>(`/songs/${songId}`)
}

// --- SSE Streaming ---

export interface JobProgressUpdate {
    percent: number
    message: string | null
    stage: string | null
    timestamp?: string
}

export interface JobCompleteEvent {
    job_id: string
    status: 'completed' | 'cancelled'
    beatmap_id?: string
}

export interface JobErrorEvent {
    job_id?: string
    message: string
    status?: string
    error?: string
}

/**
 * Subscribe to real-time job progress updates via Server-Sent Events.
 * 
 * The backend sends the following event types:
 * - `status`: Initial job status when connecting
 * - `progress`: Progress updates (percent, message, stage)
 * - `complete`: Job completed successfully (includes beatmap_id)
 * - `error`: Job failed or was cancelled
 * - `timeout`: Connection closed due to inactivity
 * 
 * @param jobId - The job ID to subscribe to
 * @param onProgress - Called on progress updates
 * @param onComplete - Called when job completes successfully
 * @param onError - Called on errors or connection issues
 * @returns Cleanup function to close the connection
 */
export function subscribeToJobProgress(
    jobId: string,
    onProgress: (update: JobProgressUpdate) => void,
    onComplete: (event?: JobCompleteEvent) => void,
    onError: (error: Error) => void
): () => void {
    const url = `${API_BASE}/ai-jobs/${jobId}/progress/stream`
    const eventSource = new EventSource(url)

    // Handle initial status event
    eventSource.addEventListener('status', (event: MessageEvent) => {
        try {
            const data = JSON.parse(event.data)
            onProgress({
                percent: data.percent ?? 0,
                message: data.message ?? null,
                stage: null,
            })
        } catch (e) {
            console.error('Failed to parse SSE status message:', e)
        }
    })

    // Handle progress updates
    eventSource.addEventListener('progress', (event: MessageEvent) => {
        try {
            const data = JSON.parse(event.data)
            onProgress({
                percent: data.percent,
                message: data.message ?? null,
                stage: data.stage ?? null,
                timestamp: data.timestamp,
            })
        } catch (e) {
            console.error('Failed to parse SSE progress message:', e)
        }
    })

    // Handle completion
    eventSource.addEventListener('complete', (event: MessageEvent) => {
        try {
            const data = JSON.parse(event.data) as JobCompleteEvent
            onComplete(data)
        } catch {
            onComplete()
        }
        eventSource.close()
    })

    // Handle errors from the server
    eventSource.addEventListener('error', (event: MessageEvent) => {
        try {
            const data = JSON.parse(event.data) as JobErrorEvent
            onError(new Error(data.message || data.error || 'Job failed'))
        } catch {
            onError(new Error('Job processing failed'))
        }
        eventSource.close()
    })

    // Handle timeout
    eventSource.addEventListener('timeout', (event: MessageEvent) => {
        try {
            const data = JSON.parse(event.data)
            onError(new Error(data.message || 'Connection timed out'))
        } catch {
            onError(new Error('Connection timed out'))
        }
        eventSource.close()
    })

    // Handle connection errors
    eventSource.onerror = () => {
        onError(new Error('Connection lost'))
        eventSource.close()
    }

    // Return cleanup function
    return () => {
        eventSource.close()
    }
}

export { APIError }
