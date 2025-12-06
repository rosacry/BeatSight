/**
 * Enhanced fetch utilities with timeout, retry, and error handling.
 * @module lib/fetch
 */

import { getAccessToken, useAuthStore } from '@/stores/authStore'

/** Default request timeout in milliseconds */
const DEFAULT_TIMEOUT = 30000

/** Default number of retries for transient errors */
const DEFAULT_RETRIES = 3

/** Base delay between retries in milliseconds (exponential backoff) */
const RETRY_BASE_DELAY = 1000

/** HTTP status codes that should trigger a retry */
const RETRYABLE_STATUS_CODES = new Set([408, 429, 500, 502, 503, 504])

/** Error types that should trigger a retry */
const RETRYABLE_ERROR_NAMES = new Set(['AbortError', 'TypeError', 'NetworkError'])

export class APIError extends Error {
    constructor(
        public status: number,
        message: string,
        public code?: string,
        public details?: unknown
    ) {
        super(message)
        this.name = 'APIError'
    }

    /** Check if this error is retryable */
    get isRetryable(): boolean {
        return RETRYABLE_STATUS_CODES.has(this.status)
    }

    /** Check if this is an authentication error */
    get isAuthError(): boolean {
        return this.status === 401
    }

    /** Check if this is a rate limit error */
    get isRateLimited(): boolean {
        return this.status === 429
    }
}

export interface RequestOptions extends Omit<RequestInit, 'signal'> {
    /** Request timeout in milliseconds */
    timeout?: number
    /** Number of retry attempts for transient errors */
    retries?: number
    /** Whether authentication is required */
    requireAuth?: boolean
    /** Skip automatic token refresh on 401 */
    skipTokenRefresh?: boolean
}

interface RetryState {
    attempt: number
    maxRetries: number
    lastError?: Error
}

/**
 * Sleep for the specified duration
 */
function sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms))
}

/**
 * Calculate exponential backoff delay with jitter
 */
function getBackoffDelay(attempt: number, baseDelay: number = RETRY_BASE_DELAY): number {
    const exponentialDelay = baseDelay * Math.pow(2, attempt)
    const jitter = Math.random() * 0.3 * exponentialDelay // 0-30% jitter
    return Math.min(exponentialDelay + jitter, 30000) // Cap at 30 seconds
}

/**
 * Check if an error should trigger a retry
 */
function shouldRetry(error: unknown, retryState: RetryState): boolean {
    if (retryState.attempt >= retryState.maxRetries) {
        return false
    }

    if (error instanceof APIError) {
        return error.isRetryable
    }

    if (error instanceof Error) {
        // Retry on network errors
        if (RETRYABLE_ERROR_NAMES.has(error.name)) {
            return true
        }
        // Retry on fetch aborts (timeout)
        if (error.message.includes('aborted') || error.message.includes('timeout')) {
            return true
        }
    }

    return false
}

/**
 * Enhanced fetch with timeout support
 */
async function fetchWithTimeout(
    url: string,
    options: RequestInit,
    timeout: number
): Promise<Response> {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeout)

    try {
        const response = await fetch(url, {
            ...options,
            signal: controller.signal,
        })
        return response
    } finally {
        clearTimeout(timeoutId)
    }
}

/**
 * Make an authenticated API request with retry and timeout support
 */
