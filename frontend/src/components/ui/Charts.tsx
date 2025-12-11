/**
 * Simple, beautiful chart components using CSS/SVG (no external dependencies).
 * Perfect for dashboards and analytics displays.
 */

import {
    forwardRef,
    useMemo,
    type HTMLAttributes,
} from 'react'
import { clsx } from 'clsx'

// ============================================================================
// TYPES
// ============================================================================

export interface DataPoint {
    label: string
    value: number
    color?: string
}

// ============================================================================
// BAR CHART
// ============================================================================

export interface BarChartProps extends HTMLAttributes<HTMLDivElement> {
    /** Data points to display */
    data: DataPoint[]
    /** Chart height */
    height?: number
    /** Show value labels */
    showValues?: boolean
    /** Horizontal layout */
    horizontal?: boolean
    /** Animate bars on mount */
    animated?: boolean
    /** Format value for display */
    formatValue?: (value: number) => string
    /** Bar color (if not set per-item) */
    barColor?: string
}

export const BarChart = forwardRef<HTMLDivElement, BarChartProps>(
    (
        {
            className,
            data,
            height = 200,
            showValues = true,
            horizontal = false,
            animated = true,
            formatValue = (v) => v.toLocaleString(),
            barColor = 'from-primary-500 to-primary-400',
            ...props
        },
        ref
    ) => {
        const maxValue = Math.max(...data.map((d) => d.value), 1)

        if (horizontal) {
            return (
                <div ref={ref} className={clsx('space-y-3', className)} {...props}>
                    {data.map((item, index) => (
                        <div key={item.label} className="space-y-1">
                            <div className="flex justify-between text-sm">
                                <span className="text-gray-400">{item.label}</span>
                                {showValues && (
                                    <span className="text-white font-medium">{formatValue(item.value)}</span>
                                )}
                            </div>
                            <div className="h-2 bg-gray-700/50 rounded-full overflow-hidden">
                                <div
                                    className={clsx(
                                        'h-full rounded-full bg-gradient-to-r',
                                        item.color || barColor,
                                        animated && 'transition-all duration-700 ease-out'
                                    )}
                                    style={{
                                        width: `${(item.value / maxValue) * 100}%`,
                                        transitionDelay: animated ? `${index * 50}ms` : '0ms',
                                    }}
                                />
                            </div>
                        </div>
                    ))}
                </div>
            )
        }

        return (
            <div ref={ref} className={clsx('flex flex-col', className)} style={{ height }} {...props}>
                <div className="flex-1 flex items-end gap-2">
                    {data.map((item, index) => (
                        <div key={item.label} className="flex-1 flex flex-col items-center gap-1">
                            {showValues && (
                                <span className="text-xs text-gray-400 font-medium">
                                    {formatValue(item.value)}
                                </span>
                            )}
                            <div
                                className={clsx(
                                    'w-full rounded-t-lg bg-gradient-to-t',
                                    item.color || barColor,
                                    animated && 'transition-all duration-700 ease-out'
                                )}
                                style={{
                                    height: `${(item.value / maxValue) * 100}%`,
                                    minHeight: item.value > 0 ? '4px' : '0',
                                    transitionDelay: animated ? `${index * 50}ms` : '0ms',
                                }}
                            />
                        </div>
                    ))}
                </div>
                <div className="flex gap-2 mt-2 pt-2 border-t border-gray-700/50">
                    {data.map((item) => (
                        <div key={item.label} className="flex-1 text-center">
                            <span className="text-xs text-gray-400 truncate block">{item.label}</span>
                        </div>
                    ))}
                </div>
            </div>
        )
    }
)

BarChart.displayName = 'BarChart'

// ============================================================================
// DONUT/PIE CHART
// ============================================================================

export interface DonutChartProps extends HTMLAttributes<HTMLDivElement> {
    /** Data points to display */
    data: DataPoint[]
    /** Chart size */
    size?: number
    /** Donut thickness (0-50, where 50 is full pie) */
    thickness?: number
    /** Show center label */
    centerLabel?: string
    /** Show center value */
    centerValue?: string
    /** Animate on mount */
    animated?: boolean
    /** Show legend */
    showLegend?: boolean
}

const defaultColors = [
    'text-primary-500',
    'text-accent-500',
    'text-green-500',
    'text-yellow-500',
    'text-red-500',
    'text-purple-500',
    'text-primary-500',
    'text-orange-500',
]

