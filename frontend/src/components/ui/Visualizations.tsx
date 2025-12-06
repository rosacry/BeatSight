/**
 * Advanced visualization components for audio analysis and performance metrics.
 * Uses CSS/SVG for smooth, GPU-accelerated animations.
 */

import {
    forwardRef,
    useEffect,
    useRef,
    useState,
    useMemo,
    useCallback,
    type HTMLAttributes,
} from 'react'
// CVA reserved for future variants
import { cn } from '../../lib/utils'

// ============================================================================
// TYPES
// ============================================================================

export interface FrequencyData {
    frequencies: number[]  // 0-1 normalized values
    labels?: string[]
}

export interface WaveformPoint {
    time: number
    amplitude: number
}

export interface HeatmapCell {
    x: number
    y: number
    value: number  // 0-1 normalized
    label?: string
}

export interface RadarDataPoint {
    label: string
    value: number  // 0-1 normalized
    color?: string
}

// ============================================================================
// AUDIO SPECTRUM VISUALIZER
// ============================================================================

export interface SpectrumVisualizerProps extends HTMLAttributes<HTMLDivElement> {
    /** Frequency data (0-1 normalized) */
    data: number[]
    /** Number of bars to display */
    barCount?: number
    /** Bar style variant */
    variant?: 'bars' | 'rounded' | 'glow' | 'gradient'
    /** Color scheme */
    colorScheme?: 'cyan' | 'pink' | 'rainbow' | 'fire'
    /** Mirror effect */
    mirrored?: boolean
    /** Animation smoothing */
    smoothing?: number
    /** Show frequency labels */
    showLabels?: boolean
    /** Height of the visualizer */
    height?: number
}

const colorSchemes = {
    cyan: ['#0ea5e9', '#06b6d4', '#22d3ee'],
    pink: ['#ec4899', '#f472b6', '#fb7185'],
    rainbow: ['#ef4444', '#f97316', '#eab308', '#22c55e', '#06b6d4', '#8b5cf6'],
    fire: ['#fbbf24', '#f97316', '#ef4444', '#dc2626'],
}

export const SpectrumVisualizer = forwardRef<HTMLDivElement, SpectrumVisualizerProps>(
    (
        {
            className,
            data,
            barCount = 32,
            variant = 'bars',
            colorScheme = 'cyan',
            mirrored = false,
            smoothing = 0.8,
            showLabels = false,
            height = 120,
            ...props
        },
        ref
    ) => {
        const [smoothedData, setSmoothedData] = useState<number[]>([])
        const prevDataRef = useRef<number[]>([])

        // Apply smoothing
        useEffect(() => {
            const sampled = sampleData(data, barCount)
            const smoothed = sampled.map((value, i) => {
                const prev = prevDataRef.current[i] || 0
                return prev * smoothing + value * (1 - smoothing)
            })
            prevDataRef.current = smoothed
            setSmoothedData(smoothed)
        }, [data, barCount, smoothing])

        const colors = colorSchemes[colorScheme]
        const bars = mirrored ? [...smoothedData].reverse().concat(smoothedData) : smoothedData

        return (
            <div
                ref={ref}
                className={cn('relative', className)}
                style={{ height }}
                {...props}
            >
                <div className="absolute inset-0 flex items-end justify-center gap-[2px]">
                    {bars.map((value, index) => {
                        const colorIndex = Math.floor((index / bars.length) * colors.length)
                        const color = colors[colorIndex % colors.length]
                        const barHeight = Math.max(2, value * 100)

                        return (
                            <div
                                key={index}
                                className={cn(
                                    'flex-1 max-w-3 transition-all duration-75',
                                    variant === 'rounded' && 'rounded-t-full',
                                    variant === 'glow' && 'rounded-t-sm shadow-lg',
                                    variant === 'gradient' && 'rounded-t-sm'
                                )}
                                style={{
                                    height: `${barHeight}%`,
                                    backgroundColor: variant === 'gradient' ? undefined : color,
                                    backgroundImage: variant === 'gradient'
                                        ? `linear-gradient(to top, ${colors.join(', ')})`
                                        : undefined,
                                    boxShadow: variant === 'glow' ? `0 0 8px ${color}` : undefined,
                                }}
                            />
                        )
                    })}
                </div>

                {/* Reflection for mirrored mode */}
                {mirrored && (
                    <div
                        className="absolute inset-x-0 bottom-0 h-1/4 opacity-30 pointer-events-none"
                        style={{
                            background: 'linear-gradient(to bottom, transparent, rgba(0,0,0,0.8))',
                        }}
                    />
                )}

                {showLabels && (
                    <div className="absolute bottom-0 inset-x-0 flex justify-between text-[10px] text-gray-500">
                        <span>20Hz</span>
                        <span>1kHz</span>
                        <span>20kHz</span>
                    </div>
                )}
            </div>
        )
    }
)
SpectrumVisualizer.displayName = 'SpectrumVisualizer'

