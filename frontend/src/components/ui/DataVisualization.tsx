/**
 * Data Visualization Components
 * 
 * Premium data visualization components for BeatSight analytics
 * and statistics display with beautiful animations.
 */

import { useMemo, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { motion, useSpring, useTransform } from 'framer-motion';

// ============================================================================
// Stat Card
// ============================================================================

export interface StatCardProps {
    label: string;
    value: number | string;
    previousValue?: number;
    suffix?: string;
    prefix?: string;
    trend?: 'up' | 'down' | 'neutral';
    trendValue?: string;
    icon?: React.ReactNode;
    className?: string;
    animate?: boolean;
}

export function StatCard({
    label,
    value,
    previousValue,
    suffix = '',
    prefix = '',
    trend,
    trendValue,
    icon,
    className,
    animate = true,
}: StatCardProps) {
    const numericValue = typeof value === 'number' ? value : parseFloat(value) || 0;

    // Animated counter
    const springValue = useSpring(0, { duration: 1500 });
    const displayValue = useTransform(springValue, (v) =>
        typeof value === 'number' ? Math.floor(v).toLocaleString() : value
    );

    useEffect(() => {
        if (animate && typeof value === 'number') {
            springValue.set(numericValue);
        }
    }, [numericValue, animate, springValue, value]);

    // Calculate trend if not provided
    const calculatedTrend = trend ?? (
        previousValue !== undefined
            ? numericValue > previousValue ? 'up' : numericValue < previousValue ? 'down' : 'neutral'
            : undefined
    );

    const trendColors = {
        up: 'text-green-500',
        down: 'text-red-500',
        neutral: 'text-gray-400',
    };

    const trendIcons = {
        up: '↑',
        down: '↓',
        neutral: '→',
    };

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className={cn(
                'relative overflow-hidden rounded-xl',
                'bg-gradient-to-br from-gray-900/80 to-gray-950/80',
                'border border-white/10 backdrop-blur-sm',
                'p-6 transition-all duration-300',
                'hover:border-primary-500/30 hover:shadow-lg hover:shadow-cyan-500/10',
                className
            )}
        >
            {/* Background glow */}
            <div className="absolute inset-0 bg-gradient-to-br from-primary-500/5 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />

            <div className="relative z-10">
                <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-400 font-medium">{label}</span>
                    {icon && (
                        <span className="text-primary-400 opacity-60">{icon}</span>
                    )}
                </div>

                <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-bold text-white">
                        {prefix}
                        {animate && typeof value === 'number' ? (
                            <motion.span>{displayValue}</motion.span>
                        ) : (
                            value
                        )}
                        {suffix}
                    </span>

                    {calculatedTrend && (
                        <span className={cn('text-sm font-medium flex items-center gap-1', trendColors[calculatedTrend])}>
                            {trendIcons[calculatedTrend]}
                            {trendValue}
                        </span>
                    )}
                </div>
            </div>
        </motion.div>
    );
}

// ============================================================================
// Progress Ring
// ============================================================================

export interface ProgressRingProps {
    value: number;
    max?: number;
    size?: number;
    strokeWidth?: number;
    label?: string;
    showValue?: boolean;
    color?: 'cyan' | 'magenta' | 'green' | 'orange';
    className?: string;
}

export function ProgressRing({
    value,
    max = 100,
    size = 120,
    strokeWidth = 8,
    label,
    showValue = true,
    color = 'cyan',
    className,
}: ProgressRingProps) {
    const percentage = Math.min(100, (value / max) * 100);
    const radius = (size - strokeWidth) / 2;
    const circumference = radius * 2 * Math.PI;
    const offset = circumference - (percentage / 100) * circumference;

    const colors = {
        cyan: { stroke: '#ff66ab', glow: 'drop-shadow(0 0 8px rgba(255, 102, 171, 0.5))' },
        magenta: { stroke: '#ff3296', glow: 'drop-shadow(0 0 8px rgba(255, 50, 150, 0.5))' },
        green: { stroke: '#10b981', glow: 'drop-shadow(0 0 8px rgba(16, 185, 129, 0.5))' },
        orange: { stroke: '#f59e0b', glow: 'drop-shadow(0 0 8px rgba(245, 158, 11, 0.5))' },
    };

    return (
        <div className={cn('relative inline-flex items-center justify-center', className)}>
            <svg width={size} height={size} className="-rotate-90">
                {/* Background circle */}
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={strokeWidth}
                    className="text-gray-800"
                />

                {/* Progress circle */}
                <motion.circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke={colors[color].stroke}
                    strokeWidth={strokeWidth}
                    strokeLinecap="round"
                    initial={{ strokeDashoffset: circumference }}
                    animate={{ strokeDashoffset: offset }}
                    transition={{ duration: 1.5, ease: 'easeOut' }}
                    strokeDasharray={circumference}
                    style={{ filter: colors[color].glow }}
                />
            </svg>

            {/* Center content */}
            <div className="absolute inset-0 flex flex-col items-center justify-center">
                {showValue && (
                    <motion.span
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="text-2xl font-bold text-white"
                    >
                        {Math.round(percentage)}%
                    </motion.span>
                )}
                {label && (
                    <span className="text-xs text-gray-400 mt-1">{label}</span>
                )}
            </div>
        </div>
    );
}

