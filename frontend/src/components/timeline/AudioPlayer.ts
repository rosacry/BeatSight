/**
 * WebAudio-based audio player for timeline editing.
 * Provides precise timing, seeking, and playback rate control.
 */

export interface AudioPlayerState {
    isPlaying: boolean
    currentTime: number // milliseconds
    duration: number // milliseconds
    playbackRate: number
    isLoading: boolean
    error: string | null
}

export interface AudioPlayerCallbacks {
    onTimeUpdate?: (time: number) => void
    onPlayStateChange?: (isPlaying: boolean) => void
    onLoad?: (duration: number) => void
    onError?: (error: string) => void
}

export class TimelineAudioPlayer {
    private audioContext: AudioContext | null = null
    private audioBuffer: AudioBuffer | null = null
    private sourceNode: AudioBufferSourceNode | null = null
    private gainNode: GainNode | null = null

    private startTime: number = 0 // AudioContext time when playback started
    private pauseTime: number = 0 // Position in track when paused (seconds)
    private _playbackRate: number = 1.0
    private _isPlaying: boolean = false
    private _isLoading: boolean = false

    private animationFrameId: number | null = null
    private callbacks: AudioPlayerCallbacks = {}

    constructor(callbacks?: AudioPlayerCallbacks) {
        if (callbacks) {
            this.callbacks = callbacks
        }
    }

    async loadAudio(url: string): Promise<void> {
        this._isLoading = true
        this.callbacks.onPlayStateChange?.(false)

        try {
            // Create AudioContext on first load (must be after user gesture)
            if (!this.audioContext) {
                this.audioContext = new AudioContext()
            }

            // Resume if suspended
            if (this.audioContext.state === 'suspended') {
                await this.audioContext.resume()
            }

            // Fetch and decode audio
            const response = await fetch(url)
            if (!response.ok) {
                throw new Error(`Failed to fetch audio: ${response.statusText}`)
            }

            const arrayBuffer = await response.arrayBuffer()
            this.audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer)

            // Create gain node for volume control
            this.gainNode = this.audioContext.createGain()
            this.gainNode.connect(this.audioContext.destination)

            this._isLoading = false
            this.callbacks.onLoad?.(this.audioBuffer.duration * 1000)
        } catch (error) {
            this._isLoading = false
            const message = error instanceof Error ? error.message : 'Failed to load audio'
            this.callbacks.onError?.(message)
            throw error
        }
    }

    play(): void {
        if (!this.audioContext || !this.audioBuffer || this._isPlaying) return

        // Resume context if needed
        if (this.audioContext.state === 'suspended') {
            this.audioContext.resume()
        }

        // Create new source node (must create new one each play)
        this.sourceNode = this.audioContext.createBufferSource()
        this.sourceNode.buffer = this.audioBuffer
        this.sourceNode.playbackRate.value = this._playbackRate
        this.sourceNode.connect(this.gainNode!)

        // Handle playback end
        this.sourceNode.onended = () => {
            if (this._isPlaying) {
                this.stop()
            }
        }

        // Start from paused position
        this.startTime = this.audioContext.currentTime
        this.sourceNode.start(0, this.pauseTime)

        this._isPlaying = true
        this.callbacks.onPlayStateChange?.(true)
        this.startTimeUpdates()
    }

    pause(): void {
        if (!this._isPlaying || !this.audioContext) return

        // Calculate current position
        const elapsed = (this.audioContext.currentTime - this.startTime) * this._playbackRate
        this.pauseTime = Math.min(this.pauseTime + elapsed, this.duration / 1000)

        this.stopPlayback()
        this._isPlaying = false
        this.callbacks.onPlayStateChange?.(false)
    }

    stop(): void {
        this.stopPlayback()
        this.pauseTime = 0
        this._isPlaying = false
        this.callbacks.onPlayStateChange?.(false)
        this.callbacks.onTimeUpdate?.(0)
    }

    private stopPlayback(): void {
        if (this.sourceNode) {
            try {
                this.sourceNode.stop()
                this.sourceNode.disconnect()
            } catch {
                // Ignore - node might already be stopped
            }
            this.sourceNode = null
        }
        this.stopTimeUpdates()
    }

    seek(timeMs: number): void {
        const wasPlaying = this._isPlaying

        if (wasPlaying) {
            this.stopPlayback()
        }

        this.pauseTime = Math.max(0, Math.min(timeMs / 1000, this.duration / 1000))
        this.callbacks.onTimeUpdate?.(this.pauseTime * 1000)

        if (wasPlaying) {
            this.play()
        }
    }

    setPlaybackRate(rate: number): void {
        this._playbackRate = Math.max(0.25, Math.min(2.0, rate))

        if (this.sourceNode) {
            this.sourceNode.playbackRate.value = this._playbackRate
        }
    }

    setVolume(volume: number): void {
        if (this.gainNode) {
            this.gainNode.gain.value = Math.max(0, Math.min(1, volume))
        }
    }

    private startTimeUpdates(): void {
        const update = () => {
            if (!this._isPlaying || !this.audioContext) return

            const elapsed = (this.audioContext.currentTime - this.startTime) * this._playbackRate
            const currentTime = (this.pauseTime + elapsed) * 1000

            if (currentTime >= this.duration) {
                this.stop()
                return
            }

            this.callbacks.onTimeUpdate?.(currentTime)
            this.animationFrameId = requestAnimationFrame(update)
        }

        this.animationFrameId = requestAnimationFrame(update)
    }

    private stopTimeUpdates(): void {
        if (this.animationFrameId !== null) {
            cancelAnimationFrame(this.animationFrameId)
            this.animationFrameId = null
        }
    }

    get currentTime(): number {
        if (!this._isPlaying || !this.audioContext) {
            return this.pauseTime * 1000
        }

        const elapsed = (this.audioContext.currentTime - this.startTime) * this._playbackRate
        return (this.pauseTime + elapsed) * 1000
    }

    get duration(): number {
        return this.audioBuffer ? this.audioBuffer.duration * 1000 : 0
    }

    get isPlaying(): boolean {
        return this._isPlaying
    }

    get isLoading(): boolean {
        return this._isLoading
    }

    get playbackRate(): number {
        return this._playbackRate
    }

    dispose(): void {
        this.stop()
        if (this.gainNode) {
            this.gainNode.disconnect()
            this.gainNode = null
        }
        if (this.audioContext) {
            this.audioContext.close()
            this.audioContext = null
        }
        this.audioBuffer = null
    }
}
