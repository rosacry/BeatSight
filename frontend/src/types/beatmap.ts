/**
 * BeatSight Beatmap Types
 * Matches the .bsm file format
 */

export interface BeatmapMetadata {
    title: string
    artist: string
    creator: string
    tags: string[]
    difficulty: number
    previewTime: number
    beatmapId: string
    createdAt: string
    modifiedAt: string
    description?: string
}

export interface BeatmapAudio {
    filename: string
    hash: string
    duration: number // milliseconds
    sampleRate: number
    drumStem?: string
    drumStemHash?: string
}

export interface TimingPoint {
    time: number // milliseconds
    bpm: number
    timeSignature: string // e.g., "4/4"
}

export interface BeatmapTiming {
    bpm: number
    offset: number
    timeSignature: string
    timingPoints: TimingPoint[]
}

export interface DrumKit {
    components: DrumComponent[]
    layout: string
    customSamples?: Record<string, string> | null
}

/**
 * Drum component types.
 * 
 * Must match:
 * - Desktop: BeatSight.Game.Mapping.DrumComponentCategory enum
 * - AI Pipeline: training/configs/health_required_labels_prod.txt
 */
export type DrumComponent =
    // Kick/Bass
    | 'kick'
    // Snare variations
    | 'snare'
    | 'rimshot'
    | 'cross_stick'
    // Hi-hat variations
    | 'hihat_closed'
    | 'hihat_open'
    | 'hihat_pedal'
    | 'hihat_foot_splash'
    // Toms
    | 'tom_high'
    | 'tom_mid'
    | 'tom_low'
    // Ride variations
    | 'ride'        // Generic (legacy)
    | 'ride_bow'
    | 'ride_bell'
    // Crashes and cymbals
    | 'crash'
    | 'crash2'
    | 'splash'
    | 'china'
    // Other
    | 'cowbell'
    | 'aux_percussion'
    | 'unknown'

export interface HitObject {
    id: string // For React keys and editing
    time: number // milliseconds
    component: DrumComponent
    velocity: number // 0.0 - 1.0
    lane: number
    duration?: number | null
}

export interface EditorMetadata {
    snapDivisor: number
    visualLanes: number
    timelineZoom: number
    bookmarks: number[]
    aiGenerationMetadata?: {
        modelVersion: string
        confidence: number
        processedAt: string
        manualEdits: boolean
    }
}

export interface Beatmap {
    version: string
    metadata: BeatmapMetadata
    audio: BeatmapAudio
    timing: BeatmapTiming
    drumKit: DrumKit
    hitObjects: HitObject[]
    editor?: EditorMetadata
}

// Timeline Editor specific types
export interface TimelineSelection {
    noteIds: Set<string>
    startTime?: number
    endTime?: number
}

export interface TimelineViewport {
    startTime: number
    endTime: number
    zoom: number // pixels per millisecond
}

export interface SnapSettings {
    enabled: boolean
    divisor: 1 | 2 | 3 | 4 | 6 | 8 | 12 | 16 | 24 | 32
}

/**
 * Timeline display settings - matches desktop EditorInfo
 */
export interface TimelineDisplaySettings {
    waveformScale: number  // 0.5 to 2.5, default 1.0
    beatGridVisible: boolean
    onsetLayerVisible: boolean
}

export interface NoteEdit {
    type: 'add' | 'delete' | 'move' | 'change_lane' | 'change_velocity'
    noteId: string
    previousState?: Partial<HitObject>
    newState?: Partial<HitObject>
}

export interface EditHistory {
    undoStack: NoteEdit[][]
    redoStack: NoteEdit[][]
}

// Diff visualization types
export interface NoteDiff {
    type: 'added' | 'removed' | 'modified' | 'unchanged'
    originalNote?: HitObject
    editedNote?: HitObject
    timeDelta?: number
    laneDelta?: number
    velocityDelta?: number
}

// Lane color mapping - matches desktop DrumComponentCategory
export const LANE_COLORS: Record<DrumComponent, string> = {
    // Kick
    kick: '#ef4444', // red-500
    // Snare variations
    snare: '#f59e0b', // amber-500
    rimshot: '#fbbf24', // amber-400
    cross_stick: '#d97706', // amber-600
    // Hi-hat variations
    hihat_closed: '#10b981', // emerald-500
    hihat_open: '#14b8a6', // teal-500
    hihat_pedal: '#059669', // emerald-600
    hihat_foot_splash: '#0d9488', // teal-600
    // Toms
    tom_high: '#3b82f6', // blue-500
    tom_mid: '#6366f1', // indigo-500
    tom_low: '#8b5cf6', // violet-500
    // Ride variations
    ride: '#a855f7', // purple-500
    ride_bow: '#a855f7', // purple-500
    ride_bell: '#c084fc', // purple-400
    // Crashes and cymbals
    crash: '#ec4899', // pink-500
    crash2: '#db2777', // pink-600
    splash: '#06b6d4', // cyan-500
    china: '#f43f5e', // rose-500
    // Other
    cowbell: '#f97316', // orange-500
    aux_percussion: '#84cc16', // lime-500
    unknown: '#6b7280', // gray-500
}

export const LANE_LABELS: Record<DrumComponent, string> = {
    kick: 'Kick',
    snare: 'Snare',
    rimshot: 'Rimshot',
    cross_stick: 'X-Stick',
    hihat_closed: 'HH (C)',
    hihat_open: 'HH (O)',
    hihat_pedal: 'HH Pedal',
    hihat_foot_splash: 'HH Splash',
    tom_high: 'Tom H',
    tom_mid: 'Tom M',
    tom_low: 'Tom L',
    ride: 'Ride',
    ride_bow: 'Ride Bow',
    ride_bell: 'Ride Bell',
    crash: 'Crash',
    crash2: 'Crash 2',
    splash: 'Splash',
    china: 'China',
    cowbell: 'Cowbell',
    aux_percussion: 'Aux Perc',
    unknown: 'Unknown',
}