// ============================================================================
// WAVEFORM DISPLAY
// ============================================================================

export interface WaveformDisplayProps extends HTMLAttributes<HTMLDivElement> {
    /** Waveform data points */
    data: number[]
    /** Current playback position (0-1) */
    progress?: number
    /** Color for played portion */
    playedColor?: string
    /** Color for unplayed portion */
    unplayedColor?: string
    /** Show center line */
    showCenterLine?: boolean
    /** Click handler for seeking */
    onSeek?: (position: number) => void
    /** Interactive mode */
    interactive?: boolean
    /** Height */
    height?: number
}

export const WaveformDisplay = forwardRef<HTMLDivElement, WaveformDisplayProps>(
    (
        {
            className,
            data,
            progress = 0,
            playedColor = '#0ea5e9',
            unplayedColor = '#374151',
            showCenterLine = true,
            onSeek,
            interactive = true,
            height = 80,
            ...props
        },
        ref
    ) => {
        const containerRef = useRef<HTMLDivElement>(null)
        const [hoverPosition, setHoverPosition] = useState<number | null>(null)

        const handleClick = useCallback((e: React.MouseEvent) => {
            if (!interactive || !onSeek || !containerRef.current) return
            const rect = containerRef.current.getBoundingClientRect()
            const position = (e.clientX - rect.left) / rect.width
            onSeek(Math.max(0, Math.min(1, position)))
        }, [interactive, onSeek])

        const handleMouseMove = useCallback((e: React.MouseEvent) => {
            if (!interactive || !containerRef.current) return
            const rect = containerRef.current.getBoundingClientRect()
            const position = (e.clientX - rect.left) / rect.width
            setHoverPosition(Math.max(0, Math.min(1, position)))
        }, [interactive])

        const handleMouseLeave = useCallback(() => {
            setHoverPosition(null)
        }, [])

        // Generate SVG path for waveform
        const path = useMemo(() => {
            if (data.length === 0) return ''

            const points: string[] = []
            const width = 100
            const centerY = 50

            data.forEach((amplitude, i) => {
                const x = (i / data.length) * width
                const y = centerY - amplitude * 40  // Scale amplitude
                points.push(i === 0 ? `M ${x} ${y}` : `L ${x} ${y}`)
            })

            // Mirror for bottom half
            for (let i = data.length - 1; i >= 0; i--) {
                const x = (i / data.length) * width
                const y = centerY + data[i] * 40
                points.push(`L ${x} ${y}`)
            }

            points.push('Z')
            return points.join(' ')
        }, [data])

        return (
            <div
                ref={ref}
                className={cn(
                    'relative select-none',
                    interactive && 'cursor-pointer',
                    className
                )}
                style={{ height }}
                {...props}
            >
                <div
                    ref={containerRef}
                    className="absolute inset-0"
                    onClick={handleClick}
                    onMouseMove={handleMouseMove}
                    onMouseLeave={handleMouseLeave}
                >
                    <svg
                        viewBox="0 0 100 100"
                        preserveAspectRatio="none"
                        className="w-full h-full"
                    >
                        <defs>
                            <clipPath id="progress-clip">
                                <rect x="0" y="0" width={progress * 100} height="100" />
                            </clipPath>
                            <clipPath id="remaining-clip">
                                <rect x={progress * 100} y="0" width={(1 - progress) * 100} height="100" />
                            </clipPath>
                        </defs>

                        {/* Unplayed portion */}
                        <path
                            d={path}
                            fill={unplayedColor}
                            clipPath="url(#remaining-clip)"
                        />

                        {/* Played portion */}
                        <path
                            d={path}
                            fill={playedColor}
                            clipPath="url(#progress-clip)"
                        />

                        {/* Center line */}
                        {showCenterLine && (
                            <line
                                x1="0" y1="50" x2="100" y2="50"
                                stroke="rgba(255,255,255,0.1)"
                                strokeWidth="0.5"
                            />
                        )}
                    </svg>

                    {/* Progress indicator */}
                    <div
                        className="absolute top-0 bottom-0 w-0.5 bg-white shadow-lg"
                        style={{ left: `${progress * 100}%` }}
                    />

                    {/* Hover indicator */}
                    {hoverPosition !== null && interactive && (
                        <div
                            className="absolute top-0 bottom-0 w-0.5 bg-white/50"
                            style={{ left: `${hoverPosition * 100}%` }}
                        />
                    )}
                </div>
            </div>
        )
    }
)
WaveformDisplay.displayName = 'WaveformDisplay'

