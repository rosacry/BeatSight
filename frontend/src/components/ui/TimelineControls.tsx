/**
 * Enhanced Timeline UI Components
 * Polished controls and visualizations for the beatmap editor.
 */

import { forwardRef, type HTMLAttributes, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode } from 'react'
import { cn } from '../../lib/utils'

// ============================================================================
// TIMELINE TOOLBAR
// ============================================================================

export interface TimelineToolbarProps extends HTMLAttributes<HTMLDivElement> {
    variant?: 'default' | 'compact' | 'floating'
}

export const TimelineToolbar = forwardRef<HTMLDivElement, TimelineToolbarProps>(
    ({ variant = 'default', className, children, ...props }, ref) => {
        const variants = {
            default: 'flex flex-wrap items-center gap-3 p-3 bg-slate-900/80 backdrop-blur-sm border-b border-slate-700/50',
            compact: 'flex items-center gap-2 p-2 bg-slate-900/90 backdrop-blur-sm',
            floating: 'flex items-center gap-3 p-3 bg-slate-800/95 backdrop-blur-md rounded-xl shadow-2xl border border-slate-700/50',
        }

        return (
            <div ref={ref} className={cn(variants[variant], className)} {...props}>
                {children}
            </div>
        )
    }
)
TimelineToolbar.displayName = 'TimelineToolbar'

export const ToolbarGroup = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
    ({ className, children, ...props }, ref) => (
        <div ref={ref} className={cn('flex items-center gap-2', className)} {...props}>
            {children}
        </div>
    )
)
ToolbarGroup.displayName = 'ToolbarGroup'

export const ToolbarDivider = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
    ({ className, ...props }, ref) => (
        <div ref={ref} className={cn('w-px h-6 bg-slate-700/50 mx-1', className)} {...props} />
    )
)
ToolbarDivider.displayName = 'ToolbarDivider'

export const ToolbarSpacer = () => <div className="flex-1" />

// ============================================================================
// CONTROL BUTTON
// ============================================================================

export interface ControlButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: 'default' | 'primary' | 'danger' | 'success' | 'ghost'
    size?: 'sm' | 'md' | 'lg'
    icon?: ReactNode
    isActive?: boolean
}

export const ControlButton = forwardRef<HTMLButtonElement, ControlButtonProps>(
    ({ variant = 'default', size = 'md', icon, isActive, className, children, disabled, ...props }, ref) => {
        const baseStyles = 'inline-flex items-center justify-center gap-1.5 font-medium rounded-lg transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-offset-slate-900'

        const variants = {
            default: 'bg-slate-700 hover:bg-slate-600 text-slate-200 focus:ring-slate-500',
            primary: 'bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-400 hover:to-amber-400 text-white shadow-lg shadow-orange-500/25 focus:ring-orange-500',
            danger: 'bg-red-500/20 hover:bg-red-500/30 text-red-400 border border-red-500/30 focus:ring-red-500',
            success: 'bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 border border-emerald-500/30 focus:ring-emerald-500',
            ghost: 'bg-transparent hover:bg-slate-700/50 text-slate-400 hover:text-slate-200 focus:ring-slate-500',
        }

        const sizes = {
            sm: 'px-2 py-1 text-xs',
            md: 'px-3 py-1.5 text-sm',
            lg: 'px-4 py-2 text-base',
        }

        return (
            <button
                ref={ref}
                disabled={disabled}
                className={cn(
                    baseStyles,
                    variants[variant],
                    sizes[size],
                    isActive && 'ring-2 ring-cyan-400 bg-cyan-500/20',
                    className
                )}
                {...props}
            >
                {icon && <span className="flex-shrink-0">{icon}</span>}
                {children}
            </button>
        )
    }
)
ControlButton.displayName = 'ControlButton'

// ============================================================================
// PLAYBACK CONTROLS
// ============================================================================

export interface PlaybackControlsProps {
    isPlaying: boolean
    isLoading?: boolean
    onPlay: () => void
    onStop: () => void
    className?: string
}

export function PlaybackControls({ isPlaying, isLoading, onPlay, onStop, className }: PlaybackControlsProps) {
    return (
        <ToolbarGroup className={className}>
            <ControlButton
                variant="ghost"
                size="md"
                onClick={onStop}
                title="Stop (Home)"
                icon={
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                        <rect x="6" y="6" width="12" height="12" rx="1" />
                    </svg>
                }
            />
            <ControlButton
                variant="primary"
                size="md"
                onClick={onPlay}
                disabled={isLoading}
                className="min-w-[90px]"
            >
                {isLoading ? (
                    <span className="flex items-center gap-2">
                        <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <circle cx="12" cy="12" r="10" strokeOpacity="0.25" />
                            <path d="M12 2a10 10 0 0 1 10 10" strokeLinecap="round" />
                        </svg>
                        Loading
                    </span>
                ) : isPlaying ? (
                    <span className="flex items-center gap-1.5">
                        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                            <rect x="6" y="5" width="4" height="14" rx="1" />
                            <rect x="14" y="5" width="4" height="14" rx="1" />
                        </svg>
                        Pause
                    </span>
                ) : (
                    <span className="flex items-center gap-1.5">
                        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M8 5.14v14.72a1 1 0 001.5.86l11-7.36a1 1 0 000-1.72l-11-7.36a1 1 0 00-1.5.86z" />
                        </svg>
                        Play
                    </span>
                )}
            </ControlButton>
        </ToolbarGroup>
    )
}

