import { useCallback, useState, useEffect, useRef, useMemo } from 'react'
import { TimelineCanvas } from './TimelineCanvas'
import { TimelineAudioPlayer } from './AudioPlayer'
import type {
    HitObject,
    DrumComponent,
    TimelineViewport,
    TimelineSelection,
    SnapSettings,
    NoteEdit,
    Beatmap,
} from '../../types/beatmap'

interface TimelineEditorProps {
    /** The beatmap being edited */
    beatmap: Beatmap
    /** Comparison beatmap for diff view (optional - canonical version) */
    comparisonBeatmap?: Beatmap
    /** URL to the audio file */
    audioUrl: string
    /** Callback when beatmap is modified */
    onBeatmapChange?: (beatmap: Beatmap) => void
    /** Callback when user wants to submit edits */
    onSubmit?: (edits: NoteEdit[]) => void
    /** Read-only mode */
    readOnly?: boolean
    /** Initial diff view state */
    showDiff?: boolean
}

/**
 * Lane sort priority matching desktop DynamicLaneLayoutBuilder.computeSortKey()
 * Lower values appear higher in the timeline (hi-hats at top, kicks in middle, crashes at bottom)
 */
const LANE_SORT_PRIORITY: Record<DrumComponent, number> = {
    // Hi-hats (top of timeline, left side of kit)
    hihat_closed: -40,
    hihat_open: -39,
    hihat_pedal: -38,
    hihat_foot_splash: -37,
    hihat_splash: -36,
    // Snare variations (center-ish)
    snare: -5,
    snare_center: -5,
    snare_rimshot: -4,
    snare_cross_stick: -3,
    rimshot: -4,
    cross_stick: -3,
    // Kick (center)
    kick: 0,
    // Toms (descending pitch order)
    tom_high: 10,
    tom_mid: 12,
    tom_low: 15,
    // Ride (right side)
    ride: 25,
    ride_bow: 25,
    ride_bell: 26,
    // Crashes/effects (bottom, around kit)
    crash: 30,
    crash2: 31,
    splash: 32,
    china: 33,
    cymbal_choke: 34,
    // Auxiliary percussion (very bottom)
    cowbell: 40,
    aux_percussion: 41,
    unknown: 50,
}

/**
 * Snap divisor options - matches desktop EditorTimeline.SupportedSnapDivisors
 * [1, 2, 3, 4, 6, 8, 12, 16, 24, 32]
 */
const SNAP_OPTIONS: { value: SnapSettings['divisor']; label: string }[] = [
    { value: 1, label: '1/1' },
    { value: 2, label: '1/2' },
    { value: 3, label: '1/3' },
    { value: 4, label: '1/4' },
    { value: 6, label: '1/6' },
    { value: 8, label: '1/8' },
    { value: 12, label: '1/12' },
    { value: 16, label: '1/16' },
    { value: 24, label: '1/24' },
    { value: 32, label: '1/32' },
]

/**
 * Waveform scale constants matching desktop EditorTimeline.cs
 */
const DEFAULT_WAVEFORM_SCALE = 1.0
const MIN_WAVEFORM_SCALE = 0.5
const MAX_WAVEFORM_SCALE = 2.5

const PLAYBACK_RATES = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0]

