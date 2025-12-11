/**
 * Onboarding Tour Component
 * 
 * A premium guided tour system for new users with
 * spotlights, tooltips, and step-by-step navigation.
 */

import { createContext, useContext, useState, useEffect, useCallback, useMemo, useRef, ReactNode } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';
import { TRANSITION_DURATION, EASE_CURVE } from '@/components/ui/UnifiedTransitions';

// ============================================================================
// Types
// ============================================================================

export interface TourStep {
    id: string;
    target: string; // CSS selector
    title: string;
    content: ReactNode;
    placement?: 'top' | 'bottom' | 'left' | 'right';
    spotlightPadding?: number;
    action?: () => void;
    disableInteraction?: boolean;
    nextButtonText?: string;
    prevButtonText?: string;
    showSkip?: boolean;
}

export interface Tour {
    id: string;
    name: string;
    steps: TourStep[];
    onComplete?: () => void;
    onSkip?: () => void;
}

interface TourContextValue {
    activeTour: Tour | null;
    currentStep: number;
    isActive: boolean;
    startTour: (tour: Tour) => void;
    endTour: () => void;
    nextStep: () => void;
    prevStep: () => void;
    skipTour: () => void;
    goToStep: (index: number) => void;
}

// ============================================================================
// Context
// ============================================================================

const TourContext = createContext<TourContextValue | null>(null);

export function useTour() {
    const context = useContext(TourContext);
    if (!context) {
        throw new Error('useTour must be used within a TourProvider');
    }
    return context;
}

// ============================================================================
// Provider
// ============================================================================

interface TourProviderProps {
    children: ReactNode;
    onTourComplete?: (tourId: string) => void;
}

export function TourProvider({ children, onTourComplete }: TourProviderProps) {
    const [activeTour, setActiveTour] = useState<Tour | null>(null);
    const [currentStep, setCurrentStep] = useState(0);

    const startTour = useCallback((tour: Tour) => {
        setActiveTour(tour);
        setCurrentStep(0);
    }, []);

    const endTour = useCallback(() => {
        if (activeTour) {
            activeTour.onComplete?.();
            onTourComplete?.(activeTour.id);

            // Mark tour as completed in localStorage
            const completedTours = JSON.parse(localStorage.getItem('beatsight_completed_tours') || '[]');
            if (!completedTours.includes(activeTour.id)) {
                completedTours.push(activeTour.id);
                localStorage.setItem('beatsight_completed_tours', JSON.stringify(completedTours));
            }
        }
        setActiveTour(null);
        setCurrentStep(0);
    }, [activeTour, onTourComplete]);

    const skipTour = useCallback(() => {
        activeTour?.onSkip?.();
        setActiveTour(null);
        setCurrentStep(0);
    }, [activeTour]);

    const nextStep = useCallback(() => {
        if (!activeTour) return;

        const step = activeTour.steps[currentStep];
        step.action?.();

        if (currentStep < activeTour.steps.length - 1) {
            setCurrentStep(prev => prev + 1);
        } else {
            endTour();
        }
    }, [activeTour, currentStep, endTour]);

    const prevStep = useCallback(() => {
        if (currentStep > 0) {
            setCurrentStep(prev => prev - 1);
        }
    }, [currentStep]);

    const goToStep = useCallback((index: number) => {
        if (activeTour && index >= 0 && index < activeTour.steps.length) {
            setCurrentStep(index);
        }
    }, [activeTour]);

    const value = useMemo(() => ({
        activeTour,
        currentStep,
        isActive: activeTour !== null,
        startTour,
        endTour,
        nextStep,
        prevStep,
        skipTour,
        goToStep,
    }), [activeTour, currentStep, startTour, endTour, nextStep, prevStep, skipTour, goToStep]);

    return (
        <TourContext.Provider value={value}>
            {children}
            <TourOverlay />
        </TourContext.Provider>
    );
}

// ============================================================================
// Tour Overlay Component
// ============================================================================

