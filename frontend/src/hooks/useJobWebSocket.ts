/**
 * WebSocket hook for real-time job updates.
 * 
 * Connects to the backend WebSocket endpoint and provides
 * real-time progress updates for AI jobs.
 */

import { useEffect, useRef, useCallback, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useAuthStore } from '@/stores/authStore'
import { queryKeys } from '@/api/hooks'
import { createLogger } from '@/lib/logger'

const logger = createLogger('WebSocket')

export type JobUpdateType = 'job_progress' | 'job_complete' | 'job_failed' | 'subscribed' | 'unsubscribed' | 'pong'

export interface JobProgressUpdate {
    type: 'job_progress'
    job_id: string
    percent: number
    message: string | null
    stage: string | null
}

export interface JobCompleteUpdate {
    type: 'job_complete'
    job_id: string
    song_id: string
    beatmap_id: string
}

export interface JobFailedUpdate {
    type: 'job_failed'
    job_id: string
    error: string
}

export type JobUpdate = JobProgressUpdate | JobCompleteUpdate | JobFailedUpdate

interface UseJobWebSocketOptions {
    onProgress?: (update: JobProgressUpdate) => void
    onComplete?: (update: JobCompleteUpdate) => void
    onFailed?: (update: JobFailedUpdate) => void
    autoReconnect?: boolean
    reconnectInterval?: number
}

export function useJobWebSocket(options: UseJobWebSocketOptions = {}) {
    const {
        onProgress,
        onComplete,
        onFailed,
        autoReconnect = true,
        reconnectInterval = 5000,
    } = options

    const wsRef = useRef<WebSocket | null>(null)
    const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const [isConnected, setIsConnected] = useState(false)
    const [lastUpdate, setLastUpdate] = useState<JobUpdate | null>(null)

    const accessToken = useAuthStore((state) => state.accessToken)
    const queryClient = useQueryClient()

    const subscribedJobs = useRef<Set<string>>(new Set())

    const connect = useCallback(() => {
        if (!accessToken) return

        // Determine WebSocket URL
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        const wsHost = import.meta.env.VITE_WS_HOST || window.location.host
        const wsUrl = `${wsProtocol}//${wsHost}/ws/jobs?token=${accessToken}`

        const ws = new WebSocket(wsUrl)
        wsRef.current = ws

        ws.onopen = () => {
            setIsConnected(true)
            logger.info('Connected to job updates')

            // Re-subscribe to any jobs we were tracking
            subscribedJobs.current.forEach((jobId) => {
                ws.send(JSON.stringify({ type: 'subscribe', job_id: jobId }))
            })
        }

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data) as JobUpdate | { type: string }

                setLastUpdate(data as JobUpdate)

                switch (data.type) {
                    case 'job_progress': {
                        const update = data as JobProgressUpdate
                        onProgress?.(update)

                        // Update React Query cache with progress
                        queryClient.setQueryData(queryKeys.job(update.job_id), (old: unknown) => {
                            if (!old) return old
                            return {
                                ...(old as object),
                                progress_percent: update.percent,
                                progress_message: update.message,
                            }
                        })
                        break
                    }

                    case 'job_complete': {
                        const update = data as JobCompleteUpdate
                        onComplete?.(update)

                        // Invalidate queries to refetch final state
                        queryClient.invalidateQueries({ queryKey: queryKeys.job(update.job_id) })
                        queryClient.invalidateQueries({ queryKey: queryKeys.jobs })
                        queryClient.invalidateQueries({ queryKey: queryKeys.song(update.song_id) })
                        break
                    }

                    case 'job_failed': {
                        const update = data as JobFailedUpdate
                        onFailed?.(update)

                        // Invalidate to refetch error state
                        queryClient.invalidateQueries({ queryKey: queryKeys.job(update.job_id) })
                        queryClient.invalidateQueries({ queryKey: queryKeys.jobs })
                        break
                    }
                }
            } catch (err) {
                logger.error('Failed to parse message:', err)
            }
        }

        ws.onclose = (event) => {
            setIsConnected(false)
            logger.info('Disconnected:', event.code, event.reason)

            // Auto-reconnect if enabled and not a clean close
            if (autoReconnect && event.code !== 1000) {
                reconnectTimeoutRef.current = setTimeout(connect, reconnectInterval)
            }
        }

        ws.onerror = (error) => {
            logger.error('Error:', error)
        }
    }, [accessToken, autoReconnect, reconnectInterval, onProgress, onComplete, onFailed, queryClient])

    const disconnect = useCallback(() => {
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current)
            reconnectTimeoutRef.current = null
        }

        if (wsRef.current) {
            wsRef.current.close(1000, 'User disconnected')
            wsRef.current = null
        }

        setIsConnected(false)
    }, [])

    const subscribeToJob = useCallback((jobId: string) => {
        subscribedJobs.current.add(jobId)

        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'subscribe', job_id: jobId }))
        }
    }, [])

    const unsubscribeFromJob = useCallback((jobId: string) => {
        subscribedJobs.current.delete(jobId)

        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'unsubscribe', job_id: jobId }))
        }
    }, [])

    // Connect when authenticated
    useEffect(() => {
        if (accessToken) {
            connect()
        } else {
            disconnect()
        }

        return disconnect
    }, [accessToken, connect, disconnect])

    // Ping to keep connection alive
    useEffect(() => {
        if (!isConnected) return

        const pingInterval = setInterval(() => {
            if (wsRef.current?.readyState === WebSocket.OPEN) {
                wsRef.current.send(JSON.stringify({ type: 'ping' }))
            }
        }, 30000)

        return () => clearInterval(pingInterval)
    }, [isConnected])

    return {
        isConnected,
        lastUpdate,
        subscribeToJob,
        unsubscribeFromJob,
        connect,
        disconnect,
    }
}
