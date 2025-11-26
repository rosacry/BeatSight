import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { TimelineAudioPlayer, AudioPlayerCallbacks } from '../AudioPlayer'

describe('TimelineAudioPlayer', () => {
    let player: TimelineAudioPlayer
    let callbacks: AudioPlayerCallbacks

    beforeEach(() => {
        callbacks = {
            onTimeUpdate: vi.fn(),
            onPlayStateChange: vi.fn(),
            onLoad: vi.fn(),
            onError: vi.fn(),
        }

        player = new TimelineAudioPlayer(callbacks)
    })

    afterEach(() => {
        player.dispose()
    })

    describe('initial state', () => {
        it('should not be playing initially', () => {
            expect(player.isPlaying).toBe(false)
        })

        it('should have zero duration initially', () => {
            expect(player.duration).toBe(0)
        })

        it('should have zero current time initially', () => {
            expect(player.currentTime).toBe(0)
        })

        it('should have default playback rate of 1', () => {
            expect(player.playbackRate).toBe(1.0)
        })

        it('should not be loading initially', () => {
            expect(player.isLoading).toBe(false)
        })
    })

    describe('playback rate', () => {
        it('should set playback rate', () => {
            player.setPlaybackRate(0.5)
            expect(player.playbackRate).toBe(0.5)

            player.setPlaybackRate(1.5)
            expect(player.playbackRate).toBe(1.5)
        })

        it('should clamp playback rate to minimum 0.25', () => {
            player.setPlaybackRate(0.1)
            expect(player.playbackRate).toBe(0.25)
        })

        it('should clamp playback rate to maximum 2.0', () => {
            player.setPlaybackRate(3.0)
            expect(player.playbackRate).toBe(2.0)
        })
    })

    describe('dispose', () => {
        it('should clean up player state', () => {
            player.dispose()
            expect(player.isPlaying).toBe(false)
            expect(player.duration).toBe(0)
        })
    })
})
