/**
 * Auto-save hook for osu!-style automatic settings persistence.
 * 
 * Features:
 * - Debounced saves to avoid excessive API calls
 * - Per-field save state tracking (idle, saving, saved, error)
 * - Automatic "Saved" message that fades after delay
 * - Error handling with retry capability
 */

import { useState, useCallback, useRef, useEffect } from 'react'

export type SaveState = 'idle' | 'saving' | 'saved' | 'error'

interface UseAutoSaveOptions<T> {
    /** Function to call when saving */
    onSave: (value: T) => Promise<void>
    /** Debounce delay in ms (default: 500ms) */
    debounceMs?: number
    /** How long to show "Saved" state in ms (default: 2000ms) */
    savedDisplayMs?: number
}

interface UseAutoSaveReturn<T> {
    /** Current save state */
    saveState: SaveState
    /** Error message if save failed */
    error: string | null
    /** Trigger a save with the given value */
    save: (value: T) => void
    /** Retry the last failed save */
    retry: () => void
    /** Reset state to idle */
    reset: () => void
}

/**
 * Hook for auto-saving individual fields with debouncing.
 * 
 * @example
 * ```tsx
 * const { saveState, save } = useAutoSave({
 *   onSave: async (value) => {
 *     await api.updateDisplayName(value)
 *   }
 * })
 * 
 * <input onChange={(e) => save(e.target.value)} />
 * <SaveIndicator state={saveState} />
 * ```
 */
export function useAutoSave<T>({
    onSave,
    debounceMs = 500,
    savedDisplayMs = 2000,
}: UseAutoSaveOptions<T>): UseAutoSaveReturn<T> {
    const [saveState, setSaveState] = useState<SaveState>('idle')
    const [error, setError] = useState<string | null>(null)

    const timeoutRef = useRef<NodeJS.Timeout | null>(null)
    const savedTimeoutRef = useRef<NodeJS.Timeout | null>(null)
    const lastValueRef = useRef<T | null>(null)
    const isMountedRef = useRef(true)

    // Cleanup on unmount
    useEffect(() => {
        isMountedRef.current = true
        return () => {
            isMountedRef.current = false
            if (timeoutRef.current) clearTimeout(timeoutRef.current)
            if (savedTimeoutRef.current) clearTimeout(savedTimeoutRef.current)
        }
    }, [])

    const performSave = useCallback(async (value: T) => {
        if (!isMountedRef.current) return

        setSaveState('saving')
        setError(null)

        try {
            await onSave(value)

            if (!isMountedRef.current) return

            setSaveState('saved')

            // Reset to idle after showing "Saved"
            savedTimeoutRef.current = setTimeout(() => {
                if (isMountedRef.current) {
                    setSaveState('idle')
                }
            }, savedDisplayMs)
        } catch (err) {
            if (!isMountedRef.current) return

            const message = err instanceof Error ? err.message : 'Failed to save'
            setError(message)
            setSaveState('error')
        }
    }, [onSave, savedDisplayMs])

    const save = useCallback((value: T) => {
        lastValueRef.current = value

        // Clear any existing timeout
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current)
        }
        if (savedTimeoutRef.current) {
            clearTimeout(savedTimeoutRef.current)
        }

        // Set to saving immediately for visual feedback, but debounce the actual save
        setSaveState('saving')

        // Debounce the actual API call
        timeoutRef.current = setTimeout(() => {
            performSave(value)
        }, debounceMs)
    }, [debounceMs, performSave])

    const retry = useCallback(() => {
        if (lastValueRef.current !== null) {
            performSave(lastValueRef.current)
        }
    }, [performSave])

    const reset = useCallback(() => {
        setSaveState('idle')
        setError(null)
        if (timeoutRef.current) clearTimeout(timeoutRef.current)
        if (savedTimeoutRef.current) clearTimeout(savedTimeoutRef.current)
    }, [])

    return {
        saveState,
        error,
        save,
        retry,
        reset,
    }
}