export function TimelineEditor({
    beatmap,
    comparisonBeatmap,
    audioUrl,
    onBeatmapChange,
    onSubmit,
    readOnly = false,
    showDiff: initialShowDiff = false,
}: TimelineEditorProps) {
    // Audio player state
    const audioPlayerRef = useRef<TimelineAudioPlayer | null>(null)
    const [isPlaying, setIsPlaying] = useState(false)
    const [currentTime, setCurrentTime] = useState(0)
    const [duration, setDuration] = useState(beatmap.audio.duration)
    const [isLoading, setIsLoading] = useState(true)
    const [playbackRate, setPlaybackRate] = useState(1.0)
    const [volume, setVolume] = useState(0.8)

    // Timeline state
    const [viewport, setViewport] = useState<TimelineViewport>({
        startTime: 0,
        endTime: 10000, // 10 seconds initial view
        zoom: 0.1, // 0.1 pixels per ms = 100px per second
    })
    const [selection, setSelection] = useState<TimelineSelection>({ noteIds: new Set() })
    const [snap, setSnap] = useState<SnapSettings>({ enabled: true, divisor: 4 })
    const [showDiff, setShowDiff] = useState(initialShowDiff)

    // Display settings matching desktop EditorTimeline
    const [waveformScale, setWaveformScale] = useState(DEFAULT_WAVEFORM_SCALE)
    const [beatGridVisible, setBeatGridVisible] = useState(true)
    const [onsetLayerVisible, setOnsetLayerVisible] = useState(false)

    // Edit history for undo/redo
    const [undoStack, setUndoStack] = useState<NoteEdit[][]>([])
    const [redoStack, setRedoStack] = useState<NoteEdit[][]>([])

    // Local editable copy of hit objects
    const [hitObjects, setHitObjects] = useState<HitObject[]>(beatmap.hitObjects)

    /**
     * Dynamically build lanes from the beatmap content.
     * Matches desktop DynamicLaneLayoutBuilder.CreateForBeatmap():
     * 1. Collect all unique components from drumKit.components or hitObjects
     * 2. Sort by priority (hi-hats at top, kicks in middle, crashes at bottom)
     */
    const lanes = useMemo(() => {
        const components = new Set<DrumComponent>()

        // First: use drumKit.components if available (preferred source)
        if (beatmap.drumKit?.components) {
            beatmap.drumKit.components.forEach((c) => components.add(c))
        }

        // Second: collect from hitObjects if drumKit is empty
        if (components.size === 0) {
            hitObjects.forEach((n) => components.add(n.component))
        }

        // Also include comparison beatmap components for diff view
        if (comparisonBeatmap) {
            if (comparisonBeatmap.drumKit?.components) {
                comparisonBeatmap.drumKit.components.forEach((c) => components.add(c))
            }
            comparisonBeatmap.hitObjects.forEach((n) => components.add(n.component))
        }

        // Fallback: at minimum show kick if nothing detected
        if (components.size === 0) {
            components.add('kick')
        }

        // Sort by priority (matching desktop DynamicLaneLayoutBuilder.computeSortKey)
        return Array.from(components).sort((a, b) => {
            const priorityA = LANE_SORT_PRIORITY[a] ?? 50
            const priorityB = LANE_SORT_PRIORITY[b] ?? 50
            return priorityA - priorityB
        })
    }, [beatmap.drumKit?.components, hitObjects, comparisonBeatmap])

    // Initialize audio player
    useEffect(() => {
        const player = new TimelineAudioPlayer({
            onTimeUpdate: setCurrentTime,
            onPlayStateChange: setIsPlaying,
            onLoad: (dur) => {
                setDuration(dur)
                setIsLoading(false)
            },
            onError: (error) => {
                console.error('Audio error:', error)
                setIsLoading(false)
            },
        })

        audioPlayerRef.current = player
        player.loadAudio(audioUrl).catch(console.error)

        return () => {
            player.dispose()
        }
    }, [audioUrl])

    // Sync volume and playback rate changes
    useEffect(() => {
        audioPlayerRef.current?.setVolume(volume)
    }, [volume])

    useEffect(() => {
        audioPlayerRef.current?.setPlaybackRate(playbackRate)
    }, [playbackRate])

    // Playback controls
    const togglePlayback = useCallback(() => {
        if (isPlaying) {
            audioPlayerRef.current?.pause()
        } else {
            audioPlayerRef.current?.play()
        }
    }, [isPlaying])

    const handleSeek = useCallback((time: number) => {
        audioPlayerRef.current?.seek(time)
        setCurrentTime(time)
    }, [])

    const stopPlayback = useCallback(() => {
        audioPlayerRef.current?.stop()
        setCurrentTime(0)
    }, [])

    // Note editing
    const applyEdit = useCallback(
        (edits: NoteEdit[]) => {
            if (readOnly) return

            setHitObjects((prev) => {
                let updated = [...prev]

                for (const editItem of edits) {
                    switch (editItem.type) {
                        case 'add':
                            if (editItem.newState) {
                                updated.push(editItem.newState as HitObject)
                            }
                            break
                        case 'delete':
                            updated = updated.filter((n) => n.id !== editItem.noteId)
                            break
                        case 'move':
                        case 'change_lane':
                        case 'change_velocity':
                            updated = updated.map((n) =>
                                n.id === editItem.noteId ? { ...n, ...editItem.newState } : n
                            )
                            break
                    }
                }

                return updated
            })

            // Push to undo stack
            setUndoStack((prev) => [...prev, edits])
            setRedoStack([]) // Clear redo stack on new edit
        },
        [readOnly]
    )

    const undo = useCallback(() => {
        if (undoStack.length === 0) return

        const lastEdits = undoStack[undoStack.length - 1]
        setUndoStack((prev) => prev.slice(0, -1))

        // Reverse the edits
        setHitObjects((prev) => {
            let updated = [...prev]

            for (const editItem of [...lastEdits].reverse()) {
                switch (editItem.type) {
                    case 'add':
                        updated = updated.filter((n) => n.id !== editItem.noteId)
                        break
                    case 'delete':
                        if (editItem.previousState) {
                            updated.push(editItem.previousState as HitObject)
                        }
                        break
                    case 'move':
                    case 'change_lane':
                    case 'change_velocity':
                        updated = updated.map((n) =>
                            n.id === editItem.noteId ? { ...n, ...editItem.previousState } : n
                        )
                        break
                }
            }

            return updated
        })

        setRedoStack((prev) => [...prev, lastEdits])
    }, [undoStack])

    const redo = useCallback(() => {
        if (redoStack.length === 0) return

        const lastEdits = redoStack[redoStack.length - 1]
        setRedoStack((prev) => prev.slice(0, -1))

        applyEdit(lastEdits)
        // Remove from undo stack since applyEdit adds it again
        setUndoStack((prev) => prev.slice(0, -1))
    }, [redoStack, applyEdit])

    // Handle note drag
    const handleNoteDrag = useCallback(
        (noteId: string, newTime: number, newLaneIndex: number) => {
            if (readOnly) return

            const note = hitObjects.find((n) => n.id === noteId)
            if (!note) return

            const newComponent = lanes[newLaneIndex]
            if (!newComponent) return

            // Apply immediately (without pushing to undo yet - that happens on mouseup)
            setHitObjects((prev) =>
                prev.map((n) =>
                    n.id === noteId ? { ...n, time: newTime, component: newComponent, lane: newLaneIndex } : n
                )
            )
        },
        [readOnly, hitObjects, lanes]
    )

    // Delete selected notes
    const deleteSelected = useCallback(() => {
        if (readOnly || selection.noteIds.size === 0) return

        const edits: NoteEdit[] = []
        for (const noteId of selection.noteIds) {
            const note = hitObjects.find((n) => n.id === noteId)
            if (note) {
                edits.push({
                    type: 'delete',
                    noteId,
                    previousState: note,
                })
            }
        }

        applyEdit(edits)
        setSelection({ noteIds: new Set() })
    }, [readOnly, selection, hitObjects, applyEdit])

    // Keyboard shortcuts
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            // Ignore if typing in an input
            if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return

            switch (e.key) {
                case ' ':
                    e.preventDefault()
                    togglePlayback()
                    break
                case 'Delete':
                case 'Backspace':
                    if (!readOnly) {
                        e.preventDefault()
                        deleteSelected()
                    }
                    break
                case 'z':
                    if ((e.ctrlKey || e.metaKey) && !e.shiftKey) {
                        e.preventDefault()
                        undo()
                    } else if ((e.ctrlKey || e.metaKey) && e.shiftKey) {
                        e.preventDefault()
                        redo()
                    }
                    break
                case 'y':
                    if (e.ctrlKey || e.metaKey) {
                        e.preventDefault()
                        redo()
                    }
                    break
                case 'a':
                    if (e.ctrlKey || e.metaKey) {
                        e.preventDefault()
                        setSelection({ noteIds: new Set(hitObjects.map((n) => n.id)) })
                    }
                    break
                case 'Escape':
                    setSelection({ noteIds: new Set() })
                    break
            }
        }

        window.addEventListener('keydown', handleKeyDown)
        return () => window.removeEventListener('keydown', handleKeyDown)
    }, [togglePlayback, deleteSelected, undo, redo, hitObjects, readOnly])

    // Notify parent of changes
    useEffect(() => {
        if (onBeatmapChange) {
            onBeatmapChange({ ...beatmap, hitObjects })
        }
    }, [hitObjects, beatmap, onBeatmapChange])

    // Calculate edit stats
    const editStats = useMemo(() => {
        if (!comparisonBeatmap) return null

        const originalIds = new Set(comparisonBeatmap.hitObjects.map((n) => n.id))
        const currentIds = new Set(hitObjects.map((n) => n.id))

        let added = 0
        let removed = 0
        let modified = 0

        for (const note of hitObjects) {
            if (!originalIds.has(note.id)) {
                added++
            } else {
                const orig = comparisonBeatmap.hitObjects.find((n) => n.id === note.id)
                if (orig && (orig.time !== note.time || orig.component !== note.component || orig.velocity !== note.velocity)) {
                    modified++
                }
            }
        }

        for (const id of originalIds) {
            if (!currentIds.has(id)) {
                removed++
            }
        }

        return { added, removed, modified }
    }, [hitObjects, comparisonBeatmap])

    // Format time display
    const formatTime = (ms: number) => {
        const seconds = Math.floor(ms / 1000)
        const minutes = Math.floor(seconds / 60)
        const remainingSeconds = seconds % 60
        const milliseconds = Math.floor((ms % 1000) / 10)
        return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}.${milliseconds.toString().padStart(2, '0')}`
    }

    // Handle submit
    const handleSubmit = useCallback(() => {
        if (!onSubmit) return

        // Collect all edits from undo stack
        const allEdits = undoStack.flat()
        onSubmit(allEdits)
    }, [onSubmit, undoStack])

    return (
        <div className="flex flex-col gap-4 rounded-lg bg-gray-900 p-4">
            {/* Toolbar */}
            <div className="flex flex-wrap items-center gap-4">
                {/* Playback controls */}
                <div className="flex items-center gap-2">
                    <button
                        onClick={stopPlayback}
                        className="rounded bg-gray-700 px-3 py-1.5 text-sm hover:bg-gray-600"
                        title="Stop"
                    >
                        ⏹
                    </button>
                    <button
                        onClick={togglePlayback}
                        disabled={isLoading}
                        className="rounded bg-orange-600 px-4 py-1.5 text-sm font-medium hover:bg-orange-500 disabled:opacity-50"
                    >
                        {isLoading ? '...' : isPlaying ? '⏸ Pause' : '▶ Play'}
                    </button>
                </div>

                {/* Time display */}
                <div className="font-mono text-sm text-gray-300">
                    {formatTime(currentTime)} / {formatTime(duration)}
                </div>

                {/* Playback rate */}
                <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-400">Speed:</span>
                    <select
                        value={playbackRate}
                        onChange={(e) => setPlaybackRate(parseFloat(e.target.value))}
                        className="rounded bg-gray-700 px-2 py-1 text-sm"
                    >
                        {PLAYBACK_RATES.map((rate) => (
                            <option key={rate} value={rate}>
                                {rate}x
                            </option>
                        ))}
                    </select>
                </div>

                {/* Volume */}
                <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-400">Vol:</span>
                    <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.1"
                        value={volume}
                        onChange={(e) => setVolume(parseFloat(e.target.value))}
                        className="h-1 w-20 cursor-pointer"
                    />
                </div>

                <div className="h-6 w-px bg-gray-700" />

                {/* Snap controls */}
                <div className="flex items-center gap-2">
                    <label className="flex items-center gap-1.5 text-sm">
                        <input
                            type="checkbox"
                            checked={snap.enabled}
                            onChange={(e) => setSnap((s) => ({ ...s, enabled: e.target.checked }))}
                            className="rounded"
                        />
                        <span className="text-gray-400">Snap</span>
                    </label>
                    <select
                        value={snap.divisor}
                        onChange={(e) =>
                            setSnap((s) => ({ ...s, divisor: parseInt(e.target.value) as SnapSettings['divisor'] }))
                        }
                        disabled={!snap.enabled}
                        className="rounded bg-gray-700 px-2 py-1 text-sm disabled:opacity-50"
                    >
                        {SNAP_OPTIONS.map((opt) => (
                            <option key={opt.value} value={opt.value}>
                                {opt.label}
                            </option>
                        ))}
                    </select>
                </div>

                <div className="h-6 w-px bg-gray-700" />

                {/* Diff toggle */}
                {comparisonBeatmap && (
                    <label className="flex items-center gap-1.5 text-sm">
                        <input
                            type="checkbox"
                            checked={showDiff}
                            onChange={(e) => setShowDiff(e.target.checked)}
                            className="rounded"
                        />
                        <span className="text-gray-400">Show Diff</span>
                    </label>
                )}

                <div className="h-6 w-px bg-gray-700" />

                {/* Display controls - matches desktop EditorTimeline */}
                <label className="flex items-center gap-1.5 text-sm">
                    <input
                        type="checkbox"
                        checked={beatGridVisible}
                        onChange={(e) => setBeatGridVisible(e.target.checked)}
                        className="rounded"
                    />
                    <span className="text-gray-400">Grid</span>
                </label>

                <label className="flex items-center gap-1.5 text-sm">
                    <input
                        type="checkbox"
                        checked={onsetLayerVisible}
                        onChange={(e) => setOnsetLayerVisible(e.target.checked)}
                        className="rounded"
                    />
                    <span className="text-gray-400">Onsets</span>
                </label>

                <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-400">Wave:</span>
                    <input
                        type="range"
                        min={MIN_WAVEFORM_SCALE}
                        max={MAX_WAVEFORM_SCALE}
                        step="0.1"
                        value={waveformScale}
                        onChange={(e) => setWaveformScale(parseFloat(e.target.value))}
                        className="h-1 w-16 cursor-pointer"
                        title={`Waveform scale: ${waveformScale.toFixed(1)}`}
                    />
                </div>

                {/* Edit stats */}
                {showDiff && editStats && (
                    <div className="flex items-center gap-3 text-xs">
                        <span className="text-green-400">+{editStats.added}</span>
                        <span className="text-red-400">-{editStats.removed}</span>
                        <span className="text-amber-400">~{editStats.modified}</span>
                    </div>
                )}

                <div className="flex-1" />

                {/* Undo/Redo */}
                {!readOnly && (
                    <div className="flex items-center gap-1">
                        <button
                            onClick={undo}
                            disabled={undoStack.length === 0}
                            className="rounded bg-gray-700 px-3 py-1.5 text-sm hover:bg-gray-600 disabled:opacity-50"
                            title="Undo (Ctrl+Z)"
                        >
                            ↩
                        </button>
                        <button
                            onClick={redo}
                            disabled={redoStack.length === 0}
                            className="rounded bg-gray-700 px-3 py-1.5 text-sm hover:bg-gray-600 disabled:opacity-50"
                            title="Redo (Ctrl+Y)"
                        >
                            ↪
                        </button>
                    </div>
                )}

                {/* Submit button */}
                {onSubmit && !readOnly && undoStack.length > 0 && (
                    <button
                        onClick={handleSubmit}
                        className="rounded bg-green-600 px-4 py-1.5 text-sm font-medium hover:bg-green-500"
                    >
                        Submit Edits ({undoStack.flat().length})
                    </button>
                )}
            </div>

            {/* Selection info */}
            {selection.noteIds.size > 0 && (
                <div className="flex items-center gap-4 rounded bg-gray-800 px-3 py-2 text-sm">
                    <span className="text-gray-400">Selected: {selection.noteIds.size} notes</span>
                    {!readOnly && (
                        <>
                            <button
                                onClick={deleteSelected}
                                className="text-red-400 hover:text-red-300"
                            >
                                Delete
                            </button>
                            <button
                                onClick={() => setSelection({ noteIds: new Set() })}
                                className="text-gray-400 hover:text-gray-300"
                            >
                                Clear Selection
                            </button>
                        </>
                    )}
                </div>
            )}

            {/* Timeline canvas */}
            <TimelineCanvas
                hitObjects={hitObjects}
                comparisonObjects={showDiff ? comparisonBeatmap?.hitObjects : undefined}
                lanes={lanes}
                bpm={beatmap.timing.bpm}
                duration={duration}
                currentTime={currentTime}
                viewport={viewport}
                selection={selection}
                snap={snap}
                showDiff={showDiff}
                beatGridVisible={beatGridVisible}
                onsetLayerVisible={onsetLayerVisible}
                waveformScale={waveformScale}
                onViewportChange={setViewport}
                onSelectionChange={setSelection}
                onNoteDrag={handleNoteDrag}
                onSeek={handleSeek}
                height={lanes.length * 32 + 60}
            />

            {/* Legend */}
            <div className="flex flex-wrap gap-4 text-xs text-gray-500">
                <span>Scroll: Pan timeline</span>
                <span>Ctrl+Scroll: Zoom</span>
                <span>Click ruler: Seek</span>
                <span>Shift+Click: Multi-select</span>
                <span>Del: Delete selected</span>
                <span>Space: Play/Pause</span>
            </div>
        </div>
    )
}
