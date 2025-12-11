/**
 * Advanced Slider components with range support, marks, and visual feedback.
 */

import {
    forwardRef,
    useState,
    useCallback,
    useRef,
    useEffect,
    type HTMLAttributes,
} from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { clsx } from 'clsx'

// ============================================================================
// SLIDER
// ============================================================================

const sliderVariants = cva(
    'relative w-full touch-none select-none',
    {
        variants: {
            size: {
                sm: 'h-4',
                md: 'h-5',
                lg: 'h-6',
            },
        },
        defaultVariants: {
            size: 'md',
        },
    }
)

const trackVariants = cva(
    'absolute rounded-full bg-dark-300',
    {
        variants: {
            size: {
                sm: 'h-1 top-1.5',
                md: 'h-1.5 top-[7px]',
                lg: 'h-2 top-2',
            },
        },
        defaultVariants: {
            size: 'md',
        },
    }
)

const rangeVariants = cva(
    'absolute rounded-full',
    {
        variants: {
            size: {
                sm: 'h-1 top-1.5',
                md: 'h-1.5 top-[7px]',
                lg: 'h-2 top-2',
            },
            color: {
                primary: 'bg-gradient-to-r from-primary-500 to-primary-400',
                accent: 'bg-gradient-to-r from-accent-500 to-pink-500',
                success: 'bg-gradient-to-r from-green-500 to-emerald-400',
                warning: 'bg-gradient-to-r from-yellow-500 to-orange-400',
            },
        },
        defaultVariants: {
            size: 'md',
            color: 'primary',
        },
    }
)

const thumbVariants = cva(
    [
        'absolute rounded-full bg-white border-2',
        'shadow-lg cursor-grab active:cursor-grabbing',
        'transition-transform duration-100',
        'hover:scale-110 focus:scale-110 focus:outline-none',
        'focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-900',
    ],
    {
        variants: {
            size: {
                sm: 'w-3 h-3 -translate-x-1.5 top-0.5',
                md: 'w-4 h-4 -translate-x-2 top-0.5',
                lg: 'w-5 h-5 -translate-x-2.5 top-0.5',
            },
            color: {
                primary: 'border-primary-500 focus-visible:ring-primary-500',
                accent: 'border-accent-500 focus-visible:ring-accent-500',
                success: 'border-green-500 focus-visible:ring-green-500',
                warning: 'border-yellow-500 focus-visible:ring-yellow-500',
            },
        },
        defaultVariants: {
            size: 'md',
            color: 'primary',
        },
    }
)

interface Mark {
    value: number
    label?: string
}

export interface SliderProps
    extends Omit<HTMLAttributes<HTMLDivElement>, 'onChange'>,
    VariantProps<typeof sliderVariants> {
    /** Current value */
    value?: number
    /** Default value (uncontrolled) */
    defaultValue?: number
    /** Minimum value */
    min?: number
    /** Maximum value */
    max?: number
    /** Step increment */
    step?: number
    /** Marks to display */
    marks?: Mark[]
    /** Show current value tooltip */
    showTooltip?: boolean
    /** Color variant */
    color?: 'primary' | 'accent' | 'success' | 'warning'
    /** Disabled state */
    disabled?: boolean
    /** Change handler */
    onChange?: (value: number) => void
    /** Format value for display */
    formatValue?: (value: number) => string
}