// ============================================================================
// RADAR CHART
// ============================================================================

export interface RadarChartProps extends HTMLAttributes<HTMLDivElement> {
    /** Data points */
    data: RadarDataPoint[]
    /** Size of the chart */
    size?: number
    /** Fill opacity */
    fillOpacity?: number
    /** Show labels */
    showLabels?: boolean
    /** Show grid */
    showGrid?: boolean
    /** Number of grid levels */
    gridLevels?: number
    /** Color */
    color?: string
    /** Animate on mount */
    animated?: boolean
}

export const RadarChart = forwardRef<HTMLDivElement, RadarChartProps>(
    (
        {
            className,
            data,
            size = 200,
            fillOpacity = 0.3,
            showLabels = true,
            showGrid = true,
            gridLevels = 5,
            color = '#0ea5e9',
            animated = true,
            ...props
        },
        ref
    ) => {
        const [isVisible, setIsVisible] = useState(!animated)
        const centerX = size / 2
        const centerY = size / 2
        const radius = (size / 2) - 30  // Leave room for labels

        useEffect(() => {
            if (animated) {
                const timer = setTimeout(() => setIsVisible(true), 100)
                return () => clearTimeout(timer)
            }
        }, [animated])

        const angleStep = (2 * Math.PI) / data.length

        // Generate polygon points
        const points = data.map((point, i) => {
            const angle = -Math.PI / 2 + i * angleStep
            const value = isVisible ? point.value : 0
            const x = centerX + Math.cos(angle) * radius * value
            const y = centerY + Math.sin(angle) * radius * value
            return `${x},${y}`
        }).join(' ')

        // Generate axis lines
        const axes = data.map((_, i) => {
            const angle = -Math.PI / 2 + i * angleStep
            const x = centerX + Math.cos(angle) * radius
            const y = centerY + Math.sin(angle) * radius
            return { x, y }
        })

        // Generate grid polygons
        const grids = Array.from({ length: gridLevels }, (_, level) => {
            const scale = (level + 1) / gridLevels
            return data.map((_, i) => {
                const angle = -Math.PI / 2 + i * angleStep
                const x = centerX + Math.cos(angle) * radius * scale
                const y = centerY + Math.sin(angle) * radius * scale
                return `${x},${y}`
            }).join(' ')
        })

        return (
            <div
                ref={ref}
                className={cn('relative', className)}
                style={{ width: size, height: size }}
                {...props}
            >
                <svg viewBox={`0 0 ${size} ${size}`} className="w-full h-full">
                    {/* Grid */}
                    {showGrid && grids.map((gridPoints, i) => (
                        <polygon
                            key={i}
                            points={gridPoints}
                            fill="none"
                            stroke="rgba(255,255,255,0.1)"
                            strokeWidth="1"
                        />
                    ))}

                    {/* Axis lines */}
                    {axes.map((axis, i) => (
                        <line
                            key={i}
                            x1={centerX}
                            y1={centerY}
                            x2={axis.x}
                            y2={axis.y}
                            stroke="rgba(255,255,255,0.1)"
                            strokeWidth="1"
                        />
                    ))}

                    {/* Data polygon */}
                    <polygon
                        points={points}
                        fill={color}
                        fillOpacity={fillOpacity}
                        stroke={color}
                        strokeWidth="2"
                        className={cn(
                            animated && 'transition-all duration-700 ease-out'
                        )}
                    />

                    {/* Data points */}
                    {data.map((point, i) => {
                        const angle = -Math.PI / 2 + i * angleStep
                        const value = isVisible ? point.value : 0
                        const x = centerX + Math.cos(angle) * radius * value
                        const y = centerY + Math.sin(angle) * radius * value
                        return (
                            <circle
                                key={i}
                                cx={x}
                                cy={y}
                                r="4"
                                fill={point.color || color}
                                className={cn(
                                    animated && 'transition-all duration-700 ease-out'
                                )}
                            />
                        )
                    })}
                </svg>

                {/* Labels */}
                {showLabels && data.map((point, i) => {
                    const angle = -Math.PI / 2 + i * angleStep
                    const labelRadius = radius + 20
                    const x = centerX + Math.cos(angle) * labelRadius
                    const y = centerY + Math.sin(angle) * labelRadius

                    return (
                        <span
                            key={i}
                            className="absolute text-xs text-gray-400 transform -translate-x-1/2 -translate-y-1/2 whitespace-nowrap"
                            style={{ left: x, top: y }}
                        >
                            {point.label}
                        </span>
                    )
                })}
            </div>
        )
    }
)
RadarChart.displayName = 'RadarChart'

