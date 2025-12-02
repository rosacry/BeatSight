import { useRef, useEffect, useCallback, useMemo, useState } from 'react'
import type {
    HitObject,
    DrumComponent,
    TimelineViewport,
    TimelineSelection,
    SnapSettings,
    NoteDiff,
} from '../../types/beatmap'
import { LANE_COLORS, LANE_LABELS } from '../../types/beatmap'

interface TimelineCanvasProps {
    /** All hit objects to display */
    hitObjects: HitObject[]
    /** Comparison hit objects for diff view (optional) */
    comparisonObjects?: HitObject[]
    /** Which lanes to show (drum components) */
    lanes: DrumComponent[]
    /** BPM for grid lines */
    bpm: number
    /** Audio duration in milliseconds */
    duration: number
    /** Current playback position in milliseconds */
    currentTime: number
    /** Viewport settings */
    viewport: TimelineViewport
    /** Selection state */
    selection: TimelineSelection
    /** Snap settings */
    snap: SnapSettings
    /** Whether diff mode is enabled */
    showDiff?: boolean
    /** Whether beat grid is visible - matches desktop EditorTimeline */
    beatGridVisible?: boolean
    /** Whether onset detection layer is visible - matches desktop EditorTimeline */
    onsetLayerVisible?: boolean
    /** Waveform scale (0.5-2.5) - matches desktop EditorTimeline */
    waveformScale?: number
    /** Callback when viewport changes */
    onViewportChange: (viewport: TimelineViewport) => void
    /** Callback when selection changes */
    onSelectionChange: (selection: TimelineSelection) => void
    /** Callback when a note is clicked */
    onNoteClick?: (note: HitObject, event: React.MouseEvent) => void
    /** Callback when a note is dragged to a new position */
    onNoteDrag?: (noteId: string, newTime: number, newLane: number) => void
    /** Callback when seeking to a position */
    onSeek?: (time: number) => void
    /** Canvas height */
    height?: number
}

const LANE_HEIGHT = 32
const NOTE_RADIUS = 10
const HEADER_HEIGHT = 24
const RULER_HEIGHT = 28
const PLAYHEAD_COLOR = '#f97316' // orange-500

/**
 * Zoom limits matching desktop EditorTimeline.cs
 * Desktop: MinZoom = 0.2, MaxZoom = 5.0 (in their coordinate system)
 */
const MIN_ZOOM = 0.02  // pixels per ms
const MAX_ZOOM = 0.5   // pixels per ms

