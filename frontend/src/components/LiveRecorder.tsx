/**
 * LiveRecorder Component
 * 
 * A comprehensive live audio recording interface for capturing drum performances.
 * Optimized for mobile-first usage with large touch targets and clear visual feedback.
 * 
 * Features:
 * - Real-time audio recording with Web Audio API
 * - Live waveform visualization
 * - Metronome with tap tempo
 * - Count-in before recording starts
 * - Recording quality selection
 * - Export and upload to BeatSight pipeline
 */

import { useState, useRef, useCallback, useEffect } from 'react'
import { createLogger } from '@/lib/logger'

const logger = createLogger('LiveRecorder')

interface LiveRecorderProps {
    /** Callback when recording is complete */
    onRecordingComplete?: (blob: Blob, metadata: RecordingMetadata) => void
    /** Initial BPM for metronome */
    initialBpm?: number
    /** Maximum recording duration in seconds */
    maxDuration?: number
    /** Show metronome controls */
    showMetronome?: boolean
}

interface RecordingMetadata {
    duration: number
    bpm: number
    sampleRate: number
    channels: number
    timestamp: Date
    deviceInfo: string
}

type RecordingState = 'idle' | 'countdown' | 'recording' | 'paused' | 'stopped'
type AudioQuality = 'standard' | 'high' | 'studio'

const QUALITY_SETTINGS: Record<AudioQuality, { sampleRate: number; bitRate: number; label: string }> = {
    standard: { sampleRate: 44100, bitRate: 128000, label: 'Standard (128kbps)' },
    high: { sampleRate: 48000, bitRate: 256000, label: 'High (256kbps)' },
    studio: { sampleRate: 96000, bitRate: 320000, label: 'Studio (320kbps)' },
}

