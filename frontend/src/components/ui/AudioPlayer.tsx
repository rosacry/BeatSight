// Copyright (c) BeatSight. Licensed under the MIT Licence.
// See the LICENCE file in the repository root for full licence text.

import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '../../lib/utils';

// AudioPlayer variants
const audioPlayerVariants = cva('relative rounded-xl border transition-all', {
    variants: {
        variant: {
            default: 'bg-dark-500/80 border-white/10 backdrop-blur-sm',
            minimal: 'bg-transparent border-transparent',
            card: 'bg-dark-400 border-white/10 shadow-xl',
        },
        size: {
            sm: 'p-3',
            md: 'p-4',
            lg: 'p-6',
        },
    },
    defaultVariants: {
        variant: 'default',
        size: 'md',
    },
});

// Icons
const PlayIcon: React.FC<{ className?: string }> = ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
        <path d="M8 5v14l11-7z" />
    </svg>
);

const PauseIcon: React.FC<{ className?: string }> = ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
        <rect x="6" y="4" width="4" height="16" rx="1" />
        <rect x="14" y="4" width="4" height="16" rx="1" />
    </svg>
);

const SkipBackIcon: React.FC<{ className?: string }> = ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
        <polygon points="19,20 9,12 19,4" />
        <line x1="5" y1="19" x2="5" y2="5" stroke="currentColor" strokeWidth="2" />
    </svg>
);

const SkipForwardIcon: React.FC<{ className?: string }> = ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
        <polygon points="5,4 15,12 5,20" />
        <line x1="19" y1="5" x2="19" y2="19" stroke="currentColor" strokeWidth="2" />
    </svg>
);

const VolumeIcon: React.FC<{ className?: string; muted?: boolean; level?: number }> = ({
    className,
    muted,
    level = 1,
}) => {
    if (muted || level === 0) {
        return (
            <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polygon points="11,5 6,9 2,9 2,15 6,15 11,19" fill="currentColor" />
                <line x1="23" y1="9" x2="17" y2="15" strokeLinecap="round" />
                <line x1="17" y1="9" x2="23" y2="15" strokeLinecap="round" />
            </svg>
        );
    }
    return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polygon points="11,5 6,9 2,9 2,15 6,15 11,19" fill="currentColor" />
            {level > 0.3 && <path d="M15.54,8.46a5,5,0,0,1,0,7.07" strokeLinecap="round" />}
            {level > 0.6 && <path d="M19.07,4.93a10,10,0,0,1,0,14.14" strokeLinecap="round" />}
        </svg>
    );
};

const RepeatIcon: React.FC<{ className?: string; mode?: 'off' | 'all' | 'one' }> = ({ className, mode = 'off' }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <polyline points="17,1 21,5 17,9" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M3,11V9a4,4,0,0,1,4-4h14" strokeLinecap="round" strokeLinejoin="round" />
        <polyline points="7,23 3,19 7,15" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M21,13v2a4,4,0,0,1-4,4H3" strokeLinecap="round" strokeLinejoin="round" />
        {mode === 'one' && (
            <text x="10" y="15" fontSize="8" fill="currentColor" fontWeight="bold">
                1
            </text>
        )}
    </svg>
);

const ShuffleIcon: React.FC<{ className?: string }> = ({ className }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <polyline points="16,3 21,3 21,8" strokeLinecap="round" strokeLinejoin="round" />
        <line x1="4" y1="20" x2="21" y2="3" strokeLinecap="round" />
        <polyline points="21,16 21,21 16,21" strokeLinecap="round" strokeLinejoin="round" />
        <line x1="15" y1="15" x2="21" y2="21" strokeLinecap="round" />
        <line x1="4" y1="4" x2="9" y2="9" strokeLinecap="round" />
    </svg>
);

// DownloadIcon - may be used in future for download functionality
// const DownloadIcon: React.FC<{ className?: string }> = ({ className }) => (
//   <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
//     <path d="M21,15v4a2,2,0,0,1-2,2H5a2,2,0,0,1-2-2v-4" strokeLinecap="round" strokeLinejoin="round" />
//     <polyline points="7,10 12,15 17,10" strokeLinecap="round" strokeLinejoin="round" />
//     <line x1="12" y1="15" x2="12" y2="3" strokeLinecap="round" />
//   </svg>
// );

// Types
export interface AudioTrack {
    id: string;
    title: string;
    artist?: string;
    album?: string;
    coverUrl?: string;
    audioUrl: string;
    duration?: number;
}

