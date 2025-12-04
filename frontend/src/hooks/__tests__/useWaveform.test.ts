/**
 * Tests for useWaveform hook - audio waveform computation
 *
 * Created: December 3, 2025
 * References: ENGINEERING_ACTION_TRACKER.md item 4.5
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { useWaveform, computeWaveformData } from '../useWaveform'

// Mock AudioContext
class MockAudioContext {
    sampleRate = 44100

    async decodeAudioData(_buffer: ArrayBuffer): Promise<AudioBuffer> {
        // Create a mock AudioBuffer with sine wave data
        const duration = 2.0 // 2 seconds
        const sampleRate = 44100
        const length = Math.floor(duration * sampleRate)

        const channelData = new Float32Array(length)
        // Generate a simple sine wave
        for (let i = 0; i < length; i++) {
            channelData[i] = Math.sin((2 * Math.PI * 440 * i) / sampleRate)
        }

        return {
            duration,
            length,
            sampleRate,
            numberOfChannels: 1,
            getChannelData: (_channel: number) => channelData,
            copyFromChannel: vi.fn(),
            copyToChannel: vi.fn(),
        } as unknown as AudioBuffer
    }

    async close(): Promise<void> {
        // Mock close
    }
}

// Store original globals
const originalAudioContext = (globalThis as any).AudioContext
const originalFetch = (globalThis as any).fetch

describe('computeWaveformData', () => {
    it('should compute min/max values for waveform buckets', () => {
        // Create a simple audio buffer
        const sampleRate = 44100
        const duration = 1.0
        const length = Math.floor(duration * sampleRate)

        const channelData = new Float32Array(length)
        // Create a simple pattern: positive in first half, negative in second half
        for (let i = 0; i < length; i++) {
            channelData[i] = i < length / 2 ? 0.5 : -0.5
        }

        const mockBuffer: AudioBuffer = {
            duration,
            length,
            sampleRate,
            numberOfChannels: 1,
            getChannelData: () => channelData,
            copyFromChannel: vi.fn(),
            copyToChannel: vi.fn(),
        } as unknown as AudioBuffer

        const result = computeWaveformData(mockBuffer, 100)

        expect(result.bucketCount).toBe(100)
        expect(result.durationSeconds).toBe(1.0)
        expect(result.bucketDurationSeconds).toBeCloseTo(0.01, 5)
        expect(result.minima).toBeInstanceOf(Float32Array)
        expect(result.maxima).toBeInstanceOf(Float32Array)
        expect(result.minima.length).toBe(100)
        expect(result.maxima.length).toBe(100)
    })

    it('should handle different bucket counts', () => {
        const sampleRate = 44100
        const duration = 2.0
        const length = Math.floor(duration * sampleRate)

        const channelData = new Float32Array(length)
        for (let i = 0; i < length; i++) {
            channelData[i] = Math.sin((2 * Math.PI * 440 * i) / sampleRate)
        }

        const mockBuffer: AudioBuffer = {
            duration,
            length,
            sampleRate,
            numberOfChannels: 1,
            getChannelData: () => channelData,
            copyFromChannel: vi.fn(),
            copyToChannel: vi.fn(),
        } as unknown as AudioBuffer

        const result500 = computeWaveformData(mockBuffer, 500)
        const result2000 = computeWaveformData(mockBuffer, 2000)

        expect(result500.bucketCount).toBe(500)
        expect(result2000.bucketCount).toBe(2000)
    })

    it('should capture min/max amplitudes within buckets', () => {
        const sampleRate = 1000
        const duration = 1.0
        const length = 1000

        const channelData = new Float32Array(length)
        // Create a known pattern: bucket 0 has range [-0.8, 0.8]
        for (let i = 0; i < 100; i++) {
            channelData[i] = i < 50 ? 0.8 : -0.8
        }
        // Bucket 1 has range [-0.3, 0.3]
        for (let i = 100; i < 200; i++) {
            channelData[i] = i < 150 ? 0.3 : -0.3
        }

        const mockBuffer: AudioBuffer = {
            duration,
            length,
            sampleRate,
            numberOfChannels: 1,
            getChannelData: () => channelData,
            copyFromChannel: vi.fn(),
            copyToChannel: vi.fn(),
        } as unknown as AudioBuffer

        const result = computeWaveformData(mockBuffer, 10)

        // First bucket should have max near 0.8 and min near -0.8
        expect(result.maxima[0]).toBeCloseTo(0.8, 1)
        expect(result.minima[0]).toBeCloseTo(-0.8, 1)

        // Second bucket should have max near 0.3 and min near -0.3
        expect(result.maxima[1]).toBeCloseTo(0.3, 1)
        expect(result.minima[1]).toBeCloseTo(-0.3, 1)
    })
})

describe('useWaveform', () => {
    beforeEach(() => {
        // Mock AudioContext
        ; (globalThis as any).AudioContext = MockAudioContext as unknown as typeof AudioContext

            // Mock fetch
            ; (globalThis as any).fetch = vi.fn().mockResolvedValue({
                ok: true,
                arrayBuffer: () => Promise.resolve(new ArrayBuffer(1024)),
            })
    })

    afterEach(() => {
        ; (globalThis as any).AudioContext = originalAudioContext
            ; (globalThis as any).fetch = originalFetch
    })

    it('should return null waveform when audioUrl is null', () => {
        const { result } = renderHook(() =>
            useWaveform({ audioUrl: null })
        )

        expect(result.current.waveformData).toBeNull()
        expect(result.current.isLoading).toBe(false)
        expect(result.current.error).toBeNull()
    })

    it('should compute waveform when given valid URL', async () => {
        const { result } = renderHook(() =>
            useWaveform({ audioUrl: 'https://example.com/audio.mp3' })
        )

        // Should be loading initially
        expect(result.current.isLoading).toBe(true)

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        expect(result.current.waveformData).not.toBeNull()
        expect(result.current.waveformData?.bucketCount).toBe(2000) // default
        expect(result.current.error).toBeNull()
    })

    it('should use custom bucket count', async () => {
        const { result } = renderHook(() =>
            useWaveform({ audioUrl: 'https://example.com/audio.mp3', bucketCount: 500 })
        )

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        expect(result.current.waveformData?.bucketCount).toBe(500)
    })

    it('should handle fetch error', async () => {
        ; (globalThis as any).fetch = vi.fn().mockResolvedValue({
            ok: false,
            statusText: 'Not Found',
        })

        const { result } = renderHook(() =>
            useWaveform({ audioUrl: 'https://example.com/missing.mp3' })
        )

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        expect(result.current.error).toContain('Failed to fetch audio')
        expect(result.current.waveformData).toBeNull()
    })

    it('should handle decode error', async () => {
        // Mock AudioContext that throws on decode
        class FailingAudioContext {
            async decodeAudioData(): Promise<AudioBuffer> {
                throw new Error('Decode failed: unsupported format')
            }
            async close(): Promise<void> { }
        }

        ; (globalThis as any).AudioContext = FailingAudioContext as unknown as typeof AudioContext

        const { result } = renderHook(() =>
            useWaveform({ audioUrl: 'https://example.com/bad.mp3' })
        )

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        expect(result.current.error).toContain('Decode failed')
        expect(result.current.waveformData).toBeNull()
    })

    it('should not compute when enabled is false', () => {
        const { result } = renderHook(() =>
            useWaveform({ audioUrl: 'https://example.com/audio.mp3', enabled: false })
        )

        expect(result.current.isLoading).toBe(false)
        expect(result.current.waveformData).toBeNull()
        expect((globalThis as any).fetch).not.toHaveBeenCalled()
    })

    it('should recompute when URL changes', async () => {
        const { result, rerender } = renderHook(
            ({ url }) => useWaveform({ audioUrl: url }),
            { initialProps: { url: 'https://example.com/audio1.mp3' } }
        )

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        expect((globalThis as any).fetch).toHaveBeenCalledTimes(1)

        // Change URL
        rerender({ url: 'https://example.com/audio2.mp3' })

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        expect((globalThis as any).fetch).toHaveBeenCalledTimes(2)
    })

    it('should provide refresh function', async () => {
        const { result } = renderHook(() =>
            useWaveform({ audioUrl: 'https://example.com/audio.mp3' })
        )

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        expect((globalThis as any).fetch).toHaveBeenCalledTimes(1)

        // Call refresh
        act(() => {
            result.current.refresh()
        })

        await waitFor(() => expect(result.current.isLoading).toBe(false))

        expect((globalThis as any).fetch).toHaveBeenCalledTimes(2)
    })
})
