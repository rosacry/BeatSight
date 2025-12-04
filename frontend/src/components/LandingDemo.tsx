/**
 * Animated demo component for the landing page.
 * Shows a visual representation of the AI workflow
 * without requiring an actual video.
 */

import { useState, useEffect } from 'react'
import { cn } from '@/lib/utils'

interface DemoStep {
    id: number
    label: string
    icon: 'upload' | 'process' | 'beatmap' | 'play'
    duration: number // ms
}

const DEMO_STEPS: DemoStep[] = [
    { id: 1, label: 'Upload Audio', icon: 'upload', duration: 2000 },
    { id: 2, label: 'AI Processing', icon: 'process', duration: 3000 },
    { id: 3, label: 'Generate Beatmap', icon: 'beatmap', duration: 2000 },
    { id: 4, label: 'Practice & Learn', icon: 'play', duration: 2500 },
]

const ICONS = {
    upload: (
        <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
    ),
    process: (
        <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
        </svg>
    ),
    beatmap: (
        <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
        </svg>
    ),
    play: (
        <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
    ),
}

// Animated waveform visualization
function WaveformAnimation({ isActive }: { isActive: boolean }) {
    return (
        <div className="flex items-center justify-center gap-1 h-12">
            {[...Array(12)].map((_, i) => (
                <div
                    key={i}
                    className={cn(
                        'w-1 bg-purple-500 rounded-full transition-all duration-300',
                        isActive ? 'animate-pulse' : 'h-2'
                    )}
                    style={{
                        height: isActive ? `${20 + Math.sin(i * 0.5) * 15 + Math.random() * 10}px` : '8px',
                        animationDelay: `${i * 100}ms`,
                    }}
                />
            ))}
        </div>
    )
}

// Animated beatmap visualization
function BeatmapAnimation({ isActive }: { isActive: boolean }) {
    const [notes, setNotes] = useState<number[]>([])

    useEffect(() => {
        if (!isActive) {
            setNotes([])
            return
        }

        const interval = setInterval(() => {
            setNotes(prev => {
                const newNotes = prev.filter(n => n > -100).map(n => n - 20)
                if (Math.random() > 0.5) {
                    newNotes.push(200)
                }
                return newNotes
            })
        }, 150)

        return () => clearInterval(interval)
    }, [isActive])

    return (
        <div className="relative h-16 w-full overflow-hidden rounded bg-gray-900/50">
            {/* Timeline lanes */}
            <div className="absolute inset-0 flex flex-col justify-around">
                {[0, 1, 2].map(lane => (
                    <div key={lane} className="h-px bg-gray-700" />
                ))}
            </div>
            {/* Moving notes */}
            {notes.map((pos, i) => (
                <div
                    key={i}
                    className="absolute w-3 h-3 bg-purple-500 rounded-full transition-transform"
                    style={{
                        left: `${pos}px`,
                        top: `${10 + (i % 3) * 20}px`,
                    }}
                />
            ))}
            {/* Playhead */}
            <div className="absolute left-8 top-0 bottom-0 w-0.5 bg-white/50" />
        </div>
    )
}

export function LandingDemo() {
    const [currentStep, setCurrentStep] = useState(0)
    const [progress, setProgress] = useState(0)
    const [isPlaying, setIsPlaying] = useState(true)

    useEffect(() => {
        if (!isPlaying) return

        const step = DEMO_STEPS[currentStep]
        const progressInterval = setInterval(() => {
            setProgress(prev => {
                if (prev >= 100) {
                    // Move to next step
                    setCurrentStep(current => (current + 1) % DEMO_STEPS.length)
                    return 0
                }
                return prev + (100 / (step.duration / 50))
            })
        }, 50)

        return () => clearInterval(progressInterval)
    }, [currentStep, isPlaying])

    const currentStepData = DEMO_STEPS[currentStep]

    return (
        <div
            className="aspect-video bg-gray-900 rounded-2xl border border-gray-700 overflow-hidden relative cursor-pointer group"
            onClick={() => setIsPlaying(!isPlaying)}
        >
            {/* Background gradient */}
            <div className="absolute inset-0 bg-gradient-to-br from-purple-900/20 to-blue-900/20" />

            {/* Main content */}
            <div className="absolute inset-0 flex flex-col items-center justify-center p-6">
                {/* Step indicator */}
                <div className="flex items-center gap-2 mb-6">
                    {DEMO_STEPS.map((step, idx) => (
                        <div
                            key={step.id}
                            className={cn(
                                'w-2 h-2 rounded-full transition-all duration-300',
                                idx === currentStep
                                    ? 'w-8 bg-purple-500'
                                    : idx < currentStep
                                        ? 'bg-purple-400'
                                        : 'bg-gray-600'
                            )}
                        />
                    ))}
                </div>

                {/* Icon */}
                <div className={cn(
                    'w-20 h-20 rounded-2xl flex items-center justify-center mb-4 transition-all duration-500',
                    currentStep === 1 ? 'bg-yellow-500/20 text-yellow-400 animate-pulse' :
                        currentStep === 3 ? 'bg-green-500/20 text-green-400' :
                            'bg-purple-500/20 text-purple-400'
                )}>
                    {ICONS[currentStepData.icon]}
                </div>

                {/* Label */}
                <p className="text-white font-medium text-lg mb-6">
                    {currentStepData.label}
                </p>

                {/* Visualization */}
                <div className="w-full max-w-xs">
                    {currentStep === 1 && <WaveformAnimation isActive={true} />}
                    {(currentStep === 2 || currentStep === 3) && <BeatmapAnimation isActive={true} />}
                    {currentStep === 0 && (
                        <div className="h-12 border-2 border-dashed border-gray-600 rounded-lg flex items-center justify-center text-gray-500 text-sm">
                            Drop audio file here
                        </div>
                    )}
                </div>

                {/* Progress bar */}
                <div className="absolute bottom-4 left-4 right-4">
                    <div className="h-1 bg-gray-700 rounded-full overflow-hidden">
                        <div
                            className="h-full bg-purple-500 transition-all duration-100 ease-linear"
                            style={{ width: `${progress}%` }}
                        />
                    </div>
                </div>
            </div>

            {/* Play/Pause overlay on hover */}
            <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                <div className="w-16 h-16 rounded-full bg-white/10 flex items-center justify-center">
                    {isPlaying ? (
                        <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
                        </svg>
                    ) : (
                        <svg className="w-8 h-8 text-white ml-1" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M8 5v14l11-7z" />
                        </svg>
                    )}
                </div>
            </div>
        </div>
    )
}