// ============================================================================
// TIME DISPLAY
// ============================================================================

export interface TimeDisplayProps {
    currentTime: number
    duration: number
    className?: string
}

export function TimeDisplay({ currentTime, duration, className }: TimeDisplayProps) {
    const formatTime = (ms: number) => {
        const totalSeconds = Math.floor(ms / 1000)
        const minutes = Math.floor(totalSeconds / 60)
        const seconds = totalSeconds % 60
        const centiseconds = Math.floor((ms % 1000) / 10)
        return `${minutes}:${seconds.toString().padStart(2, '0')}.${centiseconds.toString().padStart(2, '0')}`
    }

    const progress = duration > 0 ? (currentTime / duration) * 100 : 0

    return (
        <div className={cn('flex flex-col', className)}>
            <div className="font-mono text-lg font-medium text-slate-100 tabular-nums tracking-tight">
                {formatTime(currentTime)}
                <span className="text-slate-500 text-sm ml-1">/ {formatTime(duration)}</span>
            </div>
            <div className="h-1 w-32 bg-slate-700/50 rounded-full overflow-hidden mt-1">
                <div
                    className="h-full bg-gradient-to-r from-cyan-500 to-fuchsia-500 transition-all duration-75"
                    style={{ width: `${progress}%` }}
                />
            </div>
        </div>
    )
}

// ============================================================================
// SPEED SELECTOR
// ============================================================================

export interface SpeedSelectorProps {
    value: number
    onChange: (value: number) => void
    rates?: number[]
    className?: string
}

export function SpeedSelector({
    value,
    onChange,
    rates = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0],
    className,
}: SpeedSelectorProps) {
    return (
        <div className={cn('flex items-center gap-2', className)}>
            <span className="text-xs text-slate-500 uppercase tracking-wider">Speed</span>
            <div className="flex items-center bg-slate-800 rounded-lg p-0.5">
                {rates.map((rate) => (
                    <button
                        key={rate}
                        onClick={() => onChange(rate)}
                        className={cn(
                            'px-2 py-1 text-xs font-medium rounded-md transition-all duration-200',
                            value === rate
                                ? 'bg-slate-600 text-white shadow-sm'
                                : 'text-slate-400 hover:text-slate-200'
                        )}
                    >
                        {rate}x
                    </button>
                ))}
            </div>
        </div>
    )
}

// ============================================================================
// VOLUME SLIDER
// ============================================================================

export interface VolumeSliderProps {
    value: number
    onChange: (value: number) => void
    className?: string
}