export const Slider = forwardRef<HTMLDivElement, SliderProps>(
    (
        {
            className,
            size,
            value: controlledValue,
            defaultValue = 0,
            min = 0,
            max = 100,
            step = 1,
            marks,
            showTooltip = false,
            color = 'primary',
            disabled = false,
            onChange,
            formatValue = (v) => v.toString(),
            ...props
        },
        ref
    ) => {
        const [internalValue, setInternalValue] = useState(defaultValue)
        const [isDragging, setIsDragging] = useState(false)
        const [showTooltipState, setShowTooltipState] = useState(false)
        const trackRef = useRef<HTMLDivElement>(null)

        const value = controlledValue ?? internalValue
        const percentage = ((value - min) / (max - min)) * 100

        const updateValue = useCallback(
            (clientX: number) => {
                if (!trackRef.current || disabled) return

                const rect = trackRef.current.getBoundingClientRect()
                const percent = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width))
                const rawValue = min + percent * (max - min)
                const steppedValue = Math.round(rawValue / step) * step
                const clampedValue = Math.max(min, Math.min(max, steppedValue))

                setInternalValue(clampedValue)
                onChange?.(clampedValue)
            },
            [min, max, step, disabled, onChange]
        )

        const handleMouseDown = useCallback(
            (e: React.MouseEvent) => {
                if (disabled) return
                setIsDragging(true)
                updateValue(e.clientX)
            },
            [disabled, updateValue]
        )

        useEffect(() => {
            if (!isDragging) return

            const handleMouseMove = (e: MouseEvent) => updateValue(e.clientX)
            const handleMouseUp = () => setIsDragging(false)

            document.addEventListener('mousemove', handleMouseMove)
            document.addEventListener('mouseup', handleMouseUp)

            return () => {
                document.removeEventListener('mousemove', handleMouseMove)
                document.removeEventListener('mouseup', handleMouseUp)
            }
        }, [isDragging, updateValue])

        return (
            <div
                ref={ref}
                className={clsx(
                    sliderVariants({ size }),
                    disabled && 'opacity-50 cursor-not-allowed',
                    className
                )}
                {...props}
            >
                {/* Track */}
                <div
                    ref={trackRef}
                    className={clsx(trackVariants({ size }), 'left-0 right-0')}
                    onMouseDown={handleMouseDown}
                />

                {/* Filled Range */}
                <div
                    className={clsx(rangeVariants({ size, color }))}
                    style={{ left: 0, width: `${percentage}%` }}
                />

                {/* Marks */}
                {marks?.map((mark) => {
                    const markPercent = ((mark.value - min) / (max - min)) * 100
                    return (
                        <div key={mark.value} className="absolute" style={{ left: `${markPercent}%` }}>
                            <div
                                className={clsx(
                                    'w-1 h-1 rounded-full bg-gray-500 -translate-x-0.5',
                                    size === 'sm' && 'top-1.5',
                                    size === 'md' && 'top-[7px]',
                                    size === 'lg' && 'top-2'
                                )}
                            />
                            {mark.label && (
                                <span className="absolute top-4 -translate-x-1/2 text-xs text-gray-400 whitespace-nowrap">
                                    {mark.label}
                                </span>
                            )}
                        </div>
                    )
                })}

                {/* Thumb */}
                <div
                    className={clsx(thumbVariants({ size, color }))}
                    style={{ left: `${percentage}%` }}
                    onMouseDown={handleMouseDown}
                    onMouseEnter={() => showTooltip && setShowTooltipState(true)}
                    onMouseLeave={() => !isDragging && setShowTooltipState(false)}
                    tabIndex={disabled ? -1 : 0}
                    role="slider"
                    aria-valuemin={min}
                    aria-valuemax={max}
                    aria-valuenow={value}
                    aria-disabled={disabled}
                />

                {/* Tooltip */}
                {showTooltip && (showTooltipState || isDragging) && (
                    <div
                        className="absolute -top-8 px-2 py-1 bg-dark-400 rounded text-xs text-white shadow-lg -translate-x-1/2 pointer-events-none"
                        style={{ left: `${percentage}%` }}
                    >
                        {formatValue(value)}
                    </div>
                )}
            </div>
        )
    }
)

Slider.displayName = 'Slider'

// ============================================================================
// RANGE SLIDER (Two Thumbs)
// ============================================================================

export interface RangeSliderProps
    extends Omit<HTMLAttributes<HTMLDivElement>, 'onChange' | 'defaultValue'>,
    VariantProps<typeof sliderVariants> {
    /** Current value [min, max] */
    value?: [number, number]
    /** Default value (uncontrolled) */
    defaultValue?: [number, number]
    /** Minimum value */
    min?: number
    /** Maximum value */
    max?: number
    /** Step increment */
    step?: number
    /** Minimum gap between handles */
    minGap?: number
    /** Color variant */
    color?: 'primary' | 'accent' | 'success' | 'warning'
    /** Disabled state */
    disabled?: boolean
    /** Change handler */
    onChange?: (value: [number, number]) => void
    /** Format value for display */
    formatValue?: (value: number) => string
}

