/**
 * DifficultyHeatmap Component
 * 
 * A revolutionary visualization showing how difficulty varies throughout a beatmap.
 * Uses a color gradient from green (easy) to red (hard) to show difficulty spikes.
 * Integrates with the timeline to show per-section difficulty analysis.
 * 
 * Features:
 * - Real-time difficulty calculation per segment
 * - Multiple difficulty metrics (density, complexity, coordination)
 * - Hover tooltips with detailed breakdowns
 * - Synchronized scrolling with timeline
 */

import { useMemo, useState, useRef, useCallback, useEffect } from 'react'
import type { HitObject, DrumComponent, Beatmap } from '@/types/beatmap'

interface DifficultyHeatmapProps {
    /** The beatmap to analyze */
    beatmap: Beatmap
    /** Current playback time in ms */
    currentTime: number
    /** Visible time range start */
    startTime: number
    /** Visible time range end */
    endTime: number
    /** Width of the component in pixels */
    width: number
    /** Height of the component in pixels */
    height?: number
    /** Callback when user clicks on a section */
    onSectionClick?: (timeMs: number) => void
    /** Show detailed breakdown on hover */
    showDetails?: boolean
}

interface DifficultySegment {
    startTime: number
    endTime: number
    overallDifficulty: number
    density: number
    complexity: number
    coordination: number
    techniques: string[]
    peakNote?: HitObject
}

// Difficulty calculation weights (matching desktop DifficultyCalculator.cs)
const WEIGHTS = {
    density: 0.3,
    complexity: 0.35,
    coordination: 0.35,
}

// Techniques that indicate higher difficulty (for future use when HitObject has technique field)
// const TECHNIQUE_DIFFICULTY: Record<string, number> = {
//     double_stroke: 1.2,
//     paradiddle: 1.4,
//     flam: 1.3,
//     ghost_note: 1.5,
//     accent: 1.1,
//     cross_stick: 1.2,
//     rimshot: 1.1,
//     roll: 1.6,
//     drag: 1.4,
//     four_on_floor: 0.8, // Common pattern, slightly easier
// }

// Component pairs that require high coordination
const COORDINATION_PAIRS: [DrumComponent, DrumComponent][] = [
    ['hihat_closed', 'snare'],
    ['hihat_open', 'kick'],
    ['kick', 'snare'],
    ['ride', 'snare'],
    ['crash', 'kick'],
    ['tom_high', 'tom_low'],
]

/**
 * Calculate difficulty metrics for a segment of hit objects
 */
function calculateSegmentDifficulty(
    notes: HitObject[],
    segmentDuration: number,
    _bpm: number
): Omit<DifficultySegment, 'startTime' | 'endTime'> {
    if (notes.length === 0) {
        return {
            overallDifficulty: 0,
            density: 0,
            complexity: 0,
            coordination: 0,
            techniques: [],
        }
    }

    // 1. Density: Notes per second, normalized to 0-10
    const density = Math.min((notes.length / (segmentDuration / 1000)) / 2, 10)

    // 2. Complexity: Unique components, velocity variance
    const uniqueComponents = new Set(notes.map(n => n.component)).size
    const velocities = notes.map(n => n.velocity)
    const velocityVariance = velocities.length > 1
        ? Math.sqrt(velocities.reduce((sum, v, _, arr) => {
            const mean = arr.reduce((a, b) => a + b, 0) / arr.length
            return sum + Math.pow(v - mean, 2)
        }, 0) / velocities.length)
        : 0

    // Calculate complexity score based on component variety and velocity variation
    const complexity = Math.min((uniqueComponents / 4) + (velocityVariance * 5), 10)

    // 3. Coordination: How often different limbs must play together
    let coordinationScore = 0
    for (let i = 0; i < notes.length - 1; i++) {
        const current = notes[i]
        const next = notes[i + 1]

        // Check for simultaneous or near-simultaneous notes (within 50ms)
        if (Math.abs(next.time - current.time) < 50) {
            // Check if this pair requires coordination
            const isPair = COORDINATION_PAIRS.some(
                ([a, b]) =>
                    (current.component === a && next.component === b) ||
                    (current.component === b && next.component === a)
            )
            if (isPair) {
                coordinationScore += 1
            }
        }

        // Check for fast hand switches
        if (next.time - current.time < 100) { // Less than 100ms gap
            if (current.component !== next.component) {
                coordinationScore += 0.5
            }
        }
    }
    const coordination = Math.min(coordinationScore / 3, 10)

    // Overall difficulty weighted average
    const overallDifficulty = Math.min(
        (density * WEIGHTS.density) +
        (complexity * WEIGHTS.complexity) +
        (coordination * WEIGHTS.coordination),
        10
    )

    // Find peak difficulty note (highest velocity)
    const peakNote = notes.reduce((peak, note) => {
        const noteScore = note.velocity
        const peakScore = peak ? peak.velocity : 0
        return noteScore > peakScore ? note : peak
    }, null as HitObject | null)

    return {
        overallDifficulty,
        density,
        complexity,
        coordination,
        techniques: [], // Techniques not available on HitObject type yet
        peakNote: peakNote || undefined,
    }
}