export interface AudioPlayerProps extends VariantProps<typeof audioPlayerVariants> {
    /** Audio track to play */
    track?: AudioTrack;
    /** Whether player is in compact mode */
    compact?: boolean;
    /** Show waveform visualization */
    showWaveform?: boolean;
    /** Show playback controls */
    showControls?: boolean;
    /** Show volume control */
    showVolume?: boolean;
    /** Show extra controls (shuffle, repeat) */
    showExtras?: boolean;
    /** Auto play when track changes */
    autoPlay?: boolean;
    /** Callback when track ends */
    onEnded?: () => void;
    /** Callback when playback state changes */
    onPlayStateChange?: (isPlaying: boolean) => void;
    /** Callback for skip next */
    onSkipNext?: () => void;
    /** Callback for skip previous */
    onSkipPrevious?: () => void;
    /** Additional class names */
    className?: string;
}

// Helper functions
const formatTime = (seconds: number): string => {
    if (!isFinite(seconds) || isNaN(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
};

/**
 * ProgressBar - Audio progress/seek bar
 */
interface ProgressBarProps {
    current: number;
    total: number;
    onSeek?: (time: number) => void;
    buffered?: number;
    className?: string;
}

const ProgressBar: React.FC<ProgressBarProps> = ({ current, total, onSeek, buffered = 0, className }) => {
    const progressRef = React.useRef<HTMLDivElement>(null);
    const [hoverPosition, setHoverPosition] = React.useState<number | null>(null);

    const calculatePosition = (clientX: number): number => {
        if (!progressRef.current) return 0;
        const rect = progressRef.current.getBoundingClientRect();
        const position = (clientX - rect.left) / rect.width;
        return Math.max(0, Math.min(1, position));
    };

    const handleClick = (e: React.MouseEvent) => {
        const position = calculatePosition(e.clientX);
        onSeek?.(position * total);
    };

    const handleMouseMove = (e: React.MouseEvent) => {
        const position = calculatePosition(e.clientX);
        setHoverPosition(position);
    };

    const handleMouseLeave = () => {
        setHoverPosition(null);
    };

    const progress = total > 0 ? (current / total) * 100 : 0;
    const bufferedProgress = total > 0 ? (buffered / total) * 100 : 0;

    return (
        <div className={cn('relative group', className)}>
            {/* Time display on hover */}
            {hoverPosition !== null && (
                <div
                    className="absolute -top-8 px-2 py-1 bg-dark-500 text-xs text-white rounded transform -translate-x-1/2 pointer-events-none"
                    style={{ left: `${hoverPosition * 100}%` }}
                >
                    {formatTime(hoverPosition * total)}
                </div>
            )}

            <div
                ref={progressRef}
                className="h-2 bg-dark-300 rounded-full cursor-pointer overflow-hidden"
                onClick={handleClick}
                onMouseMove={handleMouseMove}
                onMouseLeave={handleMouseLeave}
            >
                {/* Buffered indicator */}
                <div
                    className="absolute h-full bg-gray-600 rounded-full transition-all"
                    style={{ width: `${bufferedProgress}%` }}
                />

                {/* Progress indicator */}
                <div
                    className="h-full bg-gradient-to-r from-primary to-accent rounded-full transition-all relative"
                    style={{ width: `${progress}%` }}
                >
                    {/* Thumb */}
                    <div
                        className={cn(
                            'absolute right-0 top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full shadow-lg',
                            'opacity-0 group-hover:opacity-100 transition-opacity'
                        )}
                    />
                </div>
            </div>
        </div>
    );
};

/**
 * VolumeSlider - Volume control slider
 */
interface VolumeSliderProps {
    volume: number;
    muted: boolean;
    onVolumeChange: (volume: number) => void;
    onMuteToggle: () => void;
}

const VolumeSlider: React.FC<VolumeSliderProps> = ({ volume, muted, onVolumeChange, onMuteToggle }) => {
    const [isExpanded, setIsExpanded] = React.useState(false);

    return (
        <div
            className="flex items-center gap-2"
            onMouseEnter={() => setIsExpanded(true)}
            onMouseLeave={() => setIsExpanded(false)}
        >
            <button
                onClick={onMuteToggle}
                className="p-2 rounded-full hover:bg-dark-300 transition-colors"
                aria-label={muted ? 'Unmute' : 'Mute'}
            >
                <VolumeIcon className="w-5 h-5 text-gray-300" muted={muted} level={volume} />
            </button>

            <div
                className={cn(
                    'overflow-hidden transition-all duration-200',
                    isExpanded ? 'w-24 opacity-100' : 'w-0 opacity-0'
                )}
            >
                <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.01"
                    value={muted ? 0 : volume}
                    onChange={(e) => onVolumeChange(parseFloat(e.target.value))}
                    className="w-full h-1 bg-dark-300 rounded-full appearance-none cursor-pointer
                     [&::-webkit-slider-thumb]:appearance-none
                     [&::-webkit-slider-thumb]:w-3
                     [&::-webkit-slider-thumb]:h-3
                     [&::-webkit-slider-thumb]:rounded-full
                     [&::-webkit-slider-thumb]:bg-white
                     [&::-webkit-slider-thumb]:cursor-pointer"
                />
            </div>
        </div>
    );
};

/**
 * TrackInfo - Track artwork and info display
 */
interface TrackInfoProps {
    track?: AudioTrack;
    compact?: boolean;
}

const TrackInfo: React.FC<TrackInfoProps> = ({ track, compact }) => {
    if (!track) {
        return (
            <div className={cn('flex items-center gap-3', compact && 'gap-2')}>
                <div
                    className={cn('bg-dark-400 rounded-lg flex-shrink-0', compact ? 'w-10 h-10' : 'w-14 h-14')}
                />
                <div className="min-w-0">
                    <div className={cn('h-4 bg-dark-300 rounded w-32', compact && 'w-24')} />
                    <div className={cn('h-3 bg-dark-400 rounded w-20 mt-1', compact && 'w-16')} />
                </div>
            </div>
        );
    }

    return (
        <div className={cn('flex items-center gap-3', compact && 'gap-2')}>
            {/* Album Art */}
            <div
                className={cn(
                    'bg-dark-400 rounded-lg flex-shrink-0 overflow-hidden',
                    compact ? 'w-10 h-10' : 'w-14 h-14'
                )}
            >
                {track.coverUrl ? (
                    <img src={track.coverUrl} alt={track.title} className="w-full h-full object-cover" />
                ) : (
                    <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-primary/20 to-accent/20">
                        <svg className="w-6 h-6 text-gray-500" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z" />
                        </svg>
                    </div>
                )}
            </div>

            {/* Track Info */}
            <div className="min-w-0">
                <h4 className={cn('font-medium text-white truncate', compact ? 'text-sm' : 'text-base')}>
                    {track.title}
                </h4>
                {track.artist && (
                    <p className={cn('text-gray-400 truncate', compact ? 'text-xs' : 'text-sm')}>
                        {track.artist}
                    </p>
                )}
            </div>
        </div>
    );
};

/**
 * Waveform - Simple CSS-based waveform visualization
 */
interface WaveformProps {
    isPlaying: boolean;
    progress: number;
}

const Waveform: React.FC<WaveformProps> = ({ isPlaying, progress }) => {
    const bars = 40;

    return (
        <div className="flex items-center justify-center gap-0.5 h-8 overflow-hidden">
            {Array.from({ length: bars }, (_, i) => {
                const isActive = (i / bars) * 100 < progress;
                const height = 20 + Math.sin(i * 0.5) * 60 + Math.random() * 20;

                return (
                    <div
                        key={i}
                        className={cn(
                            'w-1 rounded-full transition-all duration-150',
                            isActive ? 'bg-gradient-to-t from-primary to-accent' : 'bg-dark-300'
                        )}
                        style={{
                            height: isPlaying ? `${height}%` : '20%',
                            animationDelay: isPlaying ? `${i * 50}ms` : '0ms',
                        }}
                    />
                );
            })}
        </div>
    );
};

/**
 * AudioPlayer - Full-featured audio player component
 */
export const AudioPlayer = React.forwardRef<HTMLDivElement, AudioPlayerProps>(
    (
        {
            track,
            variant,
            size,
            compact = false,
            showWaveform = false,
            showControls = true,
            showVolume = true,
            showExtras = false,
            autoPlay = false,
            onEnded,
            onPlayStateChange,
            onSkipNext,
            onSkipPrevious,
            className,
            ...props
        },
        ref
    ) => {
        const audioRef = React.useRef<HTMLAudioElement>(null);
        const [isPlaying, setIsPlaying] = React.useState(false);
        const [currentTime, setCurrentTime] = React.useState(0);
        const [duration, setDuration] = React.useState(0);
        const [volume, setVolume] = React.useState(0.8);
        const [isMuted, setIsMuted] = React.useState(false);
        const [isLoading, setIsLoading] = React.useState(false);
        const [repeatMode, setRepeatMode] = React.useState<'off' | 'all' | 'one'>('off');
        const [shuffle, setShuffle] = React.useState(false);

        // Load track
        React.useEffect(() => {
            if (audioRef.current && track?.audioUrl) {
                audioRef.current.src = track.audioUrl;
                audioRef.current.load();
                if (autoPlay) {
                    audioRef.current.play().catch(() => { });
                }
            }
        }, [track?.audioUrl, autoPlay]);

        // Audio event handlers
        React.useEffect(() => {
            const audio = audioRef.current;
            if (!audio) return;

            const handleTimeUpdate = () => setCurrentTime(audio.currentTime);
            const handleLoadedMetadata = () => setDuration(audio.duration);
            const handlePlay = () => {
                setIsPlaying(true);
                onPlayStateChange?.(true);
            };
            const handlePause = () => {
                setIsPlaying(false);
                onPlayStateChange?.(false);
            };
            const handleEnded = () => {
                if (repeatMode === 'one') {
                    audio.currentTime = 0;
                    audio.play();
                } else {
                    onEnded?.();
                }
            };
            const handleWaiting = () => setIsLoading(true);
            const handleCanPlay = () => setIsLoading(false);

            audio.addEventListener('timeupdate', handleTimeUpdate);
            audio.addEventListener('loadedmetadata', handleLoadedMetadata);
            audio.addEventListener('play', handlePlay);
            audio.addEventListener('pause', handlePause);
            audio.addEventListener('ended', handleEnded);
            audio.addEventListener('waiting', handleWaiting);
            audio.addEventListener('canplay', handleCanPlay);

            return () => {
                audio.removeEventListener('timeupdate', handleTimeUpdate);
                audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
                audio.removeEventListener('play', handlePlay);
                audio.removeEventListener('pause', handlePause);
                audio.removeEventListener('ended', handleEnded);
                audio.removeEventListener('waiting', handleWaiting);
                audio.removeEventListener('canplay', handleCanPlay);
            };
        }, [onEnded, onPlayStateChange, repeatMode]);

        // Volume effect
        React.useEffect(() => {
            if (audioRef.current) {
                audioRef.current.volume = isMuted ? 0 : volume;
            }
        }, [volume, isMuted]);

        const togglePlay = () => {
            if (!audioRef.current) return;
            if (isPlaying) {
                audioRef.current.pause();
            } else {
                audioRef.current.play().catch(() => { });
            }
        };

        const handleSeek = (time: number) => {
            if (audioRef.current) {
                audioRef.current.currentTime = time;
            }
        };

        const handleVolumeChange = (newVolume: number) => {
            setVolume(newVolume);
            if (newVolume > 0 && isMuted) {
                setIsMuted(false);
            }
        };

        const toggleMute = () => setIsMuted(!isMuted);
        const cycleRepeat = () => {
            const modes: ('off' | 'all' | 'one')[] = ['off', 'all', 'one'];
            const currentIndex = modes.indexOf(repeatMode);
            setRepeatMode(modes[(currentIndex + 1) % modes.length]);
        };
        const toggleShuffle = () => setShuffle(!shuffle);

        const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

        return (
            <div ref={ref} className={cn(audioPlayerVariants({ variant, size }), className)} {...props}>
                <audio ref={audioRef} preload="metadata" />

                {compact ? (
                    // Compact layout
                    <div className="flex items-center gap-4">
                        <TrackInfo track={track} compact />

                        <div className="flex-1 mx-4">
                            <ProgressBar current={currentTime} total={duration} onSeek={handleSeek} />
                        </div>

                        <div className="flex items-center gap-2">
                            <button
                                onClick={togglePlay}
                                disabled={!track}
                                className="w-10 h-10 rounded-full bg-primary flex items-center justify-center hover:bg-primary/80 transition-colors disabled:opacity-50"
                            >
                                {isPlaying ? (
                                    <PauseIcon className="w-5 h-5 text-white" />
                                ) : (
                                    <PlayIcon className="w-5 h-5 text-white ml-0.5" />
                                )}
                            </button>
                        </div>
                    </div>
                ) : (
                    // Full layout
                    <div className="space-y-4">
                        {/* Track Info */}
                        <div className="flex items-start justify-between">
                            <TrackInfo track={track} />
                        </div>

                        {/* Waveform */}
                        {showWaveform && <Waveform isPlaying={isPlaying} progress={progress} />}

                        {/* Progress */}
                        <div className="space-y-2">
                            <ProgressBar current={currentTime} total={duration} onSeek={handleSeek} />

                            <div className="flex justify-between text-xs text-gray-500">
                                <span>{formatTime(currentTime)}</span>
                                <span>{formatTime(duration)}</span>
                            </div>
                        </div>

                        {/* Controls */}
                        {showControls && (
                            <div className="flex items-center justify-center gap-4">
                                {showExtras && (
                                    <button
                                        onClick={toggleShuffle}
                                        className={cn(
                                            'p-2 rounded-full transition-colors',
                                            shuffle ? 'text-primary' : 'text-gray-400 hover:text-white'
                                        )}
                                    >
                                        <ShuffleIcon className="w-5 h-5" />
                                    </button>
                                )}

                                {onSkipPrevious && (
                                    <button
                                        onClick={onSkipPrevious}
                                        className="p-2 rounded-full text-gray-400 hover:text-white transition-colors"
                                    >
                                        <SkipBackIcon className="w-5 h-5" />
                                    </button>
                                )}

                                <button
                                    onClick={togglePlay}
                                    disabled={!track}
                                    className={cn(
                                        'w-14 h-14 rounded-full flex items-center justify-center transition-all',
                                        'bg-gradient-to-r from-primary to-accent hover:shadow-lg hover:shadow-primary/30',
                                        'disabled:opacity-50 disabled:cursor-not-allowed'
                                    )}
                                >
                                    {isLoading ? (
                                        <div className="w-6 h-6 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                    ) : isPlaying ? (
                                        <PauseIcon className="w-6 h-6 text-white" />
                                    ) : (
                                        <PlayIcon className="w-6 h-6 text-white ml-1" />
                                    )}
                                </button>

                                {onSkipNext && (
                                    <button
                                        onClick={onSkipNext}
                                        className="p-2 rounded-full text-gray-400 hover:text-white transition-colors"
                                    >
                                        <SkipForwardIcon className="w-5 h-5" />
                                    </button>
                                )}

                                {showExtras && (
                                    <button
                                        onClick={cycleRepeat}
                                        className={cn(
                                            'p-2 rounded-full transition-colors',
                                            repeatMode !== 'off' ? 'text-primary' : 'text-gray-400 hover:text-white'
                                        )}
                                    >
                                        <RepeatIcon className="w-5 h-5" mode={repeatMode} />
                                    </button>
                                )}
                            </div>
                        )}

                        {/* Volume */}
                        {showVolume && (
                            <div className="flex justify-center">
                                <VolumeSlider
                                    volume={volume}
                                    muted={isMuted}
                                    onVolumeChange={handleVolumeChange}
                                    onMuteToggle={toggleMute}
                                />
                            </div>
                        )}
                    </div>
                )}
            </div>
        );
    }
);
AudioPlayer.displayName = 'AudioPlayer';

/**
 * MiniPlayer - Minimal floating player
 */
export interface MiniPlayerProps {
    track?: AudioTrack;
    isPlaying?: boolean;
    onPlayPause?: () => void;
    onExpand?: () => void;
    className?: string;
}

export const MiniPlayer: React.FC<MiniPlayerProps> = ({
    track,
    isPlaying = false,
    onPlayPause,
    onExpand,
    className,
}) => {
    return (
        <div
            className={cn(
                'fixed bottom-4 right-4 flex items-center gap-3 p-3 bg-dark-500/95 backdrop-blur-md rounded-xl border border-white/10 shadow-2xl',
                className
            )}
        >
            {/* Track artwork */}
            <div className="w-12 h-12 bg-dark-400 rounded-lg overflow-hidden flex-shrink-0">
                {track?.coverUrl && (
                    <img src={track.coverUrl} alt={track.title} className="w-full h-full object-cover" />
                )}
            </div>

            {/* Info */}
            <div className="min-w-0 max-w-32" onClick={onExpand}>
                <p className="text-sm font-medium text-white truncate cursor-pointer hover:text-primary">
                    {track?.title || 'No track'}
                </p>
                <p className="text-xs text-gray-400 truncate">{track?.artist || 'Unknown artist'}</p>
            </div>

            {/* Play/Pause */}
            <button
                onClick={onPlayPause}
                disabled={!track}
                className="w-10 h-10 rounded-full bg-primary flex items-center justify-center hover:bg-primary/80 transition-colors disabled:opacity-50"
            >
                {isPlaying ? (
                    <PauseIcon className="w-5 h-5 text-white" />
                ) : (
                    <PlayIcon className="w-5 h-5 text-white ml-0.5" />
                )}
            </button>
        </div>
    );
};

export default AudioPlayer;