export const RangeSlider = forwardRef<HTMLDivElement, RangeSliderProps>(
    (
        {
            className,
            size,
            value: controlledValue,
            defaultValue = [25, 75],
            min = 0,
            max = 100,
            step = 1,
            minGap = 0,
            color = 'primary',
            disabled = false,
            onChange,
            formatValue = (v) => v.toString(),
            ...props
        },
        ref
    ) => {
        const [internalValue, setInternalValue] = useState(defaultValue)
        const [activeThumb, setActiveThumb] = useState<0 | 1 | null>(null)
        const trackRef = useRef<HTMLDivElement>(null)

        const value = controlledValue ?? internalValue
        const [lowValue, highValue] = value
        const lowPercent = ((lowValue - min) / (max - min)) * 100
        const highPercent = ((highValue - min) / (max - min)) * 100

        const updateValue = useCallback(
            (clientX: number, thumbIndex: 0 | 1) => {
                if (!trackRef.current || disabled) return

                const rect = trackRef.current.getBoundingClientRect()
                const percent = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width))
                const rawValue = min + percent * (max - min)
                const steppedValue = Math.round(rawValue / step) * step

                const newValue: [number, number] = [...value] as [number, number]

                if (thumbIndex === 0) {
                    newValue[0] = Math.min(steppedValue, highValue - minGap)
                    newValue[0] = Math.max(min, newValue[0])
                } else {
                    newValue[1] = Math.max(steppedValue, lowValue + minGap)
                    newValue[1] = Math.min(max, newValue[1])
                }

                setInternalValue(newValue)
                onChange?.(newValue)
            },
            [min, max, step, minGap, value, lowValue, highValue, disabled, onChange]
        )

        useEffect(() => {
            if (activeThumb === null) return

            const handleMouseMove = (e: MouseEvent) => updateValue(e.clientX, activeThumb)
            const handleMouseUp = () => setActiveThumb(null)

            document.addEventListener('mousemove', handleMouseMove)
            document.addEventListener('mouseup', handleMouseUp)

            return () => {
                document.removeEventListener('mousemove', handleMouseMove)
                document.removeEventListener('mouseup', handleMouseUp)
            }
        }, [activeThumb, updateValue])

        return (
            <div
                ref={ref}
                className={clsx(
                    sliderVariants({ size }),
                    disabled && 'opacity-50 cursor-not-allowed',
                    className
                )}
                {...props}
            >
                {/* Track */}
                <div ref={trackRef} className={clsx(trackVariants({ size }), 'left-0 right-0')} />

                {/* Filled Range */}
                <div
                    className={clsx(rangeVariants({ size, color }))}
                    style={{ left: `${lowPercent}%`, width: `${highPercent - lowPercent}%` }}
                />

                {/* Low Thumb */}
                <div
                    className={clsx(thumbVariants({ size, color }), activeThumb === 0 && 'scale-110')}
                    style={{ left: `${lowPercent}%` }}
                    onMouseDown={() => !disabled && setActiveThumb(0)}
                    tabIndex={disabled ? -1 : 0}
                    role="slider"
                    aria-label="Minimum value"
                    aria-valuemin={min}
                    aria-valuemax={highValue - minGap}
                    aria-valuenow={lowValue}
                />

                {/* High Thumb */}
                <div
                    className={clsx(thumbVariants({ size, color }), activeThumb === 1 && 'scale-110')}
                    style={{ left: `${highPercent}%` }}
                    onMouseDown={() => !disabled && setActiveThumb(1)}
                    tabIndex={disabled ? -1 : 0}
                    role="slider"
                    aria-label="Maximum value"
                    aria-valuemin={lowValue + minGap}
                    aria-valuemax={max}
                    aria-valuenow={highValue}
                />

                {/* Value Labels */}
                <div className="flex justify-between mt-2 text-xs text-gray-400">
                    <span>{formatValue(lowValue)}</span>
                    <span>{formatValue(highValue)}</span>
                </div>
            </div>
        )
    }
)

RangeSlider.displayName = 'RangeSlider'

// ============================================================================
// VOLUME SLIDER (Vertical with Icon)
// ============================================================================

export interface VolumeSliderProps extends Omit<SliderProps, 'size'> {
    /** Show mute button */
    showMute?: boolean
    /** Muted state */
    muted?: boolean
    /** Mute toggle handler */
    onMuteToggle?: (muted: boolean) => void
}

export const VolumeSlider = forwardRef<HTMLDivElement, VolumeSliderProps>(
    ({ value = 50, showMute = true, muted = false, onMuteToggle, onChange, className, ...props }, ref) => {
        const [previousValue, setPreviousValue] = useState(value)

        const handleMuteToggle = () => {
            if (muted) {
                onChange?.(previousValue)
            } else {
                setPreviousValue(value)
                onChange?.(0)
            }
            onMuteToggle?.(!muted)
        }

        const VolumeIcon = () => {
            if (muted || value === 0) {
                return (
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" />
                    </svg>
                )
            }
            if (value < 50) {
                return (
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                    </svg>
                )
            }
            return (
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                </svg>
            )
        }

        return (
            <div ref={ref} className={clsx('flex items-center gap-3', className)} {...props}>
                {showMute && (
                    <button
                        type="button"
                        onClick={handleMuteToggle}
                        className="text-gray-400 hover:text-white transition-colors"
                        aria-label={muted ? 'Unmute' : 'Mute'}
                    >
                        <VolumeIcon />
                    </button>
                )}
                <Slider
                    value={muted ? 0 : value}
                    onChange={onChange}
                    min={0}
                    max={100}
                    color="primary"
                    className="flex-1"
                    {...props}
                />
            </div>
        )
    }
)

VolumeSlider.displayName = 'VolumeSlider'