// ============================================================================
// Bar Chart
// ============================================================================

export interface BarChartData {
    label: string;
    value: number;
    color?: string;
}

export interface BarChartProps {
    data: BarChartData[];
    height?: number;
    showValues?: boolean;
    animate?: boolean;
    orientation?: 'vertical' | 'horizontal';
    className?: string;
}

export function BarChart({
    data,
    height = 200,
    showValues = true,
    animate = true,
    orientation = 'vertical',
    className,
}: BarChartProps) {
    const maxValue = Math.max(...data.map(d => d.value));

    const defaultColors = [
        '#ff66ab', // primary pink
        '#ff3296', // magenta
        '#10b981', // green
        '#f59e0b', // orange
        '#8b5cf6', // purple
        '#ef4444', // red
    ];

    if (orientation === 'horizontal') {
        return (
            <div className={cn('space-y-3', className)}>
                {data.map((item, index) => {
                    const percentage = (item.value / maxValue) * 100;
                    const barColor = item.color || defaultColors[index % defaultColors.length];

                    return (
                        <div key={item.label} className="space-y-1">
                            <div className="flex justify-between text-sm">
                                <span className="text-gray-300">{item.label}</span>
                                {showValues && (
                                    <span className="text-gray-400">{item.value.toLocaleString()}</span>
                                )}
                            </div>
                            <div className="h-3 bg-gray-800 rounded-full overflow-hidden">
                                <motion.div
                                    initial={animate ? { width: 0 } : undefined}
                                    animate={{ width: `${percentage}%` }}
                                    transition={{ duration: 0.8, delay: index * 0.1 }}
                                    className="h-full rounded-full"
                                    style={{
                                        backgroundColor: barColor,
                                        boxShadow: `0 0 10px ${barColor}40`,
                                    }}
                                />
                            </div>
                        </div>
                    );
                })}
            </div>
        );
    }

    return (
        <div className={cn('flex items-end gap-2 justify-around', className)} style={{ height }}>
            {data.map((item, index) => {
                const percentage = (item.value / maxValue) * 100;
                const barColor = item.color || defaultColors[index % defaultColors.length];

                return (
                    <div key={item.label} className="flex flex-col items-center flex-1">
                        <motion.div
                            initial={animate ? { height: 0 } : undefined}
                            animate={{ height: `${percentage}%` }}
                            transition={{ duration: 0.8, delay: index * 0.1 }}
                            className="w-full max-w-12 rounded-t-lg"
                            style={{
                                backgroundColor: barColor,
                                boxShadow: `0 0 15px ${barColor}30`,
                            }}
                        />
                        {showValues && (
                            <motion.span
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                transition={{ delay: 0.5 + index * 0.1 }}
                                className="text-xs text-gray-300 mt-2"
                            >
                                {item.value.toLocaleString()}
                            </motion.span>
                        )}
                        <span className="text-xs text-gray-500 mt-1 truncate max-w-full">
                            {item.label}
                        </span>
                    </div>
                );
            })}
        </div>
    );
}

// ============================================================================
// Sparkline
// ============================================================================

export interface SparklineProps {
    data: number[];
    width?: number;
    height?: number;
    color?: string;
    showArea?: boolean;
    className?: string;
}