// ============================================================================
// HEATMAP
// ============================================================================

export interface HeatmapProps extends HTMLAttributes<HTMLDivElement> {
    /** Heatmap data */
    data: HeatmapCell[]
    /** Number of columns */
    columns: number
    /** Number of rows */
    rows: number
    /** Cell size */
    cellSize?: number
    /** Gap between cells */
    gap?: number
    /** Color range [low, high] */
    colorRange?: [string, string]
    /** Show tooltips */
    showTooltips?: boolean
    /** Cell click handler */
    onCellClick?: (cell: HeatmapCell) => void
    /** X-axis labels */
    xLabels?: string[]
    /** Y-axis labels */
    yLabels?: string[]
}

export const Heatmap = forwardRef<HTMLDivElement, HeatmapProps>(
    (
        {
            className,
            data,
            columns,
            rows,
            cellSize = 24,
            gap = 2,
            colorRange = ['#1e293b', '#0ea5e9'],
            showTooltips = true,
            onCellClick,
            xLabels,
            yLabels,
            ...props
        },
        ref
    ) => {
        const [hoveredCell, setHoveredCell] = useState<HeatmapCell | null>(null)

        // Create a map for quick lookup
        const cellMap = useMemo(() => {
            const map = new Map<string, HeatmapCell>()
            data.forEach(cell => {
                map.set(`${cell.x}-${cell.y}`, cell)
            })
            return map
        }, [data])

        const interpolateColor = (value: number) => {
            // Simple linear interpolation between two colors
            const hex1 = colorRange[0].replace('#', '')
            const hex2 = colorRange[1].replace('#', '')

            const r1 = parseInt(hex1.slice(0, 2), 16)
            const g1 = parseInt(hex1.slice(2, 4), 16)
            const b1 = parseInt(hex1.slice(4, 6), 16)

            const r2 = parseInt(hex2.slice(0, 2), 16)
            const g2 = parseInt(hex2.slice(2, 4), 16)
            const b2 = parseInt(hex2.slice(4, 6), 16)

            const r = Math.round(r1 + (r2 - r1) * value)
            const g = Math.round(g1 + (g2 - g1) * value)
            const b = Math.round(b1 + (b2 - b1) * value)

            return `rgb(${r}, ${g}, ${b})`
        }

        const gridWidth = columns * (cellSize + gap) - gap
        const gridHeight = rows * (cellSize + gap) - gap

        return (
            <div ref={ref} className={cn('relative', className)} {...props}>
                {/* Y-axis labels */}
                {yLabels && (
                    <div
                        className="absolute right-full mr-2 flex flex-col justify-between"
                        style={{ height: gridHeight }}
                    >
                        {yLabels.map((label, i) => (
                            <span
                                key={i}
                                className="text-xs text-gray-500"
                                style={{ height: cellSize, lineHeight: `${cellSize}px` }}
                            >
                                {label}
                            </span>
                        ))}
                    </div>
                )}

                {/* Grid */}
                <div
                    className="grid"
                    style={{
                        gridTemplateColumns: `repeat(${columns}, ${cellSize}px)`,
                        gap,
                    }}
                >
                    {Array.from({ length: rows * columns }, (_, index) => {
                        const x = index % columns
                        const y = Math.floor(index / columns)
                        const cell = cellMap.get(`${x}-${y}`)
                        const value = cell?.value || 0

                        return (
                            <div
                                key={index}
                                className={cn(
                                    'rounded-sm transition-all duration-150',
                                    onCellClick && 'cursor-pointer hover:ring-2 hover:ring-white/50'
                                )}
                                style={{
                                    width: cellSize,
                                    height: cellSize,
                                    backgroundColor: interpolateColor(value),
                                }}
                                onClick={() => cell && onCellClick?.(cell)}
                                onMouseEnter={() => cell && setHoveredCell(cell)}
                                onMouseLeave={() => setHoveredCell(null)}
                            />
                        )
                    })}
                </div>

                {/* X-axis labels */}
                {xLabels && (
                    <div
                        className="flex justify-between mt-2"
                        style={{ width: gridWidth }}
                    >
                        {xLabels.map((label, i) => (
                            <span
                                key={i}
                                className="text-xs text-gray-500"
                                style={{ width: cellSize, textAlign: 'center' }}
                            >
                                {label}
                            </span>
                        ))}
                    </div>
                )}

                {/* Tooltip */}
                {showTooltips && hoveredCell && (
                    <div className="absolute -top-8 left-1/2 -translate-x-1/2 px-2 py-1 bg-gray-800 rounded text-xs text-white whitespace-nowrap z-10">
                        {hoveredCell.label || `Value: ${(hoveredCell.value * 100).toFixed(0)}%`}
                    </div>
                )}
            </div>
        )
    }
)
Heatmap.displayName = 'Heatmap'

