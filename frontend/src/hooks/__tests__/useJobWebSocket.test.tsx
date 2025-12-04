/**
 * Tests for useJobWebSocket hook.
 * Tests WebSocket connection, message handling, and reconnection logic.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactNode } from 'react'
import { useJobWebSocket, JobProgressUpdate, JobCompleteUpdate, JobFailedUpdate } from '../useJobWebSocket'

// Mock the auth store
const mockAccessToken = { current: 'test-token' }
vi.mock('@/stores/authStore', () => ({
    useAuthStore: vi.fn((selector) => {
        const state = { accessToken: mockAccessToken.current }
        return selector(state)
    }),
}))

// Mock logger
vi.mock('@/lib/logger', () => ({
    createLogger: () => ({
        info: vi.fn(),
        error: vi.fn(),
        warn: vi.fn(),
        debug: vi.fn(),
    }),
}))

import { useAuthStore } from '@/stores/authStore'

// Store WebSocket instances for testing
let wsInstances: MockWebSocket[] = []

// Mock WebSocket
class MockWebSocket {
    static CONNECTING = 0
    static OPEN = 1
    static CLOSING = 2
    static CLOSED = 3

    url: string
    readyState: number = MockWebSocket.CONNECTING
    onopen: ((event: Event) => void) | null = null
    onclose: ((event: CloseEvent) => void) | null = null
    onmessage: ((event: MessageEvent) => void) | null = null
    onerror: ((event: Event) => void) | null = null

    private sentMessages: string[] = []

    constructor(url: string) {
        this.url = url
        wsInstances.push(this)
    }

    send(data: string) {
        this.sentMessages.push(data)
    }

    close(code?: number, reason?: string) {
        this.readyState = MockWebSocket.CLOSED
        if (this.onclose) {
            this.onclose(new CloseEvent('close', { code: code || 1000, reason }))
        }
    }

    // Test helpers
    simulateOpen() {
        this.readyState = MockWebSocket.OPEN
        if (this.onopen) {
            this.onopen(new Event('open'))
        }
    }

    simulateMessage(data: unknown) {
        if (this.onmessage) {
            this.onmessage(new MessageEvent('message', { data: JSON.stringify(data) }))
        }
    }

    simulateClose(code = 1006, reason = '') {
        this.readyState = MockWebSocket.CLOSED
        if (this.onclose) {
            this.onclose(new CloseEvent('close', { code, reason }))
        }
    }

    getSentMessages() {
        return this.sentMessages
    }
}

function getLastWsInstance(): MockWebSocket | undefined {
    return wsInstances[wsInstances.length - 1]
}

// Replace global WebSocket using vi.stubGlobal
beforeEach(() => {
    wsInstances = []
    mockAccessToken.current = 'test-token'
    vi.stubGlobal('WebSocket', MockWebSocket)
})

afterEach(() => {
    vi.unstubAllGlobals()
    vi.clearAllMocks()
})

// Test wrapper with QueryClient
function createWrapper() {
    const queryClient = new QueryClient({
        defaultOptions: {
            queries: { retry: false },
        },
    })
    return function Wrapper({ children }: { children: ReactNode }) {
        return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    }
}

describe('useJobWebSocket', () => {
    describe('Connection', () => {
        it('creates WebSocket when authenticated', async () => {
            renderHook(() => useJobWebSocket(), {
                wrapper: createWrapper(),
            })

            expect(wsInstances.length).toBe(1)
            expect(getLastWsInstance()?.url).toContain('token=test-token')
        })

        it('does not connect when not authenticated', () => {
            mockAccessToken.current = null as unknown as string

            renderHook(() => useJobWebSocket(), {
                wrapper: createWrapper(),
            })

            expect(wsInstances.length).toBe(0)
        })

        it('reports isConnected after open', async () => {
            const { result } = renderHook(() => useJobWebSocket(), {
                wrapper: createWrapper(),
            })

            expect(result.current.isConnected).toBe(false)

            act(() => {
                getLastWsInstance()?.simulateOpen()
            })

            await waitFor(() => {
                expect(result.current.isConnected).toBe(true)
            })
        })
    })

    describe('Message Handling', () => {
        it('handles job_progress updates', async () => {
            const onProgress = vi.fn()
            const { result } = renderHook(
                () => useJobWebSocket({ onProgress }),
                { wrapper: createWrapper() }
            )

            act(() => {
                getLastWsInstance()?.simulateOpen()
            })

            const progressUpdate: JobProgressUpdate = {
                type: 'job_progress',
                job_id: 'job-123',
                percent: 50,
                message: 'Processing audio...',
                stage: 'separation',
            }

            act(() => {
                getLastWsInstance()?.simulateMessage(progressUpdate)
            })

            await waitFor(() => {
                expect(onProgress).toHaveBeenCalledWith(progressUpdate)
            })
            expect(result.current.lastUpdate).toEqual(progressUpdate)
        })

        it('handles job_complete updates', async () => {
            const onComplete = vi.fn()
            const { result } = renderHook(
                () => useJobWebSocket({ onComplete }),
                { wrapper: createWrapper() }
            )

            act(() => {
                getLastWsInstance()?.simulateOpen()
            })

            const completeUpdate: JobCompleteUpdate = {
                type: 'job_complete',
                job_id: 'job-123',
                song_id: 'song-456',
                beatmap_id: 'beatmap-789',
            }

            act(() => {
                getLastWsInstance()?.simulateMessage(completeUpdate)
            })

            await waitFor(() => {
                expect(onComplete).toHaveBeenCalledWith(completeUpdate)
            })
            expect(result.current.lastUpdate).toEqual(completeUpdate)
        })

        it('handles job_failed updates', async () => {
            const onFailed = vi.fn()
            const { result } = renderHook(
                () => useJobWebSocket({ onFailed }),
                { wrapper: createWrapper() }
            )

            act(() => {
                getLastWsInstance()?.simulateOpen()
            })

            const failedUpdate: JobFailedUpdate = {
                type: 'job_failed',
                job_id: 'job-123',
                error: 'Processing failed: out of memory',
            }

            act(() => {
                getLastWsInstance()?.simulateMessage(failedUpdate)
            })

            await waitFor(() => {
                expect(onFailed).toHaveBeenCalledWith(failedUpdate)
            })
            expect(result.current.lastUpdate).toEqual(failedUpdate)
        })
    })

    describe('Job Subscription', () => {
        it('sends subscribe message when subscribeToJob is called', async () => {
            const { result } = renderHook(() => useJobWebSocket(), {
                wrapper: createWrapper(),
            })

            act(() => {
                getLastWsInstance()?.simulateOpen()
            })

            act(() => {
                result.current.subscribeToJob('job-123')
            })

            const messages = getLastWsInstance()?.getSentMessages() || []
            expect(messages).toContainEqual(
                JSON.stringify({ type: 'subscribe', job_id: 'job-123' })
            )
        })

        it('sends unsubscribe message when unsubscribeFromJob is called', async () => {
            const { result } = renderHook(() => useJobWebSocket(), {
                wrapper: createWrapper(),
            })

            act(() => {
                getLastWsInstance()?.simulateOpen()
            })

            act(() => {
                result.current.subscribeToJob('job-123')
                result.current.unsubscribeFromJob('job-123')
            })

            const messages = getLastWsInstance()?.getSentMessages() || []
            expect(messages).toContainEqual(
                JSON.stringify({ type: 'unsubscribe', job_id: 'job-123' })
            )
        })
    })

    describe('Reconnection', () => {
        it('auto-reconnects after unexpected disconnect', async () => {
            vi.useFakeTimers()

            renderHook(() => useJobWebSocket({ autoReconnect: true, reconnectInterval: 1000 }), {
                wrapper: createWrapper(),
            })

            const firstWsCount = wsInstances.length

            act(() => {
                getLastWsInstance()?.simulateOpen()
            })

            // Simulate unexpected disconnect
            act(() => {
                getLastWsInstance()?.simulateClose(1006, 'Abnormal closure')
            })

            // Advance time past reconnect interval
            await act(async () => {
                vi.advanceTimersByTime(1500)
            })

            // Should have created a new WebSocket
            expect(wsInstances.length).toBeGreaterThan(firstWsCount)

            vi.useRealTimers()
        })

        it('does not reconnect when autoReconnect is false', async () => {
            vi.useFakeTimers()

            renderHook(() => useJobWebSocket({ autoReconnect: false }), {
                wrapper: createWrapper(),
            })

            const initialCount = wsInstances.length

            act(() => {
                getLastWsInstance()?.simulateOpen()
            })

            // Simulate disconnect
            act(() => {
                getLastWsInstance()?.simulateClose(1006, 'Abnormal closure')
            })

            // Advance time
            await act(async () => {
                vi.advanceTimersByTime(10000)
            })

            // Should not have reconnected
            expect(wsInstances.length).toBe(initialCount)

            vi.useRealTimers()
        })
    })

    describe('Hook API', () => {
        it('provides connect and disconnect methods', () => {
            const { result } = renderHook(() => useJobWebSocket(), {
                wrapper: createWrapper(),
            })

            expect(typeof result.current.connect).toBe('function')
            expect(typeof result.current.disconnect).toBe('function')
            expect(typeof result.current.subscribeToJob).toBe('function')
            expect(typeof result.current.unsubscribeFromJob).toBe('function')
        })

        it('exposes lastUpdate state', () => {
            const { result } = renderHook(() => useJobWebSocket(), {
                wrapper: createWrapper(),
            })

            expect(result.current.lastUpdate).toBe(null)
        })
    })
})