export async function request<T>(
    endpoint: string,
    options: RequestOptions = {}
): Promise<T> {
    const {
        timeout = DEFAULT_TIMEOUT,
        retries = DEFAULT_RETRIES,
        requireAuth = false,
        skipTokenRefresh = false,
        ...fetchOptions
    } = options

    const url = endpoint.startsWith('http') ? endpoint : `/api${endpoint}`

    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        ...(fetchOptions.headers as Record<string, string> || {}),
    }

    // Add auth header if available
    const token = getAccessToken()
    if (token) {
        headers['Authorization'] = `Bearer ${token}`
    } else if (requireAuth) {
        throw new APIError(401, 'Authentication required', 'AUTH_REQUIRED')
    }

    const retryState: RetryState = {
        attempt: 0,
        maxRetries: retries,
    }

    while (true) {
        try {
            const response = await fetchWithTimeout(
                url,
                {
                    ...fetchOptions,
                    headers,
                },
                timeout
            )

            // Handle 401 with token refresh
            if (response.status === 401 && !skipTokenRefresh && token) {
                const authStore = useAuthStore.getState()
                try {
                    await authStore.refreshTokens()
                    // Retry with new token
                    const newToken = getAccessToken()
                    if (newToken) {
                        headers['Authorization'] = `Bearer ${newToken}`
                        retryState.attempt = 0 // Reset retry counter for auth retry
                        continue
                    }
                } catch {
                    // Refresh failed, logout and throw
                    authStore.logout()
                    throw new APIError(401, 'Session expired', 'SESSION_EXPIRED')
                }
            }

            if (!response.ok) {
                const errorBody = await response.json().catch(() => ({ detail: 'Unknown error' }))
                throw new APIError(
                    response.status,
                    errorBody.detail || errorBody.message || 'Request failed',
                    errorBody.code,
                    errorBody
                )
            }

            // Handle empty responses
            const contentType = response.headers.get('content-type')
            if (!contentType || !contentType.includes('application/json')) {
                return undefined as T
            }

            return response.json()
        } catch (error) {
            retryState.lastError = error as Error

            if (shouldRetry(error, retryState)) {
                const delay = getBackoffDelay(retryState.attempt)
                retryState.attempt++

                if (import.meta.env.DEV) {
                    console.warn(
                        `[API] Request failed, retrying (${retryState.attempt}/${retryState.maxRetries})`,
                        { url, error, delay }
                    )
                }

                await sleep(delay)
                continue
            }

            // Don't retry - re-throw the error
            throw error
        }
    }
}

/**
 * Make a GET request
 */
export function get<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    return request<T>(endpoint, { ...options, method: 'GET' })
}

/**
 * Make a POST request
 */
export function post<T>(endpoint: string, data?: unknown, options?: RequestOptions): Promise<T> {
    return request<T>(endpoint, {
        ...options,
        method: 'POST',
        body: data ? JSON.stringify(data) : undefined,
    })
}

/**
 * Make a PUT request
 */
export function put<T>(endpoint: string, data?: unknown, options?: RequestOptions): Promise<T> {
    return request<T>(endpoint, {
        ...options,
        method: 'PUT',
        body: data ? JSON.stringify(data) : undefined,
    })
}

/**
 * Make a PATCH request
 */
export function patch<T>(endpoint: string, data?: unknown, options?: RequestOptions): Promise<T> {
    return request<T>(endpoint, {
        ...options,
        method: 'PATCH',
        body: data ? JSON.stringify(data) : undefined,
    })
}

/**
 * Make a DELETE request
 */
export function del<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    return request<T>(endpoint, { ...options, method: 'DELETE' })
}

/**
 * Upload a file with progress tracking
 */
export async function uploadFile(
    endpoint: string,
    file: File,
    options?: {
        fieldName?: string
        additionalData?: Record<string, string>
        onProgress?: (progress: number) => void
        timeout?: number
    }
): Promise<unknown> {
    const {
        fieldName = 'file',
        additionalData = {},
        onProgress,
        timeout = 300000, // 5 minutes for uploads
    } = options || {}

    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest()
        const formData = new FormData()

        formData.append(fieldName, file)
        Object.entries(additionalData).forEach(([key, value]) => {
            formData.append(key, value)
        })

        xhr.upload.addEventListener('progress', (event) => {
            if (event.lengthComputable && onProgress) {
                onProgress((event.loaded / event.total) * 100)
            }
        })

        xhr.addEventListener('load', () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                try {
                    resolve(JSON.parse(xhr.responseText))
                } catch {
                    resolve(xhr.responseText)
                }
            } else {
                try {
                    const error = JSON.parse(xhr.responseText)
                    reject(new APIError(xhr.status, error.detail || 'Upload failed', error.code))
                } catch {
                    reject(new APIError(xhr.status, 'Upload failed'))
                }
            }
        })

        xhr.addEventListener('error', () => {
            reject(new APIError(0, 'Network error during upload'))
        })

        xhr.addEventListener('timeout', () => {
            reject(new APIError(408, 'Upload timed out'))
        })

        xhr.timeout = timeout

        const url = endpoint.startsWith('http') ? endpoint : `/api${endpoint}`
        xhr.open('POST', url)

        const token = getAccessToken()
        if (token) {
            xhr.setRequestHeader('Authorization', `Bearer ${token}`)
        }

        xhr.send(formData)
    })
}
