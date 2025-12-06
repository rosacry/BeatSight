/**
 * Debounce and throttle utilities for React.
 * 
 * Usage:
 *   // Debounce a value (e.g., search input)
 *   const debouncedSearch = useDebounce(searchTerm, 300)
 *   
 *   // Debounce a callback
 *   const debouncedSave = useDebouncedCallback(save, 500)
 *   
 *   // Throttle a callback (e.g., scroll handler)
 *   const throttledScroll = useThrottledCallback(onScroll, 100)
 * 
 * @module hooks/useDebounce
 */

import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Debounce a value - returns the value after it stops changing for `delay` ms.
 * 
 * @param value - The value to debounce
 * @param delay - Delay in milliseconds (default: 300)
 * @returns The debounced value
 * 
 * @example
 * const [search, setSearch] = useState('')
 * const debouncedSearch = useDebounce(search, 300)
 * 
 * useEffect(() => {
 *   if (debouncedSearch) fetchResults(debouncedSearch)
 * }, [debouncedSearch])
 */
export function useDebounce<T>(value: T, delay = 300): T {
    const [debouncedValue, setDebouncedValue] = useState<T>(value)

    useEffect(() => {
        const timer = setTimeout(() => {
            setDebouncedValue(value)
        }, delay)

        return () => {
            clearTimeout(timer)
        }
    }, [value, delay])

    return debouncedValue
}

/**
 * Create a debounced callback function.
 * 
 * @param callback - The function to debounce
 * @param delay - Delay in milliseconds (default: 300)
 * @returns A debounced version of the callback
 * 
 * @example
 * const handleSearch = useDebouncedCallback((query: string) => {
 *   fetchResults(query)
 * }, 300)
 * 
 * <input onChange={(e) => handleSearch(e.target.value)} />
 */
export function useDebouncedCallback<T extends (...args: unknown[]) => unknown>(
    callback: T,
    delay = 300
): (...args: Parameters<T>) => void {
    const callbackRef = useRef(callback)
    const timeoutRef = useRef<ReturnType<typeof setTimeout>>()

    // Keep callback ref up to date
    useEffect(() => {
        callbackRef.current = callback
    }, [callback])

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current)
            }
        }
    }, [])

    return useCallback(
        (...args: Parameters<T>) => {
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current)
            }
            timeoutRef.current = setTimeout(() => {
                callbackRef.current(...args)
            }, delay)
        },
        [delay]
    )
}

/**
 * Create a throttled callback function.
 * Unlike debounce, throttle ensures the function is called at most once per `delay` ms.
 * 
 * @param callback - The function to throttle
 * @param delay - Minimum time between calls in milliseconds (default: 100)
 * @returns A throttled version of the callback
 * 
 * @example
 * const handleScroll = useThrottledCallback(() => {
 *   updateScrollPosition(window.scrollY)
 * }, 100)
 * 
 * useEffect(() => {
 *   window.addEventListener('scroll', handleScroll)
 *   return () => window.removeEventListener('scroll', handleScroll)
 * }, [handleScroll])
 */
export function useThrottledCallback<T extends (...args: unknown[]) => unknown>(
    callback: T,
    delay = 100
): (...args: Parameters<T>) => void {
    const callbackRef = useRef(callback)
    const lastCallRef = useRef<number>(0)
    const timeoutRef = useRef<ReturnType<typeof setTimeout>>()

    // Keep callback ref up to date
    useEffect(() => {
        callbackRef.current = callback
    }, [callback])

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current)
            }
        }
    }, [])

    return useCallback(
        (...args: Parameters<T>) => {
            const now = Date.now()
            const timeSinceLastCall = now - lastCallRef.current

            if (timeSinceLastCall >= delay) {
                // Enough time has passed, call immediately
                lastCallRef.current = now
                callbackRef.current(...args)
            } else {
                // Schedule for later (trailing call)
                if (timeoutRef.current) {
                    clearTimeout(timeoutRef.current)
                }
                timeoutRef.current = setTimeout(() => {
                    lastCallRef.current = Date.now()
                    callbackRef.current(...args)
                }, delay - timeSinceLastCall)
            }
        },
        [delay]
    )
}

/**
 * Leading-edge throttle - fires immediately on first call, then throttles.
 * 
 * @param callback - The function to throttle
 * @param delay - Minimum time between calls in milliseconds (default: 100)
 * @returns A throttled version of the callback
 */
export function useLeadingThrottle<T extends (...args: unknown[]) => unknown>(
    callback: T,
    delay = 100
): (...args: Parameters<T>) => void {
    const callbackRef = useRef(callback)
    const lastCallRef = useRef<number>(0)
    const isThrottledRef = useRef(false)

    useEffect(() => {
        callbackRef.current = callback
    }, [callback])

    return useCallback(
        (...args: Parameters<T>) => {
            const now = Date.now()

            if (!isThrottledRef.current || now - lastCallRef.current >= delay) {
                lastCallRef.current = now
                isThrottledRef.current = true
                callbackRef.current(...args)
            }
        },
        [delay]
    )
}

/**
 * Debounce with immediate first call (leading + trailing).
 * Fires immediately on first call, then debounces subsequent calls.
 * 
 * @param callback - The function to debounce
 * @param delay - Delay in milliseconds (default: 300)
 * @returns A debounced version of the callback
 */
export function useLeadingDebounce<T extends (...args: unknown[]) => unknown>(
    callback: T,
    delay = 300
): (...args: Parameters<T>) => void {
    const callbackRef = useRef(callback)
    const timeoutRef = useRef<ReturnType<typeof setTimeout>>()
    const isLeadingRef = useRef(true)

    useEffect(() => {
        callbackRef.current = callback
    }, [callback])

    useEffect(() => {
        return () => {
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current)
            }
        }
    }, [])

    return useCallback(
        (...args: Parameters<T>) => {
            if (isLeadingRef.current) {
                // First call - execute immediately
                isLeadingRef.current = false
                callbackRef.current(...args)
            }

            // Clear any pending timeout
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current)
            }

            // Set timeout for trailing call and to reset leading flag
            timeoutRef.current = setTimeout(() => {
                isLeadingRef.current = true
            }, delay)
        },
        [delay]
    )
}