export function LiveRecorder({
    onRecordingComplete,
    initialBpm = 120,
    maxDuration = 600, // 10 minutes default
    showMetronome = true,
}: LiveRecorderProps) {
    // Recording state
    const [state, setState] = useState<RecordingState>('idle')
    const [duration, setDuration] = useState(0)
    const [countdown, setCountdown] = useState(4)
    const [quality, setQuality] = useState<AudioQuality>('high')

    // Metronome state
    const [bpm, setBpm] = useState(initialBpm)
    const [metronomeEnabled, setMetronomeEnabled] = useState(false)
    const [tapTimes, setTapTimes] = useState<number[]>([])
    const [beatCount, setBeatCount] = useState(0)

    // Audio visualization
    const [waveformData, setWaveformData] = useState<number[]>(new Array(64).fill(0))
    const [peakLevel, setPeakLevel] = useState(0)
    const [clipWarning, setClipWarning] = useState(false)

    // Refs for audio handling
    const audioContextRef = useRef<AudioContext | null>(null)
    const mediaStreamRef = useRef<MediaStream | null>(null)
    const mediaRecorderRef = useRef<MediaRecorder | null>(null)
    const analyserRef = useRef<AnalyserNode | null>(null)
    const chunksRef = useRef<Blob[]>([])
    const animationFrameRef = useRef<number>(0)
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
    const metronomeIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
    const countdownIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

    // Metronome audio
    const metronomeGainRef = useRef<GainNode | null>(null)

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            stopRecording()
            if (metronomeIntervalRef.current) clearInterval(metronomeIntervalRef.current)
            if (audioContextRef.current) audioContextRef.current.close()
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])

    // Initialize audio context and request microphone
    const initAudio = useCallback(async () => {
        try {
            const qualitySettings = QUALITY_SETTINGS[quality]

            // Request microphone access
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: qualitySettings.sampleRate,
                    channelCount: 2,
                    echoCancellation: false,
                    noiseSuppression: false,
                    autoGainControl: false,
                },
            })
            mediaStreamRef.current = stream

            // Create audio context
            const audioContext = new AudioContext({ sampleRate: qualitySettings.sampleRate })
            audioContextRef.current = audioContext

            // Create analyser for visualization
            const analyser = audioContext.createAnalyser()
            analyser.fftSize = 256
            analyser.smoothingTimeConstant = 0.8
            analyserRef.current = analyser

            // Connect microphone to analyser
            const source = audioContext.createMediaStreamSource(stream)
            source.connect(analyser)

            // Create metronome gain node
            const metronomeGain = audioContext.createGain()
            metronomeGain.gain.value = 0.3
            metronomeGain.connect(audioContext.destination)
            metronomeGainRef.current = metronomeGain

            return true
        } catch (error) {
            logger.error('Failed to initialize audio:', error)
            return false
        }
    }, [quality])

    // Update waveform visualization
    const updateVisualization = useCallback(() => {
        if (!analyserRef.current) return

        const analyser = analyserRef.current
        const dataArray = new Uint8Array(analyser.frequencyBinCount)
        analyser.getByteFrequencyData(dataArray)

        // Convert to normalized values
        const normalizedData = Array.from(dataArray).map(v => v / 255)
        setWaveformData(normalizedData)

        // Calculate peak level
        const peak = Math.max(...normalizedData)
        setPeakLevel(peak)
        setClipWarning(peak > 0.95)

        if (state === 'recording') {
            animationFrameRef.current = requestAnimationFrame(updateVisualization)
        }
    }, [state])

    // Play metronome tick
    const playTick = useCallback((isAccent: boolean = false) => {
        if (!audioContextRef.current || !metronomeGainRef.current) return

        const ctx = audioContextRef.current
        const oscillator = ctx.createOscillator()
        const gainNode = ctx.createGain()

        oscillator.type = 'sine'
        oscillator.frequency.value = isAccent ? 1000 : 800

        gainNode.gain.setValueAtTime(0.3, ctx.currentTime)
        gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.1)

        oscillator.connect(gainNode)
        gainNode.connect(metronomeGainRef.current)

        oscillator.start()
        oscillator.stop(ctx.currentTime + 0.1)
    }, [])

    // Start metronome
    const startMetronome = useCallback(() => {
        if (metronomeIntervalRef.current) clearInterval(metronomeIntervalRef.current)

        const interval = 60000 / bpm
        let beat = 0

        const tick = () => {
            const isAccent = beat % 4 === 0
            playTick(isAccent)
            setBeatCount(beat + 1)
            beat = (beat + 1) % 4
        }

        tick() // First tick immediately
        metronomeIntervalRef.current = setInterval(tick, interval)
    }, [bpm, playTick])

    // Stop metronome
    const stopMetronome = useCallback(() => {
        if (metronomeIntervalRef.current) {
            clearInterval(metronomeIntervalRef.current)
            metronomeIntervalRef.current = null
        }
        setBeatCount(0)
    }, [])

    // Toggle metronome
    const toggleMetronome = useCallback(() => {
        if (metronomeEnabled) {
            stopMetronome()
        } else {
            startMetronome()
        }
        setMetronomeEnabled(!metronomeEnabled)
    }, [metronomeEnabled, startMetronome, stopMetronome])

    // Tap tempo
    const handleTapTempo = useCallback(() => {
        const now = Date.now()
        const newTaps = [...tapTimes, now].filter(t => now - t < 5000).slice(-8)
        setTapTimes(newTaps)

        if (newTaps.length >= 2) {
            const intervals = newTaps.slice(1).map((t, i) => t - newTaps[i])
            const avgInterval = intervals.reduce((a, b) => a + b, 0) / intervals.length
            const newBpm = Math.round(60000 / avgInterval)
            setBpm(Math.max(40, Math.min(240, newBpm)))
        }
    }, [tapTimes])

    // Start countdown before recording
    const startCountdown = useCallback(async () => {
        const initialized = await initAudio()
        if (!initialized) return

        setState('countdown')
        setCountdown(4)

        // Start metronome during countdown if enabled
        if (metronomeEnabled) {
            startMetronome()
        }

        countdownIntervalRef.current = setInterval(() => {
            setCountdown(prev => {
                if (prev <= 1) {
                    if (countdownIntervalRef.current) {
                        clearInterval(countdownIntervalRef.current)
                    }
                    startRecording()
                    return 0
                }
                playTick(prev === 4) // Accent on first beat
                return prev - 1
            })
        }, 60000 / bpm)
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [bpm, initAudio, metronomeEnabled, playTick, startMetronome])

    // Start recording
    const startRecording = useCallback(() => {
        if (!mediaStreamRef.current) return

        const qualitySettings = QUALITY_SETTINGS[quality]
        chunksRef.current = []

        try {
            // Try to use audio/webm with opus for best quality
            const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
                ? 'audio/webm;codecs=opus'
                : 'audio/webm'

            const mediaRecorder = new MediaRecorder(mediaStreamRef.current, {
                mimeType,
                audioBitsPerSecond: qualitySettings.bitRate,
            })

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    chunksRef.current.push(event.data)
                }
            }

            mediaRecorder.onstop = () => {
                const blob = new Blob(chunksRef.current, { type: mimeType })
                const metadata: RecordingMetadata = {
                    duration,
                    bpm,
                    sampleRate: qualitySettings.sampleRate,
                    channels: 2,
                    timestamp: new Date(),
                    deviceInfo: navigator.userAgent,
                }
                onRecordingComplete?.(blob, metadata)
            }

            mediaRecorderRef.current = mediaRecorder
            mediaRecorder.start(1000) // Collect data every second

            setState('recording')
            setDuration(0)

            // Start duration timer
            timerRef.current = setInterval(() => {
                setDuration(prev => {
                    if (prev >= maxDuration) {
                        stopRecording()
                        return prev
                    }
                    return prev + 1
                })
            }, 1000)

            // Start visualization
            updateVisualization()
        } catch (error) {
            console.error('Failed to start recording:', error)
            setState('idle')
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [quality, duration, bpm, maxDuration, onRecordingComplete, updateVisualization])

    // Stop recording
    const stopRecording = useCallback(() => {
        if (mediaRecorderRef.current && state === 'recording') {
            mediaRecorderRef.current.stop()
        }

        if (timerRef.current) {
            clearInterval(timerRef.current)
            timerRef.current = null
        }

        if (animationFrameRef.current) {
            cancelAnimationFrame(animationFrameRef.current)
        }

        stopMetronome()

        // Stop all tracks
        if (mediaStreamRef.current) {
            mediaStreamRef.current.getTracks().forEach(track => track.stop())
        }

        setState('stopped')
    }, [state, stopMetronome])

    // Pause recording
    const pauseRecording = useCallback(() => {
        if (mediaRecorderRef.current && state === 'recording') {
            mediaRecorderRef.current.pause()
            setState('paused')
            if (timerRef.current) clearInterval(timerRef.current)
            stopMetronome()
        }
    }, [state, stopMetronome])

    // Resume recording
    const resumeRecording = useCallback(() => {
        if (mediaRecorderRef.current && state === 'paused') {
            mediaRecorderRef.current.resume()
            setState('recording')

            timerRef.current = setInterval(() => {
                setDuration(prev => prev + 1)
            }, 1000)

            if (metronomeEnabled) startMetronome()
            updateVisualization()
        }
    }, [state, metronomeEnabled, startMetronome, updateVisualization])

    // Reset recorder
    const resetRecorder = useCallback(() => {
        stopRecording()
        setState('idle')
        setDuration(0)
        chunksRef.current = []
    }, [stopRecording])

    // Format duration as mm:ss
    const formatDuration = (seconds: number) => {
        const mins = Math.floor(seconds / 60)
        const secs = seconds % 60
        return `${mins}:${secs.toString().padStart(2, '0')}`
    }

    return (
        <div className="bg-gray-900 rounded-xl p-4 md:p-6 space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                    <svg className="w-6 h-6 text-red-500" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm-1 1.93c-3.94-.49-7-3.85-7-7.93V7h2v1c0 2.76 2.24 5 5 5s5-2.24 5-5V7h2v1c0 4.08-3.06 7.44-7 7.93V19h3v2H8v-2h3v-3.07z" />
                    </svg>
                    Live Recorder
                </h2>

                {/* Quality selector */}
                <select
                    value={quality}
                    onChange={(e) => setQuality(e.target.value as AudioQuality)}
                    disabled={state !== 'idle'}
                    className="bg-gray-800 text-white text-sm rounded-lg px-3 py-1.5 border border-gray-700 disabled:opacity-50"
                >
                    {Object.entries(QUALITY_SETTINGS).map(([key, { label }]) => (
                        <option key={key} value={key}>{label}</option>
                    ))}
                </select>
            </div>

            {/* Waveform Visualization */}
            <div className="relative h-24 bg-gray-800 rounded-lg overflow-hidden">
                {/* Waveform bars */}
                <div className="absolute inset-0 flex items-center justify-center gap-0.5 px-2">
                    {waveformData.map((value, i) => (
                        <div
                            key={i}
                            className="flex-1 bg-primary-500 rounded-sm transition-all duration-75"
                            style={{
                                height: `${Math.max(2, value * 100)}%`,
                                opacity: 0.6 + value * 0.4,
                            }}
                        />
                    ))}
                </div>

                {/* Countdown overlay */}
                {state === 'countdown' && (
                    <div className="absolute inset-0 flex items-center justify-center bg-black/70">
                        <span className="text-6xl font-bold text-white animate-pulse">
                            {countdown}
                        </span>
                    </div>
                )}

                {/* Recording indicator */}
                {state === 'recording' && (
                    <div className="absolute top-2 left-2 flex items-center gap-2">
                        <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse" />
                        <span className="text-white text-sm font-medium">REC</span>
                    </div>
                )}

                {/* Clip warning */}
                {clipWarning && (
                    <div className="absolute top-2 right-2 px-2 py-0.5 bg-red-500/80 text-white text-xs rounded">
                        CLIPPING
                    </div>
                )}

                {/* Peak level meter */}
                <div className="absolute bottom-2 right-2 w-24 h-2 bg-gray-700 rounded-full overflow-hidden">
                    <div
                        className={`h-full transition-all duration-75 ${peakLevel > 0.9 ? 'bg-red-500' : peakLevel > 0.7 ? 'bg-yellow-500' : 'bg-green-500'
                            }`}
                        style={{ width: `${peakLevel * 100}%` }}
                    />
                </div>
            </div>

            {/* Duration Display */}
            <div className="text-center">
                <div className="text-5xl font-mono font-bold text-white tracking-wider">
                    {formatDuration(duration)}
                </div>
                <div className="text-sm text-gray-500 mt-1">
                    Max: {formatDuration(maxDuration)}
                </div>
            </div>

            {/* Main Controls */}
            <div className="flex items-center justify-center gap-4">
                {state === 'idle' && (
                    <button
                        onClick={startCountdown}
                        className="w-20 h-20 rounded-full bg-red-500 hover:bg-red-600 flex items-center justify-center transition-colors shadow-lg shadow-red-500/30"
                    >
                        <div className="w-8 h-8 rounded-full bg-white" />
                    </button>
                )}

                {state === 'countdown' && (
                    <button
                        onClick={resetRecorder}
                        className="w-20 h-20 rounded-full bg-gray-600 hover:bg-gray-700 flex items-center justify-center transition-colors"
                    >
                        <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
                        </svg>
                    </button>
                )}

                {state === 'recording' && (
                    <>
                        <button
                            onClick={pauseRecording}
                            className="w-16 h-16 rounded-full bg-yellow-500 hover:bg-yellow-600 flex items-center justify-center transition-colors"
                        >
                            <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 24 24">
                                <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
                            </svg>
                        </button>
                        <button
                            onClick={stopRecording}
                            className="w-20 h-20 rounded-full bg-red-500 hover:bg-red-600 flex items-center justify-center transition-colors shadow-lg shadow-red-500/30"
                        >
                            <div className="w-8 h-8 rounded bg-white" />
                        </button>
                    </>
                )}

                {state === 'paused' && (
                    <>
                        <button
                            onClick={resumeRecording}
                            className="w-20 h-20 rounded-full bg-green-500 hover:bg-green-600 flex items-center justify-center transition-colors"
                        >
                            <svg className="w-10 h-10 text-white ml-1" fill="currentColor" viewBox="0 0 24 24">
                                <path d="M8 5v14l11-7z" />
                            </svg>
                        </button>
                        <button
                            onClick={stopRecording}
                            className="w-16 h-16 rounded-full bg-red-500 hover:bg-red-600 flex items-center justify-center transition-colors"
                        >
                            <div className="w-6 h-6 rounded bg-white" />
                        </button>
                    </>
                )}

                {state === 'stopped' && (
                    <button
                        onClick={resetRecorder}
                        className="px-6 py-3 bg-primary-500 hover:bg-primary-600 text-white rounded-lg font-medium transition-colors"
                    >
                        Record Again
                    </button>
                )}
            </div>

            {/* Metronome Controls */}
            {showMetronome && (
                <div className="border-t border-gray-800 pt-4">
                    <div className="flex items-center justify-between mb-3">
                        <span className="text-sm font-medium text-gray-400">Metronome</span>
                        <button
                            onClick={toggleMetronome}
                            disabled={state !== 'idle'}
                            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${metronomeEnabled ? 'bg-primary-500' : 'bg-gray-700'
                                } disabled:opacity-50`}
                        >
                            <span
                                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${metronomeEnabled ? 'translate-x-6' : 'translate-x-1'
                                    }`}
                            />
                        </button>
                    </div>

                    <div className="flex items-center gap-4">
                        {/* BPM Control */}
                        <div className="flex-1">
                            <div className="flex items-center gap-2 mb-2">
                                <button
                                    onClick={() => setBpm(Math.max(40, bpm - 5))}
                                    disabled={state !== 'idle'}
                                    className="w-8 h-8 rounded bg-gray-800 text-white hover:bg-gray-700 disabled:opacity-50"
                                >
                                    -
                                </button>
                                <div className="flex-1 text-center">
                                    <span className="text-2xl font-bold text-white">{bpm}</span>
                                    <span className="text-gray-500 text-sm ml-1">BPM</span>
                                </div>
                                <button
                                    onClick={() => setBpm(Math.min(240, bpm + 5))}
                                    disabled={state !== 'idle'}
                                    className="w-8 h-8 rounded bg-gray-800 text-white hover:bg-gray-700 disabled:opacity-50"
                                >
                                    +
                                </button>
                            </div>
                            <input
                                type="range"
                                min="40"
                                max="240"
                                value={bpm}
                                onChange={(e) => setBpm(parseInt(e.target.value))}
                                disabled={state !== 'idle'}
                                className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer disabled:opacity-50"
                            />
                        </div>

                        {/* Tap Tempo */}
                        <button
                            onClick={handleTapTempo}
                            disabled={state !== 'idle'}
                            className="px-4 py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-700 disabled:opacity-50 whitespace-nowrap"
                        >
                            Tap Tempo
                        </button>
                    </div>

                    {/* Beat Indicator */}
                    {metronomeEnabled && (
                        <div className="flex items-center justify-center gap-2 mt-3">
                            {[1, 2, 3, 4].map((beat) => (
                                <div
                                    key={beat}
                                    className={`w-4 h-4 rounded-full transition-all ${beatCount % 4 === beat % 4
                                        ? beat === 1
                                            ? 'bg-primary-500 scale-125'
                                            : 'bg-gray-400 scale-110'
                                        : 'bg-gray-700'
                                        }`}
                                />
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Tips */}
            <div className="text-xs text-gray-500 text-center space-y-1">
                <p>💡 Position your phone near your kit for best results</p>
                <p>📱 Keep your device steady during recording</p>
            </div>
        </div>
    )
}

export default LiveRecorder