// ============================================================================
// DRUM KIT VISUALIZER (Specific to BeatSight)
// ============================================================================

export interface DrumHit {
    instrument: 'kick' | 'snare' | 'hihat' | 'tom1' | 'tom2' | 'tom3' | 'crash' | 'ride'
    velocity: number  // 0-1
    time: number
}

export interface DrumKitVisualizerProps extends HTMLAttributes<HTMLDivElement> {
    /** Active drum hits */
    activeHits: DrumHit[]
    /** Show instrument labels */
    showLabels?: boolean
    /** Glow intensity */
    glowIntensity?: number
}

const drumPositions: Record<DrumHit['instrument'], { x: number; y: number; size: number }> = {
    kick: { x: 50, y: 75, size: 24 },
    snare: { x: 35, y: 55, size: 18 },
    hihat: { x: 20, y: 35, size: 14 },
    tom1: { x: 35, y: 30, size: 14 },
    tom2: { x: 50, y: 25, size: 14 },
    tom3: { x: 65, y: 55, size: 16 },
    crash: { x: 25, y: 15, size: 16 },
    ride: { x: 75, y: 25, size: 18 },
}

const drumColors: Record<DrumHit['instrument'], string> = {
    kick: '#ef4444',
    snare: '#f97316',
    hihat: '#eab308',
    tom1: '#22c55e',
    tom2: '#06b6d4',
    tom3: '#3b82f6',
    crash: '#8b5cf6',
    ride: '#ec4899',
}

export const DrumKitVisualizer = forwardRef<HTMLDivElement, DrumKitVisualizerProps>(
    (
        {
            className,
            activeHits,
            showLabels = true,
            glowIntensity = 1,
            ...props
        },
        ref
    ) => {
        // Create a map of active instruments
        const activeMap = useMemo(() => {
            const map = new Map<DrumHit['instrument'], number>()
            activeHits.forEach(hit => {
                const existing = map.get(hit.instrument) || 0
                map.set(hit.instrument, Math.max(existing, hit.velocity))
            })
            return map
        }, [activeHits])

        return (
            <div
                ref={ref}
                className={cn('relative bg-gray-900/50 rounded-xl overflow-hidden', className)}
                style={{ aspectRatio: '4/3' }}
                {...props}
            >
                <svg viewBox="0 0 100 100" className="w-full h-full">
                    {Object.entries(drumPositions).map(([instrument, pos]) => {
                        const velocity = activeMap.get(instrument as DrumHit['instrument']) || 0
                        const color = drumColors[instrument as DrumHit['instrument']]
                        const scale = 1 + velocity * 0.2

                        return (
                            <g key={instrument}>
                                {/* Glow effect */}
                                {velocity > 0 && (
                                    <circle
                                        cx={pos.x}
                                        cy={pos.y}
                                        r={pos.size * scale + 5}
                                        fill={color}
                                        opacity={velocity * 0.3 * glowIntensity}
                                        className="transition-all duration-75"
                                    />
                                )}

                                {/* Drum pad */}
                                <circle
                                    cx={pos.x}
                                    cy={pos.y}
                                    r={pos.size * scale}
                                    fill={velocity > 0 ? color : '#374151'}
                                    stroke={color}
                                    strokeWidth="2"
                                    opacity={0.3 + velocity * 0.7}
                                    className="transition-all duration-75"
                                />

                                {/* Label */}
                                {showLabels && (
                                    <text
                                        x={pos.x}
                                        y={pos.y + pos.size + 8}
                                        textAnchor="middle"
                                        fill="rgba(255,255,255,0.5)"
                                        fontSize="4"
                                        className="uppercase"
                                    >
                                        {instrument}
                                    </text>
                                )}
                            </g>
                        )
                    })}
                </svg>
            </div>
        )
    }
)
DrumKitVisualizer.displayName = 'DrumKitVisualizer'