export function Sparkline({
    data,
    width = 150,
    height = 40,
    color = '#ff66ab',
    showArea = true,
    className,
}: SparklineProps) {
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;

    const points = data.map((value, index) => {
        const x = (index / (data.length - 1)) * width;
        const y = height - ((value - min) / range) * height;
        return `${x},${y}`;
    }).join(' ');

    const areaPoints = `0,${height} ${points} ${width},${height}`;

    return (
        <svg width={width} height={height} className={className}>
            {/* Gradient definition */}
            <defs>
                <linearGradient id={`sparkline-gradient-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={color} stopOpacity="0.3" />
                    <stop offset="100%" stopColor={color} stopOpacity="0" />
                </linearGradient>
            </defs>

            {/* Area fill */}
            {showArea && (
                <motion.polygon
                    points={areaPoints}
                    fill={`url(#sparkline-gradient-${color.replace('#', '')})`}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.5 }}
                />
            )}

            {/* Line */}
            <motion.polyline
                points={points}
                fill="none"
                stroke={color}
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 1 }}
                style={{ filter: `drop-shadow(0 0 4px ${color}80)` }}
            />

            {/* End dot */}
            <motion.circle
                cx={width}
                cy={height - ((data[data.length - 1] - min) / range) * height}
                r={3}
                fill={color}
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: 1, duration: 0.3 }}
                style={{ filter: `drop-shadow(0 0 4px ${color})` }}
            />
        </svg>
    );
}

// ============================================================================
// Activity Heatmap
// ============================================================================

export interface HeatmapData {
    date: string;
    value: number;
}

export interface ActivityHeatmapProps {
    data: HeatmapData[];
    weeks?: number;
    colorScale?: string[];
    className?: string;
}

export function ActivityHeatmap({
    data,
    weeks = 12,
    colorScale = ['#1e293b', '#0e4429', '#006d32', '#26a641', '#39d353'],
    className,
}: ActivityHeatmapProps) {
    const cellSize = 12;
    const gap = 3;
    const days = 7;

    // Create a map of date -> value
    const dataMap = new Map(data.map(d => [d.date, d.value]));
    const maxValue = Math.max(...data.map(d => d.value), 1);

    // Generate dates for the heatmap
    const dates = useMemo(() => {
        const result: string[] = [];
        const today = new Date();

        for (let i = weeks * 7 - 1; i >= 0; i--) {
            const date = new Date(today);
            date.setDate(date.getDate() - i);
            result.push(date.toISOString().split('T')[0]);
        }

        return result;
    }, [weeks]);

    const getColor = (value: number) => {
        if (value === 0) return colorScale[0];
        const index = Math.min(
            Math.ceil((value / maxValue) * (colorScale.length - 2)) + 1,
            colorScale.length - 1
        );
        return colorScale[index];
    };

    return (
        <div className={cn('overflow-x-auto', className)}>
            <svg
                width={weeks * (cellSize + gap) + gap}
                height={days * (cellSize + gap) + 20}
            >
                {/* Day labels */}
                {['M', '', 'W', '', 'F', '', 'S'].map((label, i) => (
                    <text
                        key={i}
                        x={0}
                        y={i * (cellSize + gap) + cellSize + 15}
                        className="fill-gray-500 text-[10px]"
                    >
                        {label}
                    </text>
                ))}

                {/* Cells */}
                <g transform="translate(20, 0)">
                    {dates.map((date, index) => {
                        const week = Math.floor(index / 7);
                        const day = index % 7;
                        const value = dataMap.get(date) || 0;

                        return (
                            <motion.rect
                                key={date}
                                x={week * (cellSize + gap)}
                                y={day * (cellSize + gap)}
                                width={cellSize}
                                height={cellSize}
                                rx={2}
                                fill={getColor(value)}
                                initial={{ opacity: 0, scale: 0.5 }}
                                animate={{ opacity: 1, scale: 1 }}
                                transition={{ delay: index * 0.005 }}
                                className="cursor-pointer hover:stroke-white hover:stroke-1"
                            >
                                <title>{`${date}: ${value}`}</title>
                            </motion.rect>
                        );
                    })}
                </g>
            </svg>
        </div>
    );
}

// ============================================================================
// Donut Chart
// ============================================================================

export interface DonutChartData {
    label: string;
    value: number;
    color?: string;
}

export interface DonutChartProps {
    data: DonutChartData[];
    size?: number;
    strokeWidth?: number;
    centerContent?: React.ReactNode;
    showLegend?: boolean;
    className?: string;
}