/**
 * Hook for managing multiple auto-save fields at once.
 * Useful for forms with many fields that each save independently.
 */
interface FieldSaveState {
    state: SaveState
    error: string | null
}

interface UseMultiAutoSaveOptions {
    /** Debounce delay in ms (default: 500ms) */
    debounceMs?: number
    /** How long to show "Saved" state in ms (default: 2000ms) */
    savedDisplayMs?: number
}

interface UseMultiAutoSaveReturn {
    /** Get save state for a specific field */
    getFieldState: (field: string) => FieldSaveState
    /** Save a specific field */
    saveField: <T>(field: string, value: T, saveFn: (value: T) => Promise<void>) => void
    /** Check if any field is currently saving */
    isAnySaving: boolean
    /** Check if any field has an error */
    hasAnyError: boolean
    /** Reset all field states */
    resetAll: () => void
}

export function useMultiAutoSave({
    debounceMs = 500,
    savedDisplayMs = 2000,
}: UseMultiAutoSaveOptions = {}): UseMultiAutoSaveReturn {
    const [fieldStates, setFieldStates] = useState<Record<string, FieldSaveState>>({})
    const timeoutsRef = useRef<Record<string, NodeJS.Timeout>>({})
    const savedTimeoutsRef = useRef<Record<string, NodeJS.Timeout>>({})
    const isMountedRef = useRef(true)

    // Cleanup on unmount
    useEffect(() => {
        isMountedRef.current = true
        return () => {
            isMountedRef.current = false
            Object.values(timeoutsRef.current).forEach(clearTimeout)
            Object.values(savedTimeoutsRef.current).forEach(clearTimeout)
        }
    }, [])

    const getFieldState = useCallback((field: string): FieldSaveState => {
        return fieldStates[field] || { state: 'idle', error: null }
    }, [fieldStates])

    const saveField = useCallback(<T,>(
        field: string,
        value: T,
        saveFn: (value: T) => Promise<void>
    ) => {
        // Clear existing timeouts for this field
        if (timeoutsRef.current[field]) {
            clearTimeout(timeoutsRef.current[field])
        }
        if (savedTimeoutsRef.current[field]) {
            clearTimeout(savedTimeoutsRef.current[field])
        }

        // Set to saving immediately
        setFieldStates(prev => ({
            ...prev,
            [field]: { state: 'saving', error: null }
        }))

        // Debounce the actual save
        timeoutsRef.current[field] = setTimeout(async () => {
            try {
                await saveFn(value)

                if (!isMountedRef.current) return

                setFieldStates(prev => ({
                    ...prev,
                    [field]: { state: 'saved', error: null }
                }))

                // Reset to idle after showing "Saved"
                savedTimeoutsRef.current[field] = setTimeout(() => {
                    if (isMountedRef.current) {
                        setFieldStates(prev => ({
                            ...prev,
                            [field]: { state: 'idle', error: null }
                        }))
                    }
                }, savedDisplayMs)
            } catch (err) {
                if (!isMountedRef.current) return

                const message = err instanceof Error ? err.message : 'Failed to save'
                setFieldStates(prev => ({
                    ...prev,
                    [field]: { state: 'error', error: message }
                }))
            }
        }, debounceMs)
    }, [debounceMs, savedDisplayMs])

    const isAnySaving = Object.values(fieldStates).some(s => s.state === 'saving')
    const hasAnyError = Object.values(fieldStates).some(s => s.state === 'error')

    const resetAll = useCallback(() => {
        setFieldStates({})
        Object.values(timeoutsRef.current).forEach(clearTimeout)
        Object.values(savedTimeoutsRef.current).forEach(clearTimeout)
        timeoutsRef.current = {}
        savedTimeoutsRef.current = {}
    }, [])

    return {
        getFieldState,
        saveField,
        isAnySaving,
        hasAnyError,
        resetAll,
    }
}

export default useAutoSave