function TourOverlay() {
    const { activeTour, currentStep, nextStep, prevStep, skipTour, isActive } = useTour();
    const [targetRect, setTargetRect] = useState<DOMRect | null>(null);
    const tooltipRef = useRef<HTMLDivElement>(null);

    const step = activeTour?.steps[currentStep];

    // Update target element position
    useEffect(() => {
        if (!step) {
            setTargetRect(null);
            return;
        }

        const updatePosition = () => {
            const element = document.querySelector(step.target);
            if (element) {
                setTargetRect(element.getBoundingClientRect());

                // Scroll element into view if needed
                element.scrollIntoView({ behavior: 'smooth', block: 'center' });
            } else {
                setTargetRect(null);
            }
        };

        updatePosition();

        // Update on scroll/resize
        window.addEventListener('scroll', updatePosition, true);
        window.addEventListener('resize', updatePosition);

        return () => {
            window.removeEventListener('scroll', updatePosition, true);
            window.removeEventListener('resize', updatePosition);
        };
    }, [step]);

    // Calculate tooltip position
    const getTooltipPosition = useCallback(() => {
        if (!targetRect || !step) return { top: '50%', left: '50%' };

        const padding = step.spotlightPadding ?? 8;
        const tooltipMargin = 16;
        const placement = step.placement ?? 'bottom';

        switch (placement) {
            case 'top':
                return {
                    top: targetRect.top - tooltipMargin,
                    left: targetRect.left + targetRect.width / 2,
                    transform: 'translate(-50%, -100%)',
                };
            case 'bottom':
                return {
                    top: targetRect.bottom + padding + tooltipMargin,
                    left: targetRect.left + targetRect.width / 2,
                    transform: 'translate(-50%, 0)',
                };
            case 'left':
                return {
                    top: targetRect.top + targetRect.height / 2,
                    left: targetRect.left - tooltipMargin,
                    transform: 'translate(-100%, -50%)',
                };
            case 'right':
                return {
                    top: targetRect.top + targetRect.height / 2,
                    left: targetRect.right + padding + tooltipMargin,
                    transform: 'translate(0, -50%)',
                };
            default:
                return {
                    top: targetRect.bottom + padding + tooltipMargin,
                    left: targetRect.left + targetRect.width / 2,
                    transform: 'translate(-50%, 0)',
                };
        }
    }, [targetRect, step]);

    if (!isActive || !activeTour || !step) return null;

    const padding = step.spotlightPadding ?? 8;
    const isLastStep = currentStep === activeTour.steps.length - 1;
    const isFirstStep = currentStep === 0;

    return (
        <AnimatePresence>
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 z-[9998]"
            >
                {/* Backdrop with spotlight cutout */}
                <svg className="absolute inset-0 w-full h-full">
                    <defs>
                        <mask id="spotlight-mask">
                            <rect width="100%" height="100%" fill="white" />
                            {targetRect && (
                                <motion.rect
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    x={targetRect.left - padding}
                                    y={targetRect.top - padding}
                                    width={targetRect.width + padding * 2}
                                    height={targetRect.height + padding * 2}
                                    rx={8}
                                    fill="black"
                                />
                            )}
                        </mask>
                    </defs>
                    <rect
                        width="100%"
                        height="100%"
                        fill="rgba(0, 0, 0, 0.75)"
                        mask="url(#spotlight-mask)"
                    />
                </svg>

                {/* Spotlight border glow */}
                {targetRect && (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ duration: TRANSITION_DURATION, ease: EASE_CURVE }}
                        className="absolute pointer-events-none"
                        style={{
                            top: targetRect.top - padding,
                            left: targetRect.left - padding,
                            width: targetRect.width + padding * 2,
                            height: targetRect.height + padding * 2,
                            borderRadius: 8,
                            boxShadow: '0 0 0 2px rgba(0, 212, 255, 0.5), 0 0 20px rgba(0, 212, 255, 0.3)',
                        }}
                    />
                )}

                {/* Tooltip */}
                <motion.div
                    ref={tooltipRef}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 10 }}
                    className={cn(
                        'fixed z-[9999] w-80',
                        'bg-dark-500 border border-white/10 rounded-xl',
                        'shadow-2xl shadow-black/50',
                    )}
                    style={getTooltipPosition()}
                >
                    {/* Progress indicator */}
                    <div className="px-4 pt-4">
                        <div className="flex items-center gap-1 mb-3">
                            {activeTour.steps.map((_, index) => (
                                <div
                                    key={index}
                                    className={cn(
                                        'h-1 flex-1 rounded-full transition-colors',
                                        index <= currentStep ? 'bg-primary-500' : 'bg-dark-300'
                                    )}
                                />
                            ))}
                        </div>
                    </div>

                    {/* Content */}
                    <div className="px-4 pb-2">
                        <h3 className="text-lg font-semibold text-white mb-2">
                            {step.title}
                        </h3>
                        <div className="text-sm text-gray-300">
                            {step.content}
                        </div>
                    </div>

                    {/* Actions */}
                    <div className="px-4 pb-4 pt-2 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            {step.showSkip !== false && (
                                <button
                                    onClick={skipTour}
                                    className="text-sm text-gray-500 hover:text-gray-300 transition-colors"
                                >
                                    Skip tour
                                </button>
                            )}
                        </div>

                        <div className="flex items-center gap-2">
                            {!isFirstStep && (
                                <button
                                    onClick={prevStep}
                                    className={cn(
                                        'px-3 py-1.5 text-sm font-medium rounded-lg',
                                        'text-gray-300 hover:text-white hover:bg-dark-400',
                                        'transition-colors'
                                    )}
                                >
                                    {step.prevButtonText ?? 'Back'}
                                </button>
                            )}

                            <button
                                onClick={nextStep}
                                className={cn(
                                    'px-4 py-1.5 text-sm font-medium rounded-lg',
                                    'bg-primary-500 text-white hover:bg-primary-400',
                                    'transition-colors'
                                )}
                            >
                                {step.nextButtonText ?? (isLastStep ? 'Finish' : 'Next')}
                            </button>
                        </div>
                    </div>
                </motion.div>
            </motion.div>
        </AnimatePresence>
    );
}