export function DonutChart({
    data,
    size = 200,
    strokeWidth = 30,
    centerContent,
    showLegend = true,
    className,
}: DonutChartProps) {
    const total = data.reduce((sum, item) => sum + item.value, 0);
    const radius = (size - strokeWidth) / 2;
    const circumference = radius * 2 * Math.PI;

    const defaultColors = [
        '#ff66ab',
        '#ff3296',
        '#10b981',
        '#f59e0b',
        '#8b5cf6',
    ];

    let accumulatedPercentage = 0;

    return (
        <div className={cn('flex items-center gap-8', className)}>
            <div className="relative" style={{ width: size, height: size }}>
                <svg width={size} height={size} className="-rotate-90">
                    {data.map((item, index) => {
                        const percentage = (item.value / total) * 100;
                        const dashOffset = circumference * (1 - percentage / 100);
                        const rotation = (accumulatedPercentage / 100) * 360;
                        const color = item.color || defaultColors[index % defaultColors.length];

                        accumulatedPercentage += percentage;

                        return (
                            <motion.circle
                                key={item.label}
                                cx={size / 2}
                                cy={size / 2}
                                r={radius}
                                fill="none"
                                stroke={color}
                                strokeWidth={strokeWidth}
                                strokeDasharray={circumference}
                                initial={{ strokeDashoffset: circumference }}
                                animate={{ strokeDashoffset: dashOffset }}
                                transition={{ duration: 1, delay: index * 0.2 }}
                                style={{
                                    transform: `rotate(${rotation}deg)`,
                                    transformOrigin: 'center',
                                }}
                            />
                        );
                    })}
                </svg>

                {/* Center content */}
                {centerContent && (
                    <div className="absolute inset-0 flex items-center justify-center">
                        {centerContent}
                    </div>
                )}
            </div>

            {/* Legend */}
            {showLegend && (
                <div className="space-y-2">
                    {data.map((item, index) => {
                        const color = item.color || defaultColors[index % defaultColors.length];
                        const percentage = ((item.value / total) * 100).toFixed(1);

                        return (
                            <motion.div
                                key={item.label}
                                initial={{ opacity: 0, x: -10 }}
                                animate={{ opacity: 1, x: 0 }}
                                transition={{ delay: 0.5 + index * 0.1 }}
                                className="flex items-center gap-2"
                            >
                                <div
                                    className="w-3 h-3 rounded-sm"
                                    style={{ backgroundColor: color }}
                                />
                                <span className="text-sm text-gray-300">{item.label}</span>
                                <span className="text-sm text-gray-500">{percentage}%</span>
                            </motion.div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

// ============================================================================
// Metric Comparison
// ============================================================================

export interface MetricComparisonProps {
    label: string;
    current: number;
    previous: number;
    format?: (value: number) => string;
    className?: string;
}

export function MetricComparison({
    label,
    current,
    previous,
    format = (v) => v.toLocaleString(),
    className,
}: MetricComparisonProps) {
    const change = previous !== 0 ? ((current - previous) / previous) * 100 : 0;
    const isPositive = change >= 0;

    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className={cn(
                'p-4 rounded-lg bg-gray-900/50 border border-white/5',
                className
            )}
        >
            <div className="text-sm text-gray-400 mb-1">{label}</div>
            <div className="flex items-end justify-between">
                <div className="text-2xl font-bold text-white">
                    {format(current)}
                </div>
                <div className={cn(
                    'flex items-center gap-1 text-sm font-medium',
                    isPositive ? 'text-green-500' : 'text-red-500'
                )}>
                    <span>{isPositive ? '↑' : '↓'}</span>
                    <span>{Math.abs(change).toFixed(1)}%</span>
                </div>
            </div>
            <div className="text-xs text-gray-500 mt-1">
                vs. previous: {format(previous)}
            </div>
        </motion.div>
    );
}

// ============================================================================
// Loading Skeleton for Charts
// ============================================================================

export interface ChartSkeletonProps {
    type?: 'bar' | 'line' | 'donut' | 'stat';
    className?: string;
}

export function ChartSkeleton({ type = 'bar', className }: ChartSkeletonProps) {
    return (
        <div className={cn('animate-pulse', className)}>
            {type === 'bar' && (
                <div className="flex items-end gap-2 h-40">
                    {[0.6, 0.8, 0.4, 0.9, 0.5, 0.7].map((height, i) => (
                        <div
                            key={i}
                            className="flex-1 bg-gray-800 rounded-t"
                            style={{ height: `${height * 100}%` }}
                        />
                    ))}
                </div>
            )}
            {type === 'line' && (
                <div className="h-40 bg-gradient-to-t from-gray-800 to-transparent rounded" />
            )}
            {type === 'donut' && (
                <div className="w-40 h-40 rounded-full border-[20px] border-gray-800" />
            )}
            {type === 'stat' && (
                <div className="space-y-3">
                    <div className="h-4 w-24 bg-gray-800 rounded" />
                    <div className="h-8 w-32 bg-gray-800 rounded" />
                </div>
            )}
        </div>
    );
}