// ============================================================================
// PERFORMANCE METER
// ============================================================================

export interface PerformanceMeterProps extends HTMLAttributes<HTMLDivElement> {
    /** Current score (0-100) */
    score: number
    /** Grade label */
    grade?: string
    /** Show percentage */
    showPercentage?: boolean
    /** Size */
    size?: number
    /** Ring thickness */
    thickness?: number
    /** Animated */
    animated?: boolean
}

const gradeColors: Record<string, string> = {
    'S+': '#fbbf24',
    'S': '#f97316',
    'A': '#22c55e',
    'B': '#06b6d4',
    'C': '#3b82f6',
    'D': '#8b5cf6',
    'F': '#ef4444',
}

export const PerformanceMeter = forwardRef<HTMLDivElement, PerformanceMeterProps>(
    (
        {
            className,
            score,
            grade,
            showPercentage = true,
            size = 120,
            thickness = 8,
            animated = true,
            ...props
        },
        ref
    ) => {
        const [displayScore, setDisplayScore] = useState(animated ? 0 : score)

        useEffect(() => {
            if (!animated) {
                setDisplayScore(score)
                return
            }

            let frame: number
            const duration = 1000
            const start = performance.now()
            const startScore = displayScore

            const animate = (now: number) => {
                const elapsed = now - start
                const progress = Math.min(elapsed / duration, 1)
                const eased = 1 - Math.pow(1 - progress, 3)  // Ease out cubic
                setDisplayScore(startScore + (score - startScore) * eased)

                if (progress < 1) {
                    frame = requestAnimationFrame(animate)
                }
            }

            frame = requestAnimationFrame(animate)
            return () => cancelAnimationFrame(frame)
        }, [score, animated])

        const circumference = 2 * Math.PI * ((size - thickness) / 2)
        const strokeDashoffset = circumference * (1 - displayScore / 100)
        const color = grade ? gradeColors[grade] || '#0ea5e9' : '#0ea5e9'

        return (
            <div
                ref={ref}
                className={cn('relative', className)}
                style={{ width: size, height: size }}
                {...props}
            >
                <svg viewBox={`0 0 ${size} ${size}`} className="w-full h-full -rotate-90">
                    {/* Background ring */}
                    <circle
                        cx={size / 2}
                        cy={size / 2}
                        r={(size - thickness) / 2}
                        fill="none"
                        stroke="rgba(255,255,255,0.1)"
                        strokeWidth={thickness}
                    />

                    {/* Progress ring */}
                    <circle
                        cx={size / 2}
                        cy={size / 2}
                        r={(size - thickness) / 2}
                        fill="none"
                        stroke={color}
                        strokeWidth={thickness}
                        strokeLinecap="round"
                        strokeDasharray={circumference}
                        strokeDashoffset={strokeDashoffset}
                        className="transition-all duration-300"
                        style={{
                            filter: `drop-shadow(0 0 6px ${color})`,
                        }}
                    />
                </svg>

                {/* Center content */}
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                    {grade && (
                        <span
                            className="text-2xl font-bold"
                            style={{ color }}
                        >
                            {grade}
                        </span>
                    )}
                    {showPercentage && (
                        <span className="text-sm text-gray-400">
                            {Math.round(displayScore)}%
                        </span>
                    )}
                </div>
            </div>
        )
    }
)
PerformanceMeter.displayName = 'PerformanceMeter'

// ============================================================================
// TIMELINE VISUALIZATION
// ============================================================================