export function TimelineCanvas({
    hitObjects,
    comparisonObjects,
    lanes,
    bpm,
    duration,
    currentTime,
    viewport,
    selection,
    snap,
    showDiff = false,
    beatGridVisible = true,
    onsetLayerVisible = false,
    waveformScale = 1.0,
    onViewportChange,
    onSelectionChange,
    onNoteClick,
    onNoteDrag,
    onSeek,
    height = 400,
}: TimelineCanvasProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null)
    const containerRef = useRef<HTMLDivElement>(null)
    const [isDragging, setIsDragging] = useState(false)
    const [dragNote, setDragNote] = useState<{ note: HitObject; startX: number; startY: number } | null>(null)
    const [isSelecting, setIsSelecting] = useState(false)
    const [selectStart, setSelectStart] = useState<{ x: number; y: number } | null>(null)

    // Calculate dimensions
    const canvasHeight = HEADER_HEIGHT + RULER_HEIGHT + lanes.length * LANE_HEIGHT
    const totalHeight = Math.max(height, canvasHeight)

    // Convert time to X position
    const timeToX = useCallback(
        (time: number): number => {
            return (time - viewport.startTime) * viewport.zoom
        },
        [viewport]
    )

    // Convert X position to time
    const xToTime = useCallback(
        (x: number): number => {
            return x / viewport.zoom + viewport.startTime
        },
        [viewport]
    )

    // Convert lane index to Y position
    const laneToY = useCallback(
        (laneIndex: number): number => {
            return HEADER_HEIGHT + RULER_HEIGHT + laneIndex * LANE_HEIGHT + LANE_HEIGHT / 2
        },
        []
    )

    // Convert Y position to lane index
    const yToLane = useCallback(
        (y: number): number => {
            const laneY = y - HEADER_HEIGHT - RULER_HEIGHT
            return Math.floor(laneY / LANE_HEIGHT)
        },
        []
    )

    // Snap time to grid based on snap settings
    const snapTime = useCallback(
        (time: number): number => {
            if (!snap.enabled) return time

            const beatDuration = 60000 / bpm
            const snapInterval = beatDuration / snap.divisor
            return Math.round(time / snapInterval) * snapInterval
        },
        [snap, bpm]
    )

    // Compute note diffs for visualization
    const noteDiffs = useMemo((): Map<string, NoteDiff> => {
        if (!showDiff || !comparisonObjects) return new Map()

        const diffs = new Map<string, NoteDiff>()
        const comparisonMap = new Map(comparisonObjects.map((n) => [n.id, n]))

        // Check each current note
        for (const note of hitObjects) {
            const compNote = comparisonMap.get(note.id)
            if (!compNote) {
                diffs.set(note.id, { type: 'added', editedNote: note })
            } else {
                const timeDelta = note.time - compNote.time
                const laneDelta = note.lane - compNote.lane
                const velocityDelta = note.velocity - compNote.velocity

                if (timeDelta !== 0 || laneDelta !== 0 || velocityDelta !== 0) {
                    diffs.set(note.id, {
                        type: 'modified',
                        originalNote: compNote,
                        editedNote: note,
                        timeDelta,
                        laneDelta,
                        velocityDelta,
                    })
                } else {
                    diffs.set(note.id, { type: 'unchanged', originalNote: compNote, editedNote: note })
                }
            }
        }

        // Check for removed notes
        for (const compNote of comparisonObjects) {
            if (!hitObjects.find((n) => n.id === compNote.id)) {
                diffs.set(compNote.id, { type: 'removed', originalNote: compNote })
            }
        }

        return diffs
    }, [hitObjects, comparisonObjects, showDiff])

    // Draw the canvas
    const draw = useCallback(() => {
        const canvas = canvasRef.current
        if (!canvas) return

        const ctx = canvas.getContext('2d')
        if (!ctx) return

        const width = canvas.width / (window.devicePixelRatio || 1)

        // Clear canvas
        ctx.fillStyle = '#1f2937' // gray-800
        ctx.fillRect(0, 0, canvas.width, canvas.height)

        // Draw lane headers (left sidebar)
        ctx.fillStyle = '#111827' // gray-900
        ctx.fillRect(0, 0, 60, canvas.height)

        // Draw lane labels
        ctx.font = '11px system-ui, sans-serif'
        ctx.textAlign = 'right'
        lanes.forEach((lane, i) => {
            const y = laneToY(i)
            ctx.fillStyle = LANE_COLORS[lane]
            ctx.fillText(LANE_LABELS[lane], 55, y + 4)
        })

        // Draw ruler background
        ctx.fillStyle = '#374151' // gray-700
        ctx.fillRect(60, HEADER_HEIGHT, width - 60, RULER_HEIGHT)

        // Draw beat grid lines (conditional on beatGridVisible - matches desktop EditorTimeline)
        const beatDuration = 60000 / bpm
        const startBeat = Math.floor(viewport.startTime / beatDuration)
        const endBeat = Math.ceil(viewport.endTime / beatDuration)

        ctx.textAlign = 'center'
        ctx.font = '10px system-ui, sans-serif'

        for (let beat = startBeat; beat <= endBeat; beat++) {
            const time = beat * beatDuration
            const x = 60 + timeToX(time)

            if (x < 60 || x > width) continue

            // Draw grid line (only if beatGridVisible)
            if (beatGridVisible) {
                ctx.strokeStyle = beat % 4 === 0 ? '#6b7280' : '#4b5563'
                ctx.lineWidth = beat % 4 === 0 ? 1 : 0.5
                ctx.beginPath()
                ctx.moveTo(x, HEADER_HEIGHT + RULER_HEIGHT)
                ctx.lineTo(x, canvas.height)
                ctx.stroke()
            }

            // Draw beat number on ruler (every 4 beats) - always shown
            if (beat % 4 === 0) {
                ctx.fillStyle = '#d1d5db' // gray-300
                ctx.fillText(`${beat / 4 + 1}`, x, HEADER_HEIGHT + RULER_HEIGHT - 8)
            }
        }

        // TODO: Draw waveform layer (scaled by waveformScale)
        // This will require fetching/computing waveform data from the audio
        // Desktop uses WaveformGraph with configurable WaveformScale (0.5 to 2.5)
        void waveformScale // Reserved for future waveform rendering

        // TODO: Draw onset detection layer (when onsetLayerVisible)
        // Desktop has OnsetDetectionLayer that shows detected transients
        void onsetLayerVisible // Reserved for future onset detection visualization

        // Draw lane backgrounds
        lanes.forEach((_, i) => {
            const y = HEADER_HEIGHT + RULER_HEIGHT + i * LANE_HEIGHT
            ctx.fillStyle = i % 2 === 0 ? '#1f2937' : '#1a1f2e'
            ctx.fillRect(60, y, width - 60, LANE_HEIGHT)
        })

        // Draw lane separator lines
        ctx.strokeStyle = '#374151'
        ctx.lineWidth = 1
        lanes.forEach((_, i) => {
            const y = HEADER_HEIGHT + RULER_HEIGHT + i * LANE_HEIGHT
            ctx.beginPath()
            ctx.moveTo(60, y)
            ctx.lineTo(width, y)
            ctx.stroke()
        })

        // Draw removed notes (diff mode)
        if (showDiff) {
            noteDiffs.forEach((diff) => {
                if (diff.type === 'removed' && diff.originalNote) {
                    const note = diff.originalNote
                    const laneIndex = lanes.indexOf(note.component)
                    if (laneIndex === -1) return

                    const x = 60 + timeToX(note.time)
                    const y = laneToY(laneIndex)

                    if (x < 60 || x > width) return

                    // Draw with strikethrough effect
                    ctx.strokeStyle = '#ef4444' // red-500
                    ctx.lineWidth = 2
                    ctx.setLineDash([4, 4])
                    ctx.beginPath()
                    ctx.arc(x, y, NOTE_RADIUS, 0, Math.PI * 2)
                    ctx.stroke()
                    ctx.setLineDash([])

                    // Strikethrough line
                    ctx.beginPath()
                    ctx.moveTo(x - NOTE_RADIUS - 4, y)
                    ctx.lineTo(x + NOTE_RADIUS + 4, y)
                    ctx.stroke()
                }
            })
        }

        // Draw hit objects
        hitObjects.forEach((note) => {
            const laneIndex = lanes.indexOf(note.component)
            if (laneIndex === -1) return

            const x = 60 + timeToX(note.time)
            const y = laneToY(laneIndex)

            if (x < 60 || x > width) return

            const isSelected = selection.noteIds.has(note.id)
            const diff = noteDiffs.get(note.id)

            // Draw note
            ctx.beginPath()
            ctx.arc(x, y, NOTE_RADIUS, 0, Math.PI * 2)

            // Color based on diff status or component
            if (showDiff && diff) {
                switch (diff.type) {
                    case 'added':
                        ctx.fillStyle = '#22c55e' // green-500
                        break
                    case 'modified':
                        ctx.fillStyle = '#f59e0b' // amber-500
                        break
                    default:
                        ctx.fillStyle = LANE_COLORS[note.component]
                }
            } else {
                ctx.fillStyle = LANE_COLORS[note.component]
            }

            // Velocity affects opacity
            ctx.globalAlpha = 0.4 + note.velocity * 0.6
            ctx.fill()
            ctx.globalAlpha = 1

            // Selection ring
            if (isSelected) {
                ctx.strokeStyle = '#ffffff'
                ctx.lineWidth = 2
                ctx.stroke()
            }

            // Diff indicator arrow for modified notes
            if (showDiff && diff?.type === 'modified' && diff.originalNote) {
                const origX = 60 + timeToX(diff.originalNote.time)
                const origLaneIndex = lanes.indexOf(diff.originalNote.component)
                const origY = laneToY(origLaneIndex)

                ctx.strokeStyle = '#f59e0b'
                ctx.lineWidth = 1
                ctx.setLineDash([3, 3])
                ctx.beginPath()
                ctx.moveTo(origX, origY)
                ctx.lineTo(x, y)
                ctx.stroke()
                ctx.setLineDash([])
            }
        })

        // Draw playhead
        const playheadX = 60 + timeToX(currentTime)
        if (playheadX >= 60 && playheadX <= width) {
            ctx.strokeStyle = PLAYHEAD_COLOR
            ctx.lineWidth = 2
            ctx.beginPath()
            ctx.moveTo(playheadX, HEADER_HEIGHT)
            ctx.lineTo(playheadX, canvas.height)
            ctx.stroke()

            // Playhead triangle
            ctx.fillStyle = PLAYHEAD_COLOR
            ctx.beginPath()
            ctx.moveTo(playheadX, HEADER_HEIGHT)
            ctx.lineTo(playheadX - 6, HEADER_HEIGHT - 8)
            ctx.lineTo(playheadX + 6, HEADER_HEIGHT - 8)
            ctx.closePath()
            ctx.fill()
        }

        // Draw selection rectangle if selecting
        if (isSelecting && selectStart) {
            // This would draw a rectangle, but we'll skip for now
        }
    }, [
        hitObjects,
        lanes,
        bpm,
        currentTime,
        viewport,
        selection,
        showDiff,
        beatGridVisible,
        waveformScale,
        onsetLayerVisible,
        noteDiffs,
        timeToX,
        laneToY,
        isSelecting,
        selectStart,
    ])

    // Handle canvas resize
    useEffect(() => {
        const canvas = canvasRef.current
        const container = containerRef.current
        if (!canvas || !container) return

        const resizeObserver = new ResizeObserver((entries) => {
            for (const entry of entries) {
                const { width } = entry.contentRect
                const dpr = window.devicePixelRatio || 1
                canvas.width = width * dpr
                canvas.height = totalHeight * dpr
                canvas.style.width = `${width}px`
                canvas.style.height = `${totalHeight}px`

                const ctx = canvas.getContext('2d')
                if (ctx) {
                    ctx.scale(dpr, dpr)
                }

                // Update viewport to match canvas width
                const viewDuration = (width - 60) / viewport.zoom
                onViewportChange({
                    ...viewport,
                    endTime: viewport.startTime + viewDuration,
                })

                draw()
            }
        })

        resizeObserver.observe(container)
        return () => resizeObserver.disconnect()
        // We only want to re-run when zoom changes, not on every viewport update
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [totalHeight, viewport.zoom, onViewportChange, draw])

    // Redraw when dependencies change
    useEffect(() => {
        draw()
    }, [draw])

    // Find note at position
    const findNoteAtPosition = useCallback(
        (x: number, y: number): HitObject | null => {
            const laneIndex = yToLane(y)

            if (laneIndex < 0 || laneIndex >= lanes.length) return null

            const lane = lanes[laneIndex]
            const hitRadius = NOTE_RADIUS + 4 // Slightly larger hit area

            for (const note of hitObjects) {
                if (note.component !== lane) continue

                const noteX = timeToX(note.time) + 60
                const noteY = laneToY(laneIndex)

                const dx = x - noteX
                const dy = y - noteY

                if (Math.sqrt(dx * dx + dy * dy) <= hitRadius) {
                    return note
                }
            }

            return null
        },
        [hitObjects, lanes, timeToX, laneToY, yToLane]
    )

    // Mouse event handlers
    const handleMouseDown = useCallback(
        (e: React.MouseEvent) => {
            const canvas = canvasRef.current
            if (!canvas) return

            const rect = canvas.getBoundingClientRect()
            const x = e.clientX - rect.left
            const y = e.clientY - rect.top

            // Check if clicking on ruler for seeking
            if (y < HEADER_HEIGHT + RULER_HEIGHT && y >= HEADER_HEIGHT && x > 60) {
                const time = xToTime(x - 60)
                onSeek?.(Math.max(0, Math.min(time, duration)))
                return
            }

            // Check if clicking on a note
            const note = findNoteAtPosition(x, y)
            if (note) {
                if (e.shiftKey) {
                    // Add/remove from selection
                    const newSelection = new Set(selection.noteIds)
                    if (newSelection.has(note.id)) {
                        newSelection.delete(note.id)
                    } else {
                        newSelection.add(note.id)
                    }
                    onSelectionChange({ noteIds: newSelection })
                } else if (!selection.noteIds.has(note.id)) {
                    // Select only this note
                    onSelectionChange({ noteIds: new Set([note.id]) })
                }

                // Start dragging
                setIsDragging(true)
                setDragNote({ note, startX: x, startY: y })
                onNoteClick?.(note, e)
            } else {
                // Clear selection or start rectangle select
                if (!e.shiftKey) {
                    onSelectionChange({ noteIds: new Set() })
                }
                setIsSelecting(true)
                setSelectStart({ x, y })
            }
        },
        [selection, xToTime, duration, onSeek, findNoteAtPosition, onSelectionChange, onNoteClick]
    )

    const handleMouseMove = useCallback(
        (e: React.MouseEvent) => {
            if (!isDragging || !dragNote) return

            const canvas = canvasRef.current
            if (!canvas) return

            const rect = canvas.getBoundingClientRect()
            const x = e.clientX - rect.left
            const y = e.clientY - rect.top

            // Calculate new time and lane
            let newTime = xToTime(x - 60)
            newTime = snapTime(newTime)
            newTime = Math.max(0, Math.min(newTime, duration))

            const newLaneIndex = yToLane(y)
            const clampedLaneIndex = Math.max(0, Math.min(newLaneIndex, lanes.length - 1))

            onNoteDrag?.(dragNote.note.id, newTime, clampedLaneIndex)
        },
        [isDragging, dragNote, xToTime, snapTime, duration, yToLane, lanes.length, onNoteDrag]
    )

    const handleMouseUp = useCallback(() => {
        setIsDragging(false)
        setDragNote(null)
        setIsSelecting(false)
        setSelectStart(null)
    }, [])

    // Wheel handler for zooming/scrolling
    const handleWheel = useCallback(
        (e: React.WheelEvent) => {
            e.preventDefault()

            if (e.ctrlKey || e.metaKey) {
                // Zoom - clamp to MIN_ZOOM/MAX_ZOOM (matches desktop EditorTimeline limits)
                const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1
                const newZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, viewport.zoom * zoomFactor))

                // Zoom towards mouse position
                const canvas = canvasRef.current
                if (!canvas) return

                const rect = canvas.getBoundingClientRect()
                const mouseX = e.clientX - rect.left - 60
                const mouseTime = xToTime(mouseX)

                const newStartTime = mouseTime - mouseX / newZoom
                const viewDuration = (rect.width - 60) / newZoom

                onViewportChange({
                    startTime: Math.max(0, newStartTime),
                    endTime: Math.min(duration, newStartTime + viewDuration),
                    zoom: newZoom,
                })
            } else {
                // Scroll horizontally
                const scrollAmount = e.deltaY / viewport.zoom
                const newStartTime = Math.max(0, Math.min(duration - (viewport.endTime - viewport.startTime), viewport.startTime + scrollAmount))
                const viewDuration = viewport.endTime - viewport.startTime

                onViewportChange({
                    ...viewport,
                    startTime: newStartTime,
                    endTime: newStartTime + viewDuration,
                })
            }
        },
        [viewport, duration, xToTime, onViewportChange]
    )

    return (
        <div
            ref={containerRef}
            className="relative w-full overflow-hidden rounded-lg border border-gray-700 bg-gray-800"
            style={{ height: totalHeight }}
        >
            <canvas
                ref={canvasRef}
                className="block"
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
                onWheel={handleWheel}
            />
        </div>
    )
}