export const DonutChart = forwardRef<HTMLDivElement, DonutChartProps>(
    (
        {
            className,
            data,
            size = 160,
            thickness = 20,
            centerLabel,
            centerValue,
            animated = true,
            showLegend = true,
            ...props
        },
        ref
    ) => {
        const total = data.reduce((sum, d) => sum + d.value, 0)
        const radius = 50 - thickness / 2
        const circumference = 2 * Math.PI * radius

        const segments = useMemo(() => {
            let currentOffset = 0
            return data.map((item, index) => {
                const percentage = total > 0 ? item.value / total : 0
                const dashLength = percentage * circumference
                const offset = currentOffset
                currentOffset += dashLength

                return {
                    ...item,
                    percentage,
                    dashLength,
                    offset,
                    color: item.color || defaultColors[index % defaultColors.length],
                }
            })
        }, [data, total, circumference])

        return (
            <div ref={ref} className={clsx('flex items-center gap-6', className)} {...props}>
                <div className="relative" style={{ width: size, height: size }}>
                    <svg viewBox="0 0 100 100" className="transform -rotate-90">
                        {/* Background circle */}
                        <circle
                            cx="50"
                            cy="50"
                            r={radius}
                            fill="none"
                            stroke="currentColor"
                            strokeWidth={thickness}
                            className="text-gray-700/50"
                        />

                        {/* Data segments */}
                        {segments.map((segment, index) => (
                            <circle
                                key={segment.label}
                                cx="50"
                                cy="50"
                                r={radius}
                                fill="none"
                                stroke="currentColor"
                                strokeWidth={thickness}
                                strokeDasharray={`${segment.dashLength} ${circumference}`}
                                strokeDashoffset={-segment.offset}
                                strokeLinecap="round"
                                className={clsx(
                                    segment.color,
                                    animated && 'transition-all duration-1000 ease-out'
                                )}
                                style={{
                                    transitionDelay: animated ? `${index * 100}ms` : '0ms',
                                }}
                            />
                        ))}
                    </svg>

                    {/* Center content */}
                    {(centerLabel || centerValue) && (
                        <div className="absolute inset-0 flex flex-col items-center justify-center">
                            {centerValue && (
                                <span className="text-2xl font-bold text-white">{centerValue}</span>
                            )}
                            {centerLabel && (
                                <span className="text-xs text-gray-400">{centerLabel}</span>
                            )}
                        </div>
                    )}
                </div>

                {/* Legend */}
                {showLegend && (
                    <div className="space-y-2">
                        {segments.map((segment) => (
                            <div key={segment.label} className="flex items-center gap-2">
                                <div className={clsx('w-3 h-3 rounded-full bg-current', segment.color)} />
                                <span className="text-sm text-gray-400">{segment.label}</span>
                                <span className="text-sm text-white font-medium ml-auto">
                                    {(segment.percentage * 100).toFixed(1)}%
                                </span>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        )
    }
)

DonutChart.displayName = 'DonutChart'

// ============================================================================
// LINE/AREA CHART
// ============================================================================

export interface LineChartProps extends HTMLAttributes<HTMLDivElement> {
    /** Data points (x is index, y is value) */
    data: number[]
    /** Chart height */
    height?: number
    /** Show area fill */
    showArea?: boolean
    /** Show data points */
    showPoints?: boolean
    /** Show grid lines */
    showGrid?: boolean
    /** Line color */
    lineColor?: string
    /** Area gradient colors */
    areaGradient?: [string, string]
    /** X-axis labels */
    labels?: string[]
    /** Animate on mount */
    animated?: boolean
    /** Curved line */
    curved?: boolean
}

export const LineChart = forwardRef<HTMLDivElement, LineChartProps>(
    (
        {
            className,
            data,
            height = 200,
            showArea = true,
            showPoints = false,
            showGrid = true,
            lineColor = '#0ea5e9', // primary-500
            areaGradient = ['rgba(14, 165, 233, 0.3)', 'rgba(14, 165, 233, 0)'],
            labels,
            animated = true,
            curved = true,
            ...props
        },
        ref
    ) => {
        const padding = 20
        const chartWidth = 100
        const chartHeight = 100

        const minValue = Math.min(...data)
        const maxValue = Math.max(...data)
        const range = maxValue - minValue || 1

        const points = useMemo(() => {
            return data.map((value, index) => ({
                x: padding + (index / Math.max(data.length - 1, 1)) * (chartWidth - 2 * padding),
                y: padding + (1 - (value - minValue) / range) * (chartHeight - 2 * padding),
                value,
            }))
        }, [data, minValue, range])

        const linePath = useMemo(() => {
            if (points.length === 0) return ''

            if (curved && points.length > 2) {
                // Catmull-Rom to Bezier conversion for smooth curves
                let path = `M ${points[0].x} ${points[0].y}`

                for (let i = 0; i < points.length - 1; i++) {
                    const p0 = points[Math.max(i - 1, 0)]
                    const p1 = points[i]
                    const p2 = points[i + 1]
                    const p3 = points[Math.min(i + 2, points.length - 1)]

                    const cp1x = p1.x + (p2.x - p0.x) / 6
                    const cp1y = p1.y + (p2.y - p0.y) / 6
                    const cp2x = p2.x - (p3.x - p1.x) / 6
                    const cp2y = p2.y - (p3.y - p1.y) / 6

                    path += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2.x} ${p2.y}`
                }

                return path
            }

            return points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ')
        }, [points, curved])

        const areaPath = useMemo(() => {
            if (!showArea || points.length === 0) return ''
            const bottomY = chartHeight - padding
            return `${linePath} L ${points[points.length - 1].x} ${bottomY} L ${points[0].x} ${bottomY} Z`
        }, [linePath, showArea, points])

        const gridLines = showGrid ? [0, 0.25, 0.5, 0.75, 1] : []

        return (
            <div ref={ref} className={clsx('relative', className)} style={{ height }} {...props}>
                <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} preserveAspectRatio="none" className="w-full h-full">
                    <defs>
                        <linearGradient id="areaGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                            <stop offset="0%" stopColor={areaGradient[0]} />
                            <stop offset="100%" stopColor={areaGradient[1]} />
                        </linearGradient>
                    </defs>

                    {/* Grid lines */}
                    {gridLines.map((ratio) => {
                        const y = padding + ratio * (chartHeight - 2 * padding)
                        return (
                            <line
                                key={ratio}
                                x1={padding}
                                y1={y}
                                x2={chartWidth - padding}
                                y2={y}
                                stroke="currentColor"
                                strokeWidth="0.5"
                                className="text-gray-700/50"
                            />
                        )
                    })}

                    {/* Area */}
                    {showArea && areaPath && (
                        <path
                            d={areaPath}
                            fill="url(#areaGradient)"
                            className={animated ? 'animate-fade-in' : ''}
                        />
                    )}

                    {/* Line */}
                    <path
                        d={linePath}
                        fill="none"
                        stroke={lineColor}
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        className={animated ? 'animate-draw-line' : ''}
                        style={{
                            strokeDasharray: animated ? 1000 : 0,
                            strokeDashoffset: animated ? 1000 : 0,
                            animation: animated ? 'draw-line 1.5s ease-out forwards' : 'none',
                        }}
                    />

                    {/* Data points */}
                    {showPoints &&
                        points.map((point, index) => (
                            <circle
                                key={index}
                                cx={point.x}
                                cy={point.y}
                                r="3"
                                fill={lineColor}
                                className={clsx(
                                    'transition-all duration-200',
                                    animated && 'opacity-0 animate-fade-in'
                                )}
                                style={{
                                    animationDelay: animated ? `${index * 50 + 500}ms` : '0ms',
                                    animationFillMode: 'forwards',
                                }}
                            />
                        ))}
                </svg>

                {/* X-axis labels */}
                {labels && labels.length > 0 && (
                    <div className="flex justify-between mt-2 px-5">
                        {labels.map((label, index) => (
                            <span key={index} className="text-xs text-gray-500">
                                {label}
                            </span>
                        ))}
                    </div>
                )}

                <style>{`
                    @keyframes draw-line {
                        to {
                            stroke-dashoffset: 0;
                        }
                    }
                    @keyframes fade-in {
                        from { opacity: 0; }
                        to { opacity: 1; }
                    }
                    .animate-fade-in {
                        animation: fade-in 0.5s ease-out forwards;
                    }
                `}</style>
            </div>
        )
    }
)

LineChart.displayName = 'LineChart'

// ============================================================================
// STAT CARD
// ============================================================================

export interface StatCardProps extends HTMLAttributes<HTMLDivElement> {
    /** Stat label */
    label: string
    /** Stat value */
    value: string | number
    /** Change percentage */
    change?: number
    /** Change label (e.g., "vs last week") */
    changeLabel?: string
    /** Icon */
    icon?: React.ReactNode
    /** Sparkline data */
    sparkline?: number[]
}

export const StatCard = forwardRef<HTMLDivElement, StatCardProps>(
    ({ className, label, value, change, changeLabel, icon, sparkline, ...props }, ref) => {
        const isPositive = change !== undefined && change >= 0

        return (
            <div
                ref={ref}
                className={clsx(
                    'p-6 rounded-xl border border-gray-700/50 bg-gray-800/50 backdrop-blur-sm',
                    className
                )}
                {...props}
            >
                <div className="flex items-start justify-between">
                    <div>
                        <p className="text-sm text-gray-400">{label}</p>
                        <p className="text-3xl font-bold text-white mt-1">{value}</p>

                        {change !== undefined && (
                            <div className="flex items-center gap-1 mt-2">
                                <span
                                    className={clsx(
                                        'flex items-center text-sm font-medium',
                                        isPositive ? 'text-green-400' : 'text-red-400'
                                    )}
                                >
                                    {isPositive ? (
                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 11l5-5m0 0l5 5m-5-5v12" />
                                        </svg>
                                    ) : (
                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 13l-5 5m0 0l-5-5m5 5V6" />
                                        </svg>
                                    )}
                                    {Math.abs(change).toFixed(1)}%
                                </span>
                                {changeLabel && (
                                    <span className="text-sm text-gray-500">{changeLabel}</span>
                                )}
                            </div>
                        )}
                    </div>

                    {icon && (
                        <div className="p-3 rounded-lg bg-primary-500/10 text-primary-400">
                            {icon}
                        </div>
                    )}
                </div>

                {sparkline && sparkline.length > 0 && (
                    <div className="mt-4 h-12">
                        <LineChart
                            data={sparkline}
                            height={48}
                            showArea={true}
                            showPoints={false}
                            showGrid={false}
                            lineColor={isPositive ? '#22c55e' : '#ef4444'}
                            areaGradient={
                                isPositive
                                    ? ['rgba(34, 197, 94, 0.2)', 'rgba(34, 197, 94, 0)']
                                    : ['rgba(239, 68, 68, 0.2)', 'rgba(239, 68, 68, 0)']
                            }
                        />
                    </div>
                )}
            </div>
        )
    }
)

StatCard.displayName = 'StatCard'

// ============================================================================
// PROGRESS RING (Circular Progress)
// ============================================================================

export interface ProgressRingProps extends HTMLAttributes<HTMLDivElement> {
    /** Progress value (0-100) */
    value: number
    /** Ring size */
    size?: number
    /** Ring thickness */
    thickness?: number
    /** Show percentage label */
    showLabel?: boolean
    /** Custom label */
    label?: string
    /** Color */
    color?: string
    /** Track color */
    trackColor?: string
}

export const ProgressRing = forwardRef<HTMLDivElement, ProgressRingProps>(
    (
        {
            className,
            value,
            size = 120,
            thickness = 8,
            showLabel = true,
            label,
            color = '#0ea5e9',
            trackColor = 'rgba(75, 85, 99, 0.5)',
            ...props
        },
        ref
    ) => {
        const radius = (size - thickness) / 2
        const circumference = 2 * Math.PI * radius
        const progress = Math.min(100, Math.max(0, value))
        const offset = circumference - (progress / 100) * circumference

        return (
            <div
                ref={ref}
                className={clsx('relative inline-flex items-center justify-center', className)}
                style={{ width: size, height: size }}
                {...props}
            >
                <svg width={size} height={size} className="transform -rotate-90">
                    {/* Track */}
                    <circle
                        cx={size / 2}
                        cy={size / 2}
                        r={radius}
                        fill="none"
                        stroke={trackColor}
                        strokeWidth={thickness}
                    />
                    {/* Progress */}
                    <circle
                        cx={size / 2}
                        cy={size / 2}
                        r={radius}
                        fill="none"
                        stroke={color}
                        strokeWidth={thickness}
                        strokeDasharray={circumference}
                        strokeDashoffset={offset}
                        strokeLinecap="round"
                        className="transition-all duration-500 ease-out"
                    />
                </svg>

                {showLabel && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span className="text-2xl font-bold text-white">{Math.round(progress)}%</span>
                        {label && <span className="text-xs text-gray-400">{label}</span>}
                    </div>
                )}
            </div>
        )
    }
)

ProgressRing.displayName = 'ProgressRing'