export interface TimelineEvent {
    id: string
    time: number  // In seconds
    type: string
    label?: string
    color?: string
}

export interface TimelineVisualizerProps extends HTMLAttributes<HTMLDivElement> {
    /** Events to display */
    events: TimelineEvent[]
    /** Total duration in seconds */
    duration: number
    /** Current time in seconds */
    currentTime?: number
    /** Zoom level */
    zoom?: number
    /** Show time markers */
    showTimeMarkers?: boolean
    /** Event click handler */
    onEventClick?: (event: TimelineEvent) => void
    /** Seek handler */
    onSeek?: (time: number) => void
    /** Height */
    height?: number
}

export const TimelineVisualizer = forwardRef<HTMLDivElement, TimelineVisualizerProps>(
    (
        {
            className,
            events,
            duration,
            currentTime = 0,
            zoom = 1,
            showTimeMarkers = true,
            onEventClick,
            onSeek,
            height = 60,
            ...props
        },
        ref
    ) => {
        const containerRef = useRef<HTMLDivElement>(null)

        const handleClick = useCallback((e: React.MouseEvent) => {
            if (!onSeek || !containerRef.current) return
            const rect = containerRef.current.getBoundingClientRect()
            const position = (e.clientX - rect.left) / rect.width
            onSeek(position * duration)
        }, [onSeek, duration])

        const formatTime = (seconds: number) => {
            const mins = Math.floor(seconds / 60)
            const secs = Math.floor(seconds % 60)
            return `${mins}:${secs.toString().padStart(2, '0')}`
        }

        // Generate time markers
        const markers = useMemo(() => {
            const interval = Math.ceil(duration / 10 / zoom) * zoom
            const result: number[] = []
            for (let t = 0; t <= duration; t += interval) {
                result.push(t)
            }
            return result
        }, [duration, zoom])

        return (
            <div
                ref={ref}
                className={cn('relative bg-gray-900/50 rounded-lg overflow-hidden', className)}
                style={{ height }}
                {...props}
            >
                <div
                    ref={containerRef}
                    className="absolute inset-0 cursor-pointer"
                    onClick={handleClick}
                >
                    {/* Time markers */}
                    {showTimeMarkers && markers.map(time => (
                        <div
                            key={time}
                            className="absolute top-0 bottom-0 border-l border-gray-700"
                            style={{ left: `${(time / duration) * 100}%` }}
                        >
                            <span className="absolute top-1 left-1 text-[10px] text-gray-500">
                                {formatTime(time)}
                            </span>
                        </div>
                    ))}

                    {/* Events */}
                    {events.map(event => (
                        <div
                            key={event.id}
                            className={cn(
                                'absolute top-1/2 -translate-y-1/2 w-2 h-2 rounded-full',
                                onEventClick && 'cursor-pointer hover:scale-150 transition-transform'
                            )}
                            style={{
                                left: `${(event.time / duration) * 100}%`,
                                backgroundColor: event.color || '#0ea5e9',
                                boxShadow: `0 0 6px ${event.color || '#0ea5e9'}`,
                            }}
                            onClick={(e) => {
                                e.stopPropagation()
                                onEventClick?.(event)
                            }}
                            title={event.label}
                        />
                    ))}

                    {/* Playhead */}
                    <div
                        className="absolute top-0 bottom-0 w-0.5 bg-white shadow-lg z-10"
                        style={{ left: `${(currentTime / duration) * 100}%` }}
                    >
                        <div className="absolute -top-1 left-1/2 -translate-x-1/2 w-0 h-0 border-l-[4px] border-r-[4px] border-t-[6px] border-l-transparent border-r-transparent border-t-white" />
                    </div>
                </div>
            </div>
        )
    }
)
TimelineVisualizer.displayName = 'TimelineVisualizer'

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function sampleData(data: number[], targetLength: number): number[] {
    if (data.length === 0) return Array(targetLength).fill(0)
    if (data.length === targetLength) return data

    const result: number[] = []
    const step = data.length / targetLength

    for (let i = 0; i < targetLength; i++) {
        const start = Math.floor(i * step)
        const end = Math.floor((i + 1) * step)
        let sum = 0
        for (let j = start; j < end && j < data.length; j++) {
            sum += data[j]
        }
        result.push(sum / (end - start))
    }

    return result
}

// ============================================================================
// EXPORTS
// ============================================================================

// Types are exported inline with interfaces above
