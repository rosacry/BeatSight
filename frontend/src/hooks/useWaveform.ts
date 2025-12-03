import { useState, useEffect, useCallback } from 'react'

/**
 * Waveform data structure matching desktop BeatSight.Game.Audio.WaveformData
 * Stores min/max amplitude buckets for efficient rendering.
 */
export interface WaveformData {
    /** Minimum amplitude values per bucket */
    minima: Float32Array
    /** Maximum amplitude values per bucket */
    maxima: Float32Array
    /** Audio duration in seconds */
    durationSeconds: number
    /** Duration of each bucket in seconds */
    bucketDurationSeconds: number
    /** Number of buckets */
    bucketCount: number
}

/**
 * Default number of buckets for waveform visualization.
 * Higher = more detail, but more memory usage.
 */
const DEFAULT_BUCKET_COUNT = 2000

/**
 * Computes waveform data from an AudioBuffer.
 * Downsamples audio into buckets storing min/max amplitudes.
 */
export function computeWaveformData(
    audioBuffer: AudioBuffer,
    bucketCount: number = DEFAULT_BUCKET_COUNT
): WaveformData {
    const channelData = audioBuffer.getChannelData(0) // Use first channel
    const samplesPerBucket = Math.floor(channelData.length / bucketCount)

    const minima = new Float32Array(bucketCount)
    const maxima = new Float32Array(bucketCount)

    for (let bucket = 0; bucket < bucketCount; bucket++) {
        const startSample = bucket * samplesPerBucket
        const endSample = Math.min(startSample + samplesPerBucket, channelData.length)

        let min = Infinity
        let max = -Infinity

        for (let i = startSample; i < endSample; i++) {
            const sample = channelData[i]
            if (sample < min) min = sample
            if (sample > max) max = sample
        }

        minima[bucket] = min === Infinity ? 0 : min
        maxima[bucket] = max === -Infinity ? 0 : max
    }

    return {
        minima,
        maxima,
        durationSeconds: audioBuffer.duration,
        bucketDurationSeconds: audioBuffer.duration / bucketCount,
        bucketCount,
    }
}

interface UseWaveformOptions {
    /** Audio URL to load and analyze */
    audioUrl: string | null
    /** Number of buckets for waveform (default: 2000) */
    bucketCount?: number
    /** Whether waveform computation is enabled */
    enabled?: boolean
}

interface UseWaveformResult {
    /** Computed waveform data */
    waveformData: WaveformData | null
    /** Whether waveform is being computed */
    isLoading: boolean
    /** Error message if computation failed */
    error: string | null
    /** Recompute waveform */
    refresh: () => void
}

/**
 * Hook to compute waveform data from an audio URL.
 * Uses Web Audio API to decode and analyze audio.
 */
export function useWaveform({
    audioUrl,
    bucketCount = DEFAULT_BUCKET_COUNT,
    enabled = true,
}: UseWaveformOptions): UseWaveformResult {
    const [waveformData, setWaveformData] = useState<WaveformData | null>(null)
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const computeWaveform = useCallback(async () => {
        if (!audioUrl || !enabled) {
            setWaveformData(null)
            return
        }

        setIsLoading(true)
        setError(null)

        try {
            // Fetch audio data
            const response = await fetch(audioUrl)
            if (!response.ok) {
                throw new Error(`Failed to fetch audio: ${response.statusText}`)
            }

            const arrayBuffer = await response.arrayBuffer()

            // Decode audio using Web Audio API
            const audioContext = new AudioContext()
            const audioBuffer = await audioContext.decodeAudioData(arrayBuffer)

            // Compute waveform
            const data = computeWaveformData(audioBuffer, bucketCount)
            setWaveformData(data)

            // Clean up audio context
            await audioContext.close()
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Failed to compute waveform'
            setError(message)
            setWaveformData(null)
        } finally {
            setIsLoading(false)
        }
    }, [audioUrl, bucketCount, enabled])

    // Compute waveform when URL changes
    useEffect(() => {
        computeWaveform()
    }, [computeWaveform])

    return {
        waveformData,
        isLoading,
        error,
        refresh: computeWaveform,
    }
}

/**
 * Get the amplitude range for a specific time window.
 * Returns [min, max] for rendering waveform in viewport.
 */
export function getWaveformRange(
    waveformData: WaveformData,
    startTimeMs: number,
    endTimeMs: number
): { minima: number[]; maxima: number[]; startBucket: number; endBucket: number } {
    const startSeconds = startTimeMs / 1000
    const endSeconds = endTimeMs / 1000

    const startBucket = Math.max(0, Math.floor(startSeconds / waveformData.bucketDurationSeconds))
    const endBucket = Math.min(
        waveformData.bucketCount,
        Math.ceil(endSeconds / waveformData.bucketDurationSeconds)
    )

    const minima: number[] = []
    const maxima: number[] = []

    for (let i = startBucket; i < endBucket; i++) {
        minima.push(waveformData.minima[i])
        maxima.push(waveformData.maxima[i])
    }

    return { minima, maxima, startBucket, endBucket }
}