// ============================================================================
// Pre-built Tours
// ============================================================================

export const welcomeTour: Tour = {
    id: 'welcome',
    name: 'Welcome to BeatSight',
    steps: [
        {
            id: 'welcome-1',
            target: '[data-tour="upload-button"]',
            title: 'Upload Any Audio',
            content: 'Upload any audio with drums—songs, band rehearsals, original tracks, or isolated drums. We support MP3, WAV, FLAC, and more.',
            placement: 'bottom',
        },
        {
            id: 'welcome-2',
            target: '[data-tour="library"]',
            title: 'Your Audio Library',
            content: 'All your uploaded audio appears here. Click any track to start creating a beatmap.',
            placement: 'right',
        },
        {
            id: 'welcome-3',
            target: '[data-tour="ai-transcribe"]',
            title: 'Create Beatmaps',
            content: 'Build beatmaps from scratch, use AI-assisted transcription as a starting point, or polish existing maps. Your refinements help improve the community library.',
            placement: 'bottom',
        },
        {
            id: 'welcome-4',
            target: '[data-tour="editor"]',
            title: 'The Editor',
            content: 'Fine-tune your beatmaps with our powerful editor. Adjust timing, add notes, and perfect your creation.',
            placement: 'left',
        },
        {
            id: 'welcome-5',
            target: '[data-tour="credits"]',
            title: 'Credits System',
            content: 'AI-assisted transcription uses credits. You get free credits to start, and can purchase more anytime. Manual creation is always free.',
            placement: 'bottom',
            nextButtonText: 'Get Started!',
        },
    ],
};

export const editorTour: Tour = {
    id: 'editor',
    name: 'Editor Tutorial',
    steps: [
        {
            id: 'editor-1',
            target: '[data-tour="timeline"]',
            title: 'The Timeline',
            content: 'This is your timeline. Drag to scroll, scroll to zoom. Notes appear as colored blocks.',
            placement: 'top',
        },
        {
            id: 'editor-2',
            target: '[data-tour="waveform"]',
            title: 'Waveform Display',
            content: 'The waveform shows your audio visually. Use it to align notes precisely with the music.',
            placement: 'top',
        },
        {
            id: 'editor-3',
            target: '[data-tour="note-tools"]',
            title: 'Note Tools',
            content: 'Select different note types here. Each instrument has its own lane.',
            placement: 'right',
        },
        {
            id: 'editor-4',
            target: '[data-tour="playback"]',
            title: 'Playback Controls',
            content: 'Play, pause, and navigate your beatmap. Use keyboard shortcuts for faster editing.',
            placement: 'top',
        },
        {
            id: 'editor-5',
            target: '[data-tour="save"]',
            title: 'Save Your Work',
            content: 'Don\'t forget to save! Your beatmaps are automatically backed up to the cloud.',
            placement: 'bottom',
            nextButtonText: 'Start Creating!',
        },
    ],
};

// ============================================================================
// Hook to check if tour is completed
// ============================================================================

export function useTourStatus(tourId: string) {
    const [isCompleted, setIsCompleted] = useState(false);

    useEffect(() => {
        const completedTours = JSON.parse(localStorage.getItem('beatsight_completed_tours') || '[]');
        setIsCompleted(completedTours.includes(tourId));
    }, [tourId]);

    const reset = useCallback(() => {
        const completedTours = JSON.parse(localStorage.getItem('beatsight_completed_tours') || '[]');
        const filtered = completedTours.filter((id: string) => id !== tourId);
        localStorage.setItem('beatsight_completed_tours', JSON.stringify(filtered));
        setIsCompleted(false);
    }, [tourId]);

    return { isCompleted, reset };
}