export function VolumeSlider({ value, onChange, className }: VolumeSliderProps) {
    const isMuted = value === 0

    return (
        <div className={cn('flex items-center gap-2', className)}>
            <button
                onClick={() => onChange(isMuted ? 0.8 : 0)}
                className="text-slate-400 hover:text-slate-200 transition-colors"
                title={isMuted ? 'Unmute' : 'Mute'}
            >
                {isMuted ? (
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M11 5L6 9H2v6h4l5 4V5zM23 9l-6 6M17 9l6 6" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                ) : value < 0.5 ? (
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M11 5L6 9H2v6h4l5 4V5zM15.54 8.46a5 5 0 010 7.07" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                ) : (
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M11 5L6 9H2v6h4l5 4V5zM19.07 4.93a10 10 0 010 14.14M15.54 8.46a5 5 0 010 7.07" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                )}
            </button>
            <div className="relative w-20 h-6 flex items-center">
                <div className="absolute inset-y-0 left-0 right-0 flex items-center">
                    <div className="w-full h-1.5 bg-slate-700 rounded-full overflow-hidden">
                        <div
                            className="h-full bg-gradient-to-r from-slate-400 to-slate-300 rounded-full"
                            style={{ width: `${value * 100}%` }}
                        />
                    </div>
                </div>
                <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={value}
                    onChange={(e) => onChange(parseFloat(e.target.value))}
                    className="absolute inset-0 w-full opacity-0 cursor-pointer"
                />
            </div>
        </div>
    )
}

// ============================================================================
// SNAP SELECTOR
// ============================================================================

export interface SnapSelectorProps {
    enabled: boolean
    divisor: number
    onEnabledChange: (enabled: boolean) => void
    onDivisorChange: (divisor: number) => void
    className?: string
}

const SNAP_OPTIONS = [
    { value: 1, label: '1/1', color: 'bg-white' },
    { value: 2, label: '1/2', color: 'bg-red-400' },
    { value: 3, label: '1/3', color: 'bg-purple-400' },
    { value: 4, label: '1/4', color: 'bg-blue-400' },
    { value: 6, label: '1/6', color: 'bg-pink-400' },
    { value: 8, label: '1/8', color: 'bg-yellow-400' },
    { value: 12, label: '1/12', color: 'bg-orange-400' },
    { value: 16, label: '1/16', color: 'bg-green-400' },
]

export function SnapSelector({
    enabled,
    divisor,
    onEnabledChange,
    onDivisorChange,
    className,
}: SnapSelectorProps) {
    return (
        <div className={cn('flex items-center gap-2', className)}>
            <button
                onClick={() => onEnabledChange(!enabled)}
                className={cn(
                    'flex items-center gap-1.5 px-2 py-1 rounded-lg text-sm transition-all duration-200',
                    enabled
                        ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                        : 'bg-slate-800 text-slate-500 border border-slate-700'
                )}
            >
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 3H3v18h18V3zM3 9h18M3 15h18M9 3v18M15 3v18" strokeLinecap="round" />
                </svg>
                Snap
            </button>
            {enabled && (
                <div className="flex items-center bg-slate-800 rounded-lg overflow-hidden">
                    {SNAP_OPTIONS.map((opt) => (
                        <button
                            key={opt.value}
                            onClick={() => onDivisorChange(opt.value)}
                            className={cn(
                                'px-2 py-1 text-xs font-medium transition-all duration-200 relative',
                                divisor === opt.value
                                    ? 'bg-slate-600 text-white'
                                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700'
                            )}
                            title={opt.label}
                        >
                            <span className={cn('w-1.5 h-1.5 rounded-full inline-block mr-1', opt.color)} />
                            {opt.label}
                        </button>
                    ))}
                </div>
            )}
        </div>
    )
}

// ============================================================================
// TOGGLE SWITCH
// ============================================================================

export interface ToggleSwitchProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'onChange'> {
    label: string
    onChange: (checked: boolean) => void
}

export const ToggleSwitch = forwardRef<HTMLInputElement, ToggleSwitchProps>(
    ({ label, checked, onChange, className, ...props }, ref) => {
        return (
            <label className={cn('flex items-center gap-2 cursor-pointer select-none', className)}>
                <div className="relative">
                    <input
                        ref={ref}
                        type="checkbox"
                        checked={checked}
                        onChange={(e) => onChange(e.target.checked)}
                        className="sr-only"
                        {...props}
                    />
                    <div
                        className={cn(
                            'w-8 h-4 rounded-full transition-colors duration-200',
                            checked ? 'bg-cyan-500' : 'bg-slate-700'
                        )}
                    />
                    <div
                        className={cn(
                            'absolute top-0.5 left-0.5 w-3 h-3 bg-white rounded-full shadow-sm transition-transform duration-200',
                            checked && 'translate-x-4'
                        )}
                    />
                </div>
                <span className="text-xs text-slate-400">{label}</span>
            </label>
        )
    }
)
ToggleSwitch.displayName = 'ToggleSwitch'

// ============================================================================
// EDIT STATS BADGE
// ============================================================================

export interface EditStatsBadgeProps {
    added: number
    removed: number
    modified: number
    className?: string
}

export function EditStatsBadge({ added, removed, modified, className }: EditStatsBadgeProps) {
    const total = added + removed + modified
    if (total === 0) return null

    return (
        <div className={cn('flex items-center gap-2 px-2 py-1 bg-slate-800/50 rounded-lg text-xs', className)}>
            {added > 0 && (
                <span className="flex items-center gap-1 text-emerald-400">
                    <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M12 5v14M5 12h14" strokeLinecap="round" />
                    </svg>
                    {added}
                </span>
            )}
            {removed > 0 && (
                <span className="flex items-center gap-1 text-red-400">
                    <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M5 12h14" strokeLinecap="round" />
                    </svg>
                    {removed}
                </span>
            )}
            {modified > 0 && (
                <span className="flex items-center gap-1 text-amber-400">
                    <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M12 20v-8M12 4v4M4 12h16" strokeLinecap="round" />
                    </svg>
                    {modified}
                </span>
            )}
        </div>
    )
}

// ============================================================================
// UNDO/REDO BUTTONS
// ============================================================================

export interface UndoRedoButtonsProps {
    canUndo: boolean
    canRedo: boolean
    onUndo: () => void
    onRedo: () => void
    className?: string
}

export function UndoRedoButtons({ canUndo, canRedo, onUndo, onRedo, className }: UndoRedoButtonsProps) {
    return (
        <div className={cn('flex items-center gap-1', className)}>
            <ControlButton
                variant="ghost"
                size="sm"
                onClick={onUndo}
                disabled={!canUndo}
                title="Undo (Ctrl+Z)"
                icon={
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M3 10h10a5 5 0 015 5v2M3 10l4-4M3 10l4 4" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                }
            />
            <ControlButton
                variant="ghost"
                size="sm"
                onClick={onRedo}
                disabled={!canRedo}
                title="Redo (Ctrl+Y)"
                icon={
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M21 10H11a5 5 0 00-5 5v2M21 10l-4-4M21 10l-4 4" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                }
            />
        </div>
    )
}

// ============================================================================
// SELECTION INFO BAR
// ============================================================================

export interface SelectionInfoBarProps {
    count: number
    onDelete?: () => void
    onClear: () => void
    readOnly?: boolean
    className?: string
}

export function SelectionInfoBar({ count, onDelete, onClear, readOnly, className }: SelectionInfoBarProps) {
    if (count === 0) return null

    return (
        <div
            className={cn(
                'flex items-center gap-4 px-4 py-2 bg-cyan-500/10 border border-cyan-500/20 rounded-lg text-sm animate-in slide-in-from-top-2 duration-200',
                className
            )}
        >
            <span className="text-cyan-400 font-medium">
                {count} note{count !== 1 && 's'} selected
            </span>

            <div className="h-4 w-px bg-cyan-500/30" />

            {!readOnly && onDelete && (
                <button
                    onClick={onDelete}
                    className="flex items-center gap-1.5 text-red-400 hover:text-red-300 transition-colors"
                >
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    Delete
                </button>
            )}

            <button
                onClick={onClear}
                className="text-slate-400 hover:text-slate-200 transition-colors"
            >
                Clear selection
            </button>
        </div>
    )
}

// ============================================================================
// KEYBOARD SHORTCUTS LEGEND
// ============================================================================

export interface KeyboardShortcut {
    key: string
    description: string
}

export interface KeyboardShortcutsLegendProps {
    shortcuts?: KeyboardShortcut[]
    className?: string
}

const DEFAULT_SHORTCUTS: KeyboardShortcut[] = [
    { key: 'Space', description: 'Play/Pause' },
    { key: 'Scroll', description: 'Pan timeline' },
    { key: 'Ctrl+Scroll', description: 'Zoom' },
    { key: 'Click ruler', description: 'Seek' },
    { key: 'Shift+Click', description: 'Multi-select' },
    { key: 'Del', description: 'Delete selected' },
    { key: 'Ctrl+Z', description: 'Undo' },
    { key: 'Ctrl+A', description: 'Select all' },
]

export function KeyboardShortcutsLegend({ shortcuts = DEFAULT_SHORTCUTS, className }: KeyboardShortcutsLegendProps) {
    return (
        <div className={cn('flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500', className)}>
            {shortcuts.map((shortcut) => (
                <span key={shortcut.key} className="flex items-center gap-1">
                    <kbd className="px-1.5 py-0.5 bg-slate-800 rounded text-slate-400 font-mono text-[10px]">
                        {shortcut.key}
                    </kbd>
                    <span>{shortcut.description}</span>
                </span>
            ))}
        </div>
    )
}

// ============================================================================
// WAVEFORM SCALE CONTROL
// ============================================================================

export interface WaveformScaleControlProps {
    value: number
    onChange: (value: number) => void
    min?: number
    max?: number
    className?: string
}

export function WaveformScaleControl({
    value,
    onChange,
    min = 0.5,
    max = 2.5,
    className,
}: WaveformScaleControlProps) {
    return (
        <div className={cn('flex items-center gap-2', className)}>
            <span className="text-xs text-slate-500 flex items-center gap-1">
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M2 12h2M6 12h2M10 8v8M14 6v12M18 10v4M22 12h2" strokeLinecap="round" />
                </svg>
                Wave
            </span>
            <div className="relative w-16 h-5 flex items-center">
                <div className="absolute inset-y-0 left-0 right-0 flex items-center">
                    <div className="w-full h-1 bg-slate-700 rounded-full">
                        <div
                            className="h-full bg-fuchsia-500 rounded-full"
                            style={{ width: `${((value - min) / (max - min)) * 100}%` }}
                        />
                    </div>
                </div>
                <input
                    type="range"
                    min={min}
                    max={max}
                    step="0.1"
                    value={value}
                    onChange={(e) => onChange(parseFloat(e.target.value))}
                    className="absolute inset-0 w-full opacity-0 cursor-pointer"
                    title={`Waveform scale: ${value.toFixed(1)}`}
                />
            </div>
            <span className="text-xs text-slate-400 font-mono w-8">{value.toFixed(1)}x</span>
        </div>
    )
}
