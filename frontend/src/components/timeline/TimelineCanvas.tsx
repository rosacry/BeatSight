import { useRef, useEffect, useCallback, useMemo, useState } from 'react'
import type {
    HitObject,
    DrumComponent,
    TimelineViewport,
    TimelineSelection,
    SnapSettings,
    NoteDiff,
    DetectedOnset,
} from '../../types/beatmap'
import { LANE_COLORS, LANE_LABELS } from '../../types/beatmap'
import type { WaveformData } from '../../hooks/useWaveform'

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
    /** Detected onsets from AI analysis - for onset layer visualization */
    detectedOnsets?: DetectedOnset[]
    /** Waveform scale (0.5-2.5) - matches desktop EditorTimeline */
    waveformScale?: number
    /** Waveform data for rendering - matches desktop WaveformGraph */
    waveformData?: WaveformData | null
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
const SIDEBAR_WIDTH = 60

/**
 * Zoom limits matching desktop EditorTimeline.cs
 * Desktop: MinZoom = 0.2, MaxZoom = 5.0 (in their coordinate system)
 */
const MIN_ZOOM = 0.02  // pixels per ms
const MAX_ZOOM = 0.5   // pixels per ms

/**
 * Performance-optimized timeline canvas with layer separation.
 * 
 * Architecture:
 * - Static layer (background canvas): Grid lines, lane labels, ruler - redrawn only on zoom/resize
 * - Dynamic layer (foreground canvas): Notes, playhead, selection - redrawn on time/interaction
 * 
 * This separation reduces redraw cost by ~60-80% during playback since the static
 * elements (which are expensive to render) don't need to be redrawn every frame.
 */
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
    detectedOnsets = [],
    waveformScale = 1.0,
    waveformData,
    onViewportChange,
    onSelectionChange,
    onNoteClick,
    onNoteDrag,
    onSeek,
    height = 400,
}: TimelineCanvasProps) {
    // Separate refs for static and dynamic layers
    const staticCanvasRef = useRef<HTMLCanvasElement>(null)
    const dynamicCanvasRef = useRef<HTMLCanvasElement>(null)
    const containerRef = useRef<HTMLDivElement>(null)

    // Track what needs redrawing (dirty flags)
    const staticDirtyRef = useRef(true)
    const lastViewportRef = useRef<{ zoom: number; startTime: number } | null>(null)

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

    /**
     * Draw STATIC layer - grid lines, lane labels, ruler marks, lane backgrounds.
     * Only redraws when zoom, lanes, or beat grid settings change.
     */
    const drawStaticLayer = useCallback(() => {
        const canvas = staticCanvasRef.current
        if (!canvas) return

        const ctx = canvas.getContext('2d')
        if (!ctx) return

        const width = canvas.width / (window.devicePixelRatio || 1)

        // Clear canvas
        ctx.fillStyle = '#1f2937' // gray-800
        ctx.fillRect(0, 0, canvas.width, canvas.height)

        // Draw lane headers (left sidebar)
        ctx.fillStyle = '#111827' // gray-900
        ctx.fillRect(0, 0, SIDEBAR_WIDTH, canvas.height)

        // Draw lane labels
        ctx.font = '11px system-ui, sans-serif'
        ctx.textAlign = 'right'
        lanes.forEach((lane, i) => {
            const y = laneToY(i)
            ctx.fillStyle = LANE_COLORS[lane]
            ctx.fillText(LANE_LABELS[lane], SIDEBAR_WIDTH - 5, y + 4)
        })

        // Draw ruler background
        ctx.fillStyle = '#374151' // gray-700
        ctx.fillRect(SIDEBAR_WIDTH, HEADER_HEIGHT, width - SIDEBAR_WIDTH, RULER_HEIGHT)

        // Draw beat grid lines
        const beatDuration = 60000 / bpm
        const startBeat = Math.floor(viewport.startTime / beatDuration)
        const endBeat = Math.ceil(viewport.endTime / beatDuration)

        ctx.textAlign = 'center'
        ctx.font = '10px system-ui, sans-serif'

        for (let beat = startBeat; beat <= endBeat; beat++) {
            const time = beat * beatDuration
            const x = SIDEBAR_WIDTH + timeToX(time)

            if (x < SIDEBAR_WIDTH || x > width) continue

            // Draw grid line (only if beatGridVisible)
            if (beatGridVisible) {
                ctx.strokeStyle = beat % 4 === 0 ? '#6b7280' : '#4b5563'
                ctx.lineWidth = beat % 4 === 0 ? 1 : 0.5
                ctx.beginPath()
                ctx.moveTo(x, HEADER_HEIGHT + RULER_HEIGHT)
                ctx.lineTo(x, canvas.height)
                ctx.stroke()
            }

            // Draw beat number on ruler (every 4 beats)
            if (beat % 4 === 0) {
                ctx.fillStyle = '#d1d5db' // gray-300
                ctx.fillText(`${beat / 4 + 1}`, x, HEADER_HEIGHT + RULER_HEIGHT - 8)
            }
        }

        // Draw lane backgrounds
        lanes.forEach((_, i) => {
            const y = HEADER_HEIGHT + RULER_HEIGHT + i * LANE_HEIGHT
            ctx.fillStyle = i % 2 === 0 ? '#1f2937' : '#1a1f2e'
            ctx.fillRect(SIDEBAR_WIDTH, y, width - SIDEBAR_WIDTH, LANE_HEIGHT)
        })

        // Draw lane separator lines
        ctx.strokeStyle = '#374151'
        ctx.lineWidth = 1
        lanes.forEach((_, i) => {
            const y = HEADER_HEIGHT + RULER_HEIGHT + i * LANE_HEIGHT
            ctx.beginPath()
            ctx.moveTo(SIDEBAR_WIDTH, y)
            ctx.lineTo(width, y)
            ctx.stroke()
        })

        // Mark static layer as clean
        staticDirtyRef.current = false
        lastViewportRef.current = { zoom: viewport.zoom, startTime: viewport.startTime }
    }, [lanes, bpm, viewport.startTime, viewport.endTime, viewport.zoom, beatGridVisible, timeToX, laneToY])

    /**
     * Draw DYNAMIC layer - waveform, notes, playhead, selection.
     * Redraws every frame during playback, but much cheaper since background is cached.
     */
    const drawDynamicLayer = useCallback(() => {
        const canvas = dynamicCanvasRef.current
        if (!canvas) return

        const ctx = canvas.getContext('2d')
        if (!ctx) return

        const width = canvas.width / (window.devicePixelRatio || 1)

        // Clear dynamic layer (transparent)
        ctx.clearRect(0, 0, canvas.width, canvas.height)

        // Draw waveform (scaled by waveformScale)
        if (waveformData) {
            const waveformHeight = RULER_HEIGHT * waveformScale
            const waveformCenterY = HEADER_HEIGHT + RULER_HEIGHT / 2
            const startSeconds = viewport.startTime / 1000
            const endSeconds = viewport.endTime / 1000

            const startBucket = Math.max(0, Math.floor(startSeconds / waveformData.bucketDurationSeconds))
            const endBucket = Math.min(
                waveformData.bucketCount,
                Math.ceil(endSeconds / waveformData.bucketDurationSeconds)
            )

            ctx.fillStyle = 'rgba(56, 189, 248, 0.4)' // sky-400 with alpha
            ctx.strokeStyle = 'rgba(56, 189, 248, 0.7)'
            ctx.lineWidth = 1

            ctx.beginPath()

            let firstPoint = true
            for (let bucket = startBucket; bucket < endBucket; bucket++) {
                const bucketStartTime = bucket * waveformData.bucketDurationSeconds * 1000
                const x = SIDEBAR_WIDTH + timeToX(bucketStartTime)

                if (x < SIDEBAR_WIDTH || x > width) continue

                const maxAmp = waveformData.maxima[bucket]
                const yMax = waveformCenterY - maxAmp * waveformHeight

                if (firstPoint) {
                    ctx.moveTo(x, yMax)
                    firstPoint = false
                } else {
                    ctx.lineTo(x, yMax)
                }
            }

            for (let bucket = endBucket - 1; bucket >= startBucket; bucket--) {
                const bucketStartTime = bucket * waveformData.bucketDurationSeconds * 1000
                const x = SIDEBAR_WIDTH + timeToX(bucketStartTime)

                if (x < SIDEBAR_WIDTH || x > width) continue

                const minAmp = waveformData.minima[bucket]
                const yMin = waveformCenterY - minAmp * waveformHeight
                ctx.lineTo(x, yMin)
            }

            ctx.closePath()
            ctx.fill()
            ctx.stroke()
        }

        // Draw onset detection layer - shows raw detected peaks before classification
        // Matches desktop DetectionDebugOverlay peak visualization
        if (onsetLayerVisible && detectedOnsets.length > 0) {
            const contentTop = HEADER_HEIGHT + RULER_HEIGHT
            const contentHeight = lanes.length * LANE_HEIGHT

            detectedOnsets.forEach((onset) => {
                // onset.time is in seconds, convert to milliseconds for timeToX
                const timeMs = onset.time * 1000
                const x = SIDEBAR_WIDTH + timeToX(timeMs)

                // Skip if outside visible area
                if (x < SIDEBAR_WIDTH || x > width) return

                // Confidence determines opacity and height
                const alpha = Math.max(0.3, Math.min(0.9, onset.confidence))
                const lineHeight = contentHeight * Math.max(0.3, onset.confidence)

                // Draw vertical line from top of content area
                ctx.beginPath()
                ctx.strokeStyle = `rgba(251, 191, 36, ${alpha})` // amber-400 with alpha
                ctx.lineWidth = 2
                ctx.moveTo(x, contentTop)
                ctx.lineTo(x, contentTop + lineHeight)
                ctx.stroke()

                // Draw small triangle marker at top
                ctx.fillStyle = `rgba(251, 191, 36, ${alpha})`
                ctx.beginPath()
                ctx.moveTo(x, contentTop)
                ctx.lineTo(x - 4, contentTop - 6)
                ctx.lineTo(x + 4, contentTop - 6)
                ctx.closePath()
                ctx.fill()
            })
        }

        // Draw removed notes (diff mode)
        if (showDiff) {
            noteDiffs.forEach((diff) => {
                if (diff.type === 'removed' && diff.originalNote) {
                    const note = diff.originalNote
                    const laneIndex = lanes.indexOf(note.component)
                    if (laneIndex === -1) return

                    const x = SIDEBAR_WIDTH + timeToX(note.time)
                    const y = laneToY(laneIndex)

                    if (x < SIDEBAR_WIDTH || x > width) return

                    ctx.strokeStyle = '#ef4444' // red-500
                    ctx.lineWidth = 2
                    ctx.setLineDash([4, 4])
                    ctx.beginPath()
                    ctx.arc(x, y, NOTE_RADIUS, 0, Math.PI * 2)
                    ctx.stroke()
                    ctx.setLineDash([])

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

            const x = SIDEBAR_WIDTH + timeToX(note.time)
            const y = laneToY(laneIndex)

            if (x < SIDEBAR_WIDTH || x > width) return

            const isSelected = selection.noteIds.has(note.id)
            const diff = noteDiffs.get(note.id)

            ctx.beginPath()
            ctx.arc(x, y, NOTE_RADIUS, 0, Math.PI * 2)

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

            ctx.globalAlpha = 0.4 + note.velocity * 0.6
            ctx.fill()
            ctx.globalAlpha = 1

            if (isSelected) {
                ctx.strokeStyle = '#ffffff'
                ctx.lineWidth = 2
                ctx.stroke()
            }

            if (showDiff && diff?.type === 'modified' && diff.originalNote) {
                const origX = SIDEBAR_WIDTH + timeToX(diff.originalNote.time)
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
        const playheadX = SIDEBAR_WIDTH + timeToX(currentTime)
        if (playheadX >= SIDEBAR_WIDTH && playheadX <= width) {
            ctx.strokeStyle = PLAYHEAD_COLOR
            ctx.lineWidth = 2
            ctx.beginPath()
            ctx.moveTo(playheadX, HEADER_HEIGHT)
            ctx.lineTo(playheadX, canvas.height)
            ctx.stroke()

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
            // Reserved for rectangle selection visualization
        }
    }, [
        hitObjects,
        lanes,
        currentTime,
        viewport,
        selection,
        showDiff,
        waveformScale,
        waveformData,
        onsetLayerVisible,
        detectedOnsets,
        noteDiffs,
        timeToX,
        laneToY,
        isSelecting,
        selectStart,
    ])

    // Check if static layer needs redraw
    const checkStaticDirty = useCallback(() => {
        const last = lastViewportRef.current
        if (!last) return true

        // Static layer is dirty if zoom or start position changed significantly
        if (Math.abs(last.zoom - viewport.zoom) > 0.0001) return true
        if (Math.abs(last.startTime - viewport.startTime) > 1) return true

        return staticDirtyRef.current
    }, [viewport.zoom, viewport.startTime])

    // Handle canvas resize
    useEffect(() => {
        const staticCanvas = staticCanvasRef.current
        const dynamicCanvas = dynamicCanvasRef.current
        const container = containerRef.current
        if (!staticCanvas || !dynamicCanvas || !container) return

        const resizeObserver = new ResizeObserver((entries) => {
            for (const entry of entries) {
                const { width } = entry.contentRect
                const dpr = window.devicePixelRatio || 1

                // Resize both canvases
                staticCanvas.width = width * dpr
                staticCanvas.height = totalHeight * dpr
                staticCanvas.style.width = `${width}px`
                staticCanvas.style.height = `${totalHeight}px`

                dynamicCanvas.width = width * dpr
                dynamicCanvas.height = totalHeight * dpr
                dynamicCanvas.style.width = `${width}px`
                dynamicCanvas.style.height = `${totalHeight}px`

                const staticCtx = staticCanvas.getContext('2d')
                const dynamicCtx = dynamicCanvas.getContext('2d')
                if (staticCtx) staticCtx.scale(dpr, dpr)
                if (dynamicCtx) dynamicCtx.scale(dpr, dpr)

                // Update viewport to match canvas width
                const viewDuration = (width - SIDEBAR_WIDTH) / viewport.zoom
                onViewportChange({
                    ...viewport,
                    endTime: viewport.startTime + viewDuration,
                })

                // Mark static layer dirty on resize
                staticDirtyRef.current = true
                drawStaticLayer()
                drawDynamicLayer()
            }
        })

        resizeObserver.observe(container)
        return () => resizeObserver.disconnect()
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [totalHeight, viewport.zoom, onViewportChange])

    // Redraw static layer only when necessary
    useEffect(() => {
        if (checkStaticDirty()) {
            drawStaticLayer()
        }
    }, [checkStaticDirty, drawStaticLayer])

    // Redraw dynamic layer when dependencies change
    useEffect(() => {
        drawDynamicLayer()
    }, [drawDynamicLayer])

    // Find note at position
    const findNoteAtPosition = useCallback(
        (x: number, y: number): HitObject | null => {
            const laneIndex = yToLane(y)

            if (laneIndex < 0 || laneIndex >= lanes.length) return null

            const lane = lanes[laneIndex]
            const hitRadius = NOTE_RADIUS + 4 // Slightly larger hit area

            for (const note of hitObjects) {
                if (note.component !== lane) continue

                const noteX = timeToX(note.time) + SIDEBAR_WIDTH
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
            const canvas = dynamicCanvasRef.current
            if (!canvas) return

            const rect = canvas.getBoundingClientRect()
            const x = e.clientX - rect.left
            const y = e.clientY - rect.top

            // Check if clicking on ruler for seeking
            if (y < HEADER_HEIGHT + RULER_HEIGHT && y >= HEADER_HEIGHT && x > SIDEBAR_WIDTH) {
                const time = xToTime(x - SIDEBAR_WIDTH)
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

            const canvas = dynamicCanvasRef.current
            if (!canvas) return

            const rect = canvas.getBoundingClientRect()
            const x = e.clientX - rect.left
            const y = e.clientY - rect.top

            // Calculate new time and lane
            let newTime = xToTime(x - SIDEBAR_WIDTH)
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

    // Touch event handlers for mobile support
    const handleTouchStart = useCallback(
        (e: React.TouchEvent) => {
            if (e.touches.length !== 1) return // Only handle single touch

            const touch = e.touches[0]
            const canvas = dynamicCanvasRef.current
            if (!canvas) return

            const rect = canvas.getBoundingClientRect()
            const x = touch.clientX - rect.left
            const y = touch.clientY - rect.top

            // Check if touching ruler for seeking
            if (y < HEADER_HEIGHT + RULER_HEIGHT && y >= HEADER_HEIGHT && x > SIDEBAR_WIDTH) {
                const time = xToTime(x - SIDEBAR_WIDTH)
                onSeek?.(Math.max(0, Math.min(time, duration)))
                return
            }

            // Check if touching a note
            const note = findNoteAtPosition(x, y)
            if (note) {
                // Select the touched note
                onSelectionChange({ noteIds: new Set([note.id]) })
                // Start dragging
                setIsDragging(true)
                setDragNote({ note, startX: x, startY: y })
            } else {
                // Clear selection
                onSelectionChange({ noteIds: new Set() })
            }
        },
        [xToTime, duration, onSeek, findNoteAtPosition, onSelectionChange]
    )

    const handleTouchMove = useCallback(
        (e: React.TouchEvent) => {
            if (!isDragging || !dragNote || e.touches.length !== 1) return

            const touch = e.touches[0]
            const canvas = dynamicCanvasRef.current
            if (!canvas) return

            const rect = canvas.getBoundingClientRect()
            const x = touch.clientX - rect.left
            const y = touch.clientY - rect.top

            // Calculate new time and lane
            let newTime = xToTime(x - SIDEBAR_WIDTH)
            newTime = snapTime(newTime)
            newTime = Math.max(0, Math.min(newTime, duration))

            const newLaneIndex = yToLane(y)
            const clampedLaneIndex = Math.max(0, Math.min(newLaneIndex, lanes.length - 1))

            onNoteDrag?.(dragNote.note.id, newTime, clampedLaneIndex)
        },
        [isDragging, dragNote, xToTime, snapTime, duration, yToLane, lanes.length, onNoteDrag]
    )

    const handleTouchEnd = useCallback(() => {
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
                const canvas = dynamicCanvasRef.current
                if (!canvas) return

                const rect = canvas.getBoundingClientRect()
                const mouseX = e.clientX - rect.left - SIDEBAR_WIDTH
                const mouseTime = xToTime(mouseX)

                const newStartTime = mouseTime - mouseX / newZoom
                const viewDuration = (rect.width - SIDEBAR_WIDTH) / newZoom

                // Mark static layer dirty since zoom changed
                staticDirtyRef.current = true

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

                // Mark static layer dirty since scroll position changed
                staticDirtyRef.current = true

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
            className="relative w-full overflow-hidden rounded-lg border border-white/10 bg-dark-400"
            style={{ height: totalHeight }}
        >
            {/* Static layer - background grid, lanes, ruler */}
            <canvas
                ref={staticCanvasRef}
                className="absolute inset-0 block"
                style={{ zIndex: 0 }}
            />
            {/* Dynamic layer - notes, playhead, waveform (handles all interactions) */}
            <canvas
                ref={dynamicCanvasRef}
                className="absolute inset-0 block touch-none"
                style={{ zIndex: 1 }}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
                onWheel={handleWheel}
                onTouchStart={handleTouchStart}
                onTouchMove={handleTouchMove}
                onTouchEnd={handleTouchEnd}
            />
        </div>
    )
}