/**
 * Get color for a difficulty value (0-10)
 * Uses a gradient from green (0) through yellow (5) to red (10)
 */
function getDifficultyColor(difficulty: number, alpha: number = 1): string {
    const normalized = Math.max(0, Math.min(10, difficulty)) / 10

    // Green (easy) -> Yellow (medium) -> Red (hard)
    let r: number, g: number, b: number

    if (normalized < 0.5) {
        // Green to Yellow
        r = Math.round(normalized * 2 * 255)
        g = 200
        b = 50
    } else {
        // Yellow to Red
        r = 255
        g = Math.round((1 - (normalized - 0.5) * 2) * 200)
        b = 50
    }

    return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

/**
 * Get label for difficulty range
 */
function getDifficultyLabel(difficulty: number): string {
    if (difficulty < 2) return 'Easy'
    if (difficulty < 4) return 'Normal'
    if (difficulty < 6) return 'Hard'
    if (difficulty < 8) return 'Expert'
    return 'Master'
}

export function DifficultyHeatmap({
    beatmap,
    currentTime,
    startTime,
    endTime,
    width,
    height = 60,
    onSectionClick,
    showDetails = true,
}: DifficultyHeatmapProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null)
    const [hoveredSegment, setHoveredSegment] = useState<DifficultySegment | null>(null)
    const [mousePosition, setMousePosition] = useState<{ x: number; y: number } | null>(null)

    // Calculate segment size based on BPM (one bar per segment)
    const segmentDuration = useMemo(() => {
        const bpm = beatmap.timing.bpm || 120
        const msPerBeat = 60000 / bpm
        // Parse time signature like "4/4" to get beats per bar
        const timeSigParts = (beatmap.timing.timeSignature || '4/4').split('/')
        const beatsPerBar = parseInt(timeSigParts[0], 10) || 4
        return msPerBeat * beatsPerBar // One bar
    }, [beatmap.timing.bpm, beatmap.timing.timeSignature])

    // Calculate all difficulty segments
    const segments = useMemo(() => {
        const result: DifficultySegment[] = []
        const totalDuration = beatmap.audio.duration
        const notes = beatmap.hitObjects

        for (let start = 0; start < totalDuration; start += segmentDuration) {
            const end = start + segmentDuration
            const segmentNotes = notes.filter((n: HitObject) => n.time >= start && n.time < end)

            const metrics = calculateSegmentDifficulty(
                segmentNotes,
                segmentDuration,
                beatmap.timing.bpm || 120
            )

            result.push({
                startTime: start,
                endTime: end,
                ...metrics,
            })
        }

        return result
    }, [beatmap.hitObjects, beatmap.audio.duration, beatmap.timing.bpm, segmentDuration])

    // Calculate average and max difficulty for scaling
    const { avgDifficulty, maxDifficulty } = useMemo(() => {
        const difficulties = segments.map(s => s.overallDifficulty)
        const avg = difficulties.reduce((a, b) => a + b, 0) / difficulties.length
        const max = Math.max(...difficulties)
        return { avgDifficulty: avg, maxDifficulty: max }
    }, [segments])

    // Render the heatmap canvas
    useEffect(() => {
        const canvas = canvasRef.current
        if (!canvas) return

        const ctx = canvas.getContext('2d')
        if (!ctx) return

        // Set canvas size for retina
        const dpr = window.devicePixelRatio || 1
        canvas.width = width * dpr
        canvas.height = height * dpr
        ctx.scale(dpr, dpr)

        // Clear canvas
        ctx.clearRect(0, 0, width, height)

        // Calculate visible range
        const visibleDuration = endTime - startTime
        const pixelsPerMs = width / visibleDuration

        // Draw background
        ctx.fillStyle = 'rgba(30, 30, 40, 0.8)'
        ctx.fillRect(0, 0, width, height)

        // Draw each visible segment
        segments.forEach(segment => {
            if (segment.endTime < startTime || segment.startTime > endTime) return

            const x = (segment.startTime - startTime) * pixelsPerMs
            const segmentWidth = segmentDuration * pixelsPerMs

            // Main difficulty bar
            const barHeight = (segment.overallDifficulty / 10) * (height - 20)

            // Gradient fill
            const gradient = ctx.createLinearGradient(x, height - barHeight - 10, x, height - 10)
            gradient.addColorStop(0, getDifficultyColor(segment.overallDifficulty, 0.9))
            gradient.addColorStop(1, getDifficultyColor(segment.overallDifficulty, 0.4))

            ctx.fillStyle = gradient
            ctx.fillRect(x, height - barHeight - 10, segmentWidth - 1, barHeight)

            // Draw mini-indicators for sub-metrics
            const indicatorHeight = 4
            const indicatorY = height - 8
            const indicatorWidth = segmentWidth / 3 - 1

            // Density indicator
            ctx.fillStyle = getDifficultyColor(segment.density, 0.7)
            ctx.fillRect(x, indicatorY, indicatorWidth, indicatorHeight)

            // Complexity indicator
            ctx.fillStyle = getDifficultyColor(segment.complexity, 0.7)
            ctx.fillRect(x + indicatorWidth + 1, indicatorY, indicatorWidth, indicatorHeight)

            // Coordination indicator
            ctx.fillStyle = getDifficultyColor(segment.coordination, 0.7)
            ctx.fillRect(x + (indicatorWidth + 1) * 2, indicatorY, indicatorWidth, indicatorHeight)
        })

        // Draw playhead
        const playheadX = (currentTime - startTime) * pixelsPerMs
        if (playheadX >= 0 && playheadX <= width) {
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.9)'
            ctx.lineWidth = 2
            ctx.beginPath()
            ctx.moveTo(playheadX, 0)
            ctx.lineTo(playheadX, height)
            ctx.stroke()
        }

        // Draw average difficulty line
        const avgLineY = height - 10 - (avgDifficulty / 10) * (height - 20)
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)'
        ctx.lineWidth = 1
        ctx.setLineDash([4, 4])
        ctx.beginPath()
        ctx.moveTo(0, avgLineY)
        ctx.lineTo(width, avgLineY)
        ctx.stroke()
        ctx.setLineDash([])

    }, [segments, currentTime, startTime, endTime, width, height, segmentDuration, avgDifficulty])

    // Handle mouse events
    const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
        const canvas = canvasRef.current
        if (!canvas) return

        const rect = canvas.getBoundingClientRect()
        const x = e.clientX - rect.left

        setMousePosition({ x: e.clientX, y: e.clientY })

        // Find which segment is being hovered
        const visibleDuration = endTime - startTime
        const pixelsPerMs = width / visibleDuration
        const timeAtMouse = startTime + (x / pixelsPerMs)

        const segment = segments.find(
            s => timeAtMouse >= s.startTime && timeAtMouse < s.endTime
        )
        setHoveredSegment(segment || null)
    }, [segments, startTime, endTime, width])

    const handleMouseLeave = useCallback(() => {
        setHoveredSegment(null)
        setMousePosition(null)
    }, [])

    const handleClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
        if (!onSectionClick) return

        const canvas = canvasRef.current
        if (!canvas) return

        const rect = canvas.getBoundingClientRect()
        const x = e.clientX - rect.left

        const visibleDuration = endTime - startTime
        const pixelsPerMs = width / visibleDuration
        const timeAtClick = startTime + (x / pixelsPerMs)

        onSectionClick(timeAtClick)
    }, [onSectionClick, startTime, endTime, width])

    // Format time as mm:ss
    const formatTime = (ms: number) => {
        const seconds = Math.floor(ms / 1000)
        const minutes = Math.floor(seconds / 60)
        const secs = seconds % 60
        return `${minutes}:${secs.toString().padStart(2, '0')}`
    }

    return (
        <div className="relative">
            {/* Header */}
            <div className="flex items-center justify-between mb-1 px-1">
                <span className="text-xs text-gray-400">Difficulty Heatmap</span>
                <div className="flex items-center gap-2 text-xs text-gray-500">
                    <span>Avg: {avgDifficulty.toFixed(1)}★</span>
                    <span>Peak: {maxDifficulty.toFixed(1)}★</span>
                </div>
            </div>

            {/* Canvas */}
            <canvas
                ref={canvasRef}
                style={{ width, height }}
                className="rounded cursor-crosshair"
                onMouseMove={handleMouseMove}
                onMouseLeave={handleMouseLeave}
                onClick={handleClick}
            />

            {/* Legend */}
            <div className="flex items-center justify-between mt-1 px-1 text-xs text-gray-500">
                <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1">
                        <div className="w-2 h-2 rounded-full bg-green-500" />
                        <span>Density</span>
                    </div>
                    <div className="flex items-center gap-1">
                        <div className="w-2 h-2 rounded-full bg-yellow-500" />
                        <span>Complexity</span>
                    </div>
                    <div className="flex items-center gap-1">
                        <div className="w-2 h-2 rounded-full bg-red-500" />
                        <span>Coordination</span>
                    </div>
                </div>
                <div className="flex items-center gap-1">
                    <div
                        className="w-24 h-2 rounded"
                        style={{
                            background: 'linear-gradient(to right, rgb(50, 200, 50), rgb(255, 200, 50), rgb(255, 50, 50))',
                        }}
                    />
                    <span>Easy → Hard</span>
                </div>
            </div>

            {/* Hover Tooltip */}
            {showDetails && hoveredSegment && mousePosition && (
                <div
                    className="fixed z-50 bg-gray-900 border border-gray-700 rounded-lg p-3 shadow-xl pointer-events-none"
                    style={{
                        left: mousePosition.x + 10,
                        top: mousePosition.y + 10,
                        maxWidth: 280,
                    }}
                >
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-white">
                            {formatTime(hoveredSegment.startTime)} - {formatTime(hoveredSegment.endTime)}
                        </span>
                        <span
                            className="text-sm font-bold px-2 py-0.5 rounded"
                            style={{
                                backgroundColor: getDifficultyColor(hoveredSegment.overallDifficulty, 0.3),
                                color: getDifficultyColor(hoveredSegment.overallDifficulty),
                            }}
                        >
                            {hoveredSegment.overallDifficulty.toFixed(1)}★ {getDifficultyLabel(hoveredSegment.overallDifficulty)}
                        </span>
                    </div>

                    {/* Metrics breakdown */}
                    <div className="space-y-1 text-xs">
                        <div className="flex items-center justify-between">
                            <span className="text-gray-400">Note Density</span>
                            <div className="flex items-center gap-1">
                                <div
                                    className="w-16 h-1.5 rounded-full bg-gray-700 overflow-hidden"
                                >
                                    <div
                                        className="h-full rounded-full transition-all"
                                        style={{
                                            width: `${(hoveredSegment.density / 10) * 100}%`,
                                            backgroundColor: getDifficultyColor(hoveredSegment.density),
                                        }}
                                    />
                                </div>
                                <span className="text-white w-8 text-right">
                                    {hoveredSegment.density.toFixed(1)}
                                </span>
                            </div>
                        </div>
                        <div className="flex items-center justify-between">
                            <span className="text-gray-400">Complexity</span>
                            <div className="flex items-center gap-1">
                                <div
                                    className="w-16 h-1.5 rounded-full bg-gray-700 overflow-hidden"
                                >
                                    <div
                                        className="h-full rounded-full transition-all"
                                        style={{
                                            width: `${(hoveredSegment.complexity / 10) * 100}%`,
                                            backgroundColor: getDifficultyColor(hoveredSegment.complexity),
                                        }}
                                    />
                                </div>
                                <span className="text-white w-8 text-right">
                                    {hoveredSegment.complexity.toFixed(1)}
                                </span>
                            </div>
                        </div>
                        <div className="flex items-center justify-between">
                            <span className="text-gray-400">Coordination</span>
                            <div className="flex items-center gap-1">
                                <div
                                    className="w-16 h-1.5 rounded-full bg-gray-700 overflow-hidden"
                                >
                                    <div
                                        className="h-full rounded-full transition-all"
                                        style={{
                                            width: `${(hoveredSegment.coordination / 10) * 100}%`,
                                            backgroundColor: getDifficultyColor(hoveredSegment.coordination),
                                        }}
                                    />
                                </div>
                                <span className="text-white w-8 text-right">
                                    {hoveredSegment.coordination.toFixed(1)}
                                </span>
                            </div>
                        </div>
                    </div>

                    {/* Techniques in this section */}
                    {hoveredSegment.techniques.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-gray-700">
                            <span className="text-xs text-gray-400">Techniques:</span>
                            <div className="flex flex-wrap gap-1 mt-1">
                                {hoveredSegment.techniques.map(tech => (
                                    <span
                                        key={tech}
                                        className="text-xs px-1.5 py-0.5 bg-primary-500/20 text-primary-400 rounded"
                                    >
                                        {tech.replace(/_/g, ' ')}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}

export default DifficultyHeatmap
