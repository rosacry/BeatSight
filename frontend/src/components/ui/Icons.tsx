/**
 * Icon System
 * Consistent, accessible SVG icons for the BeatSight application.
 * All icons follow a unified design language with proper accessibility.
 */

import React, { forwardRef, type SVGAttributes } from 'react'
import { cn } from '../../lib/utils'

// ============================================================================
// BASE ICON COMPONENT
// ============================================================================

export interface IconProps extends SVGAttributes<SVGElement> {
  /** Icon size - maps to both width and height */
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl' | number
  /** Color - defaults to currentColor */
  color?: string
  /** Accessible label for screen readers */
  label?: string
}

const sizeMap = {
  xs: 12,
  sm: 16,
  md: 20,
  lg: 24,
  xl: 32,
}

/**
 * Base icon wrapper with consistent sizing and accessibility
 */
export const Icon = forwardRef<SVGSVGElement, IconProps & { children: React.ReactNode }>(
  ({ size = 'md', color = 'currentColor', label, className, children, ...props }, ref) => {
    const sizeValue = typeof size === 'number' ? size : sizeMap[size]

    return (
      <svg
        ref={ref}
        width={sizeValue}
        height={sizeValue}
        viewBox="0 0 24 24"
        fill="none"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        className={cn('shrink-0', className)}
        role={label ? 'img' : 'presentation'}
        aria-label={label}
        aria-hidden={!label}
        {...props}
      >
        {children}
      </svg>
    )
  }
)
Icon.displayName = 'Icon'

// ============================================================================
// MUSIC & AUDIO ICONS
// ============================================================================

export const PlayIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <polygon points="5 3 19 12 5 21 5 3" fill="currentColor" stroke="none" />
  </Icon>
))
PlayIcon.displayName = 'PlayIcon'

export const PauseIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <rect x="6" y="4" width="4" height="16" fill="currentColor" stroke="none" />
    <rect x="14" y="4" width="4" height="16" fill="currentColor" stroke="none" />
  </Icon>
))
PauseIcon.displayName = 'PauseIcon'

export const StopIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <rect x="4" y="4" width="16" height="16" rx="2" fill="currentColor" stroke="none" />
  </Icon>
))
StopIcon.displayName = 'StopIcon'

export const SkipForwardIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <polygon points="5 4 15 12 5 20 5 4" fill="currentColor" stroke="none" />
    <line x1="19" y1="5" x2="19" y2="19" />
  </Icon>
))
SkipForwardIcon.displayName = 'SkipForwardIcon'

export const SkipBackIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <polygon points="19 20 9 12 19 4 19 20" fill="currentColor" stroke="none" />
    <line x1="5" y1="19" x2="5" y2="5" />
  </Icon>
))
SkipBackIcon.displayName = 'SkipBackIcon'

export const VolumeIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
    <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
    <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
  </Icon>
))
VolumeIcon.displayName = 'VolumeIcon'

export const VolumeMuteIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
    <line x1="23" y1="9" x2="17" y2="15" />
    <line x1="17" y1="9" x2="23" y2="15" />
  </Icon>
))
VolumeMuteIcon.displayName = 'VolumeMuteIcon'

export const MusicNoteIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <path d="M9 18V5l12-2v13" />
    <circle cx="6" cy="18" r="3" />
    <circle cx="18" cy="16" r="3" />
  </Icon>
))
MusicNoteIcon.displayName = 'MusicNoteIcon'

export const MicrophoneIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
    <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
    <line x1="12" y1="19" x2="12" y2="23" />
    <line x1="8" y1="23" x2="16" y2="23" />
  </Icon>
))
MicrophoneIcon.displayName = 'MicrophoneIcon'

export const WaveformIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <line x1="4" y1="8" x2="4" y2="16" />
    <line x1="8" y1="6" x2="8" y2="18" />
    <line x1="12" y1="4" x2="12" y2="20" />
    <line x1="16" y1="6" x2="16" y2="18" />
    <line x1="20" y1="8" x2="20" y2="16" />
  </Icon>
))
WaveformIcon.displayName = 'WaveformIcon'

// ============================================================================
// DRUM ICONS
// ============================================================================

export const DrumIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <ellipse cx="12" cy="8" rx="9" ry="4" />
    <path d="M3 8v8c0 2.2 4 4 9 4s9-1.8 9-4V8" />
    <line x1="3" y1="8" x2="3" y2="16" />
    <line x1="21" y1="8" x2="21" y2="16" />
  </Icon>
))
DrumIcon.displayName = 'DrumIcon'

export const DrumstickIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <path d="M2 2l6 6" />
    <path d="M8 8a4 4 0 0 0 5.66 5.66L22 5.5l-8.14 8.14A4 4 0 0 0 8 8z" />
    <circle cx="5" cy="19" r="3" />
  </Icon>
))
DrumstickIcon.displayName = 'DrumstickIcon'

export const MetronomeIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <path d="M5 21l2-14h10l2 14z" />
    <line x1="12" y1="7" x2="12" y2="3" />
    <circle cx="12" cy="10" r="1" fill="currentColor" stroke="none" />
    <line x1="12" y1="10" x2="16" y2="3" />
  </Icon>
))
MetronomeIcon.displayName = 'MetronomeIcon'

// ============================================================================
// NAVIGATION ICONS
// ============================================================================

export const HomeIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    <polyline points="9 22 9 12 15 12 15 22" />
  </Icon>
))
HomeIcon.displayName = 'HomeIcon'

export const SearchIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <circle cx="11" cy="11" r="8" />
    <line x1="21" y1="21" x2="16.65" y2="16.65" />
  </Icon>
))
SearchIcon.displayName = 'SearchIcon'

export const SettingsIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </Icon>
))
SettingsIcon.displayName = 'SettingsIcon'

export const UserIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </Icon>
))
UserIcon.displayName = 'UserIcon'

export const MenuIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <line x1="3" y1="12" x2="21" y2="12" />
    <line x1="3" y1="6" x2="21" y2="6" />
    <line x1="3" y1="18" x2="21" y2="18" />
  </Icon>
))
MenuIcon.displayName = 'MenuIcon'

export const CloseIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </Icon>
))
CloseIcon.displayName = 'CloseIcon'

export const ChevronLeftIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <polyline points="15 18 9 12 15 6" />
  </Icon>
))
ChevronLeftIcon.displayName = 'ChevronLeftIcon'

export const ChevronRightIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <polyline points="9 18 15 12 9 6" />
  </Icon>
))
ChevronRightIcon.displayName = 'ChevronRightIcon'

export const ChevronUpIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <polyline points="18 15 12 9 6 15" />
  </Icon>
))
ChevronUpIcon.displayName = 'ChevronUpIcon'

export const ChevronDownIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <polyline points="6 9 12 15 18 9" />
  </Icon>
))
ChevronDownIcon.displayName = 'ChevronDownIcon'

export const ArrowLeftIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <line x1="19" y1="12" x2="5" y2="12" />
    <polyline points="12 19 5 12 12 5" />
  </Icon>
))
ArrowLeftIcon.displayName = 'ArrowLeftIcon'

export const ArrowRightIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <line x1="5" y1="12" x2="19" y2="12" />
    <polyline points="12 5 19 12 12 19" />
  </Icon>
))
ArrowRightIcon.displayName = 'ArrowRightIcon'

// ============================================================================
// ACTION ICONS
// ============================================================================

export const PlusIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <line x1="12" y1="5" x2="12" y2="19" />
    <line x1="5" y1="12" x2="19" y2="12" />
  </Icon>
))
PlusIcon.displayName = 'PlusIcon'

export const MinusIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <line x1="5" y1="12" x2="19" y2="12" />
  </Icon>
))
MinusIcon.displayName = 'MinusIcon'

export const CheckIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <polyline points="20 6 9 17 4 12" />
  </Icon>
))
CheckIcon.displayName = 'CheckIcon'

export const EditIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
  </Icon>
))
EditIcon.displayName = 'EditIcon'

export const TrashIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <polyline points="3 6 5 6 21 6" />
    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
  </Icon>
))
TrashIcon.displayName = 'TrashIcon'

export const CopyIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
  </Icon>
))
CopyIcon.displayName = 'CopyIcon'

export const DownloadIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="7 10 12 15 17 10" />
    <line x1="12" y1="15" x2="12" y2="3" />
  </Icon>
))
DownloadIcon.displayName = 'DownloadIcon'

export const UploadIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="17 8 12 3 7 8" />
    <line x1="12" y1="3" x2="12" y2="15" />
  </Icon>
))
UploadIcon.displayName = 'UploadIcon'

export const ShareIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <circle cx="18" cy="5" r="3" />
    <circle cx="6" cy="12" r="3" />
    <circle cx="18" cy="19" r="3" />
    <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
    <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
  </Icon>
))
ShareIcon.displayName = 'ShareIcon'

export const RefreshIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <polyline points="23 4 23 10 17 10" />
    <polyline points="1 20 1 14 7 14" />
    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
  </Icon>
))
RefreshIcon.displayName = 'RefreshIcon'

// ============================================================================
// STATUS & FEEDBACK ICONS
// ============================================================================

export const InfoIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <circle cx="12" cy="12" r="10" />
    <line x1="12" y1="16" x2="12" y2="12" />
    <line x1="12" y1="8" x2="12.01" y2="8" />
  </Icon>
))
InfoIcon.displayName = 'InfoIcon'

export const WarningIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
    <line x1="12" y1="9" x2="12" y2="13" />
    <line x1="12" y1="17" x2="12.01" y2="17" />
  </Icon>
))
WarningIcon.displayName = 'WarningIcon'

export const ErrorIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <circle cx="12" cy="12" r="10" />
    <line x1="15" y1="9" x2="9" y2="15" />
    <line x1="9" y1="9" x2="15" y2="15" />
  </Icon>
))
ErrorIcon.displayName = 'ErrorIcon'

export const SuccessIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
    <polyline points="22 4 12 14.01 9 11.01" />
  </Icon>
))
SuccessIcon.displayName = 'SuccessIcon'

export const LoadingIcon = forwardRef<SVGSVGElement, IconProps>(({ className, ...props }, ref) => (
  <Icon ref={ref} className={cn('animate-spin', className)} {...props}>
    <line x1="12" y1="2" x2="12" y2="6" />
    <line x1="12" y1="18" x2="12" y2="22" />
    <line x1="4.93" y1="4.93" x2="7.76" y2="7.76" />
    <line x1="16.24" y1="16.24" x2="19.07" y2="19.07" />
    <line x1="2" y1="12" x2="6" y2="12" />
    <line x1="18" y1="12" x2="22" y2="12" />
    <line x1="4.93" y1="19.07" x2="7.76" y2="16.24" />
    <line x1="16.24" y1="7.76" x2="19.07" y2="4.93" />
  </Icon>
))
LoadingIcon.displayName = 'LoadingIcon'

// ============================================================================
// RATING & SCORING ICONS
// ============================================================================

export const StarIcon = forwardRef<SVGSVGElement, IconProps & { filled?: boolean }>(
  ({ filled = false, ...props }, ref) => (
    <Icon ref={ref} {...props}>
      <polygon
        points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"
        fill={filled ? 'currentColor' : 'none'}
      />
    </Icon>
  )
)
StarIcon.displayName = 'StarIcon'

export const HeartIcon = forwardRef<SVGSVGElement, IconProps & { filled?: boolean }>(
  ({ filled = false, ...props }, ref) => (
    <Icon ref={ref} {...props}>
      <path
        d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"
        fill={filled ? 'currentColor' : 'none'}
      />
    </Icon>
  )
)
HeartIcon.displayName = 'HeartIcon'

export const TrophyIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6" />
    <path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18" />
    <path d="M4 22h16" />
    <path d="M10 22V8a6 6 0 0 0-6-6h12a6 6 0 0 1-6 6" />
    <path d="M14 22v-6" />
    <path d="M10 16v6" />
  </Icon>
))
TrophyIcon.displayName = 'TrophyIcon'

export const FireIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z" />
  </Icon>
))
FireIcon.displayName = 'FireIcon'

// ============================================================================
// LAYOUT & VIEW ICONS
// ============================================================================

export const GridIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <rect x="3" y="3" width="7" height="7" />
    <rect x="14" y="3" width="7" height="7" />
    <rect x="14" y="14" width="7" height="7" />
    <rect x="3" y="14" width="7" height="7" />
  </Icon>
))
GridIcon.displayName = 'GridIcon'

export const ListIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <line x1="8" y1="6" x2="21" y2="6" />
    <line x1="8" y1="12" x2="21" y2="12" />
    <line x1="8" y1="18" x2="21" y2="18" />
    <line x1="3" y1="6" x2="3.01" y2="6" />
    <line x1="3" y1="12" x2="3.01" y2="12" />
    <line x1="3" y1="18" x2="3.01" y2="18" />
  </Icon>
))
ListIcon.displayName = 'ListIcon'

export const MaximizeIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3" />
  </Icon>
))
MaximizeIcon.displayName = 'MaximizeIcon'

export const MinimizeIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3" />
  </Icon>
))
MinimizeIcon.displayName = 'MinimizeIcon'

// ============================================================================
// MISC ICONS
// ============================================================================

export const ClockIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <circle cx="12" cy="12" r="10" />
    <polyline points="12 6 12 12 16 14" />
  </Icon>
))
ClockIcon.displayName = 'ClockIcon'

export const CalendarIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
    <line x1="16" y1="2" x2="16" y2="6" />
    <line x1="8" y1="2" x2="8" y2="6" />
    <line x1="3" y1="10" x2="21" y2="10" />
  </Icon>
))
CalendarIcon.displayName = 'CalendarIcon'

export const ExternalLinkIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
    <polyline points="15 3 21 3 21 9" />
    <line x1="10" y1="14" x2="21" y2="3" />
  </Icon>
))
ExternalLinkIcon.displayName = 'ExternalLinkIcon'

export const FilterIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
  </Icon>
))
FilterIcon.displayName = 'FilterIcon'

export const SortIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <line x1="4" y1="6" x2="20" y2="6" />
    <line x1="4" y1="12" x2="16" y2="12" />
    <line x1="4" y1="18" x2="12" y2="18" />
  </Icon>
))
SortIcon.displayName = 'SortIcon'

export const MoreHorizontalIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" />
    <circle cx="19" cy="12" r="1" fill="currentColor" stroke="none" />
    <circle cx="5" cy="12" r="1" fill="currentColor" stroke="none" />
  </Icon>
))
MoreHorizontalIcon.displayName = 'MoreHorizontalIcon'

export const MoreVerticalIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" />
    <circle cx="12" cy="5" r="1" fill="currentColor" stroke="none" />
    <circle cx="12" cy="19" r="1" fill="currentColor" stroke="none" />
  </Icon>
))
MoreVerticalIcon.displayName = 'MoreVerticalIcon'

export const KeyboardIcon = forwardRef<SVGSVGElement, IconProps>((props, ref) => (
  <Icon ref={ref} {...props}>
    <rect x="2" y="4" width="20" height="16" rx="2" ry="2" />
    <path d="M6 8h.001" />
    <path d="M10 8h.001" />
    <path d="M14 8h.001" />
    <path d="M18 8h.001" />
    <path d="M8 12h.001" />
    <path d="M12 12h.001" />
    <path d="M16 12h.001" />
    <path d="M7 16h10" />
  </Icon>
))
KeyboardIcon.displayName = 'KeyboardIcon'

// ============================================================================
// ICON MAP FOR DYNAMIC USAGE
// ============================================================================

export const iconMap = {
  // Music & Audio
  play: PlayIcon,
  pause: PauseIcon,
  stop: StopIcon,
  skipForward: SkipForwardIcon,
  skipBack: SkipBackIcon,
  volume: VolumeIcon,
  volumeMute: VolumeMuteIcon,
  musicNote: MusicNoteIcon,
  microphone: MicrophoneIcon,
  waveform: WaveformIcon,
  drum: DrumIcon,
  drumstick: DrumstickIcon,
  metronome: MetronomeIcon,

  // Navigation
  home: HomeIcon,
  search: SearchIcon,
  settings: SettingsIcon,
  user: UserIcon,
  menu: MenuIcon,
  close: CloseIcon,
  chevronLeft: ChevronLeftIcon,
  chevronRight: ChevronRightIcon,
  chevronUp: ChevronUpIcon,
  chevronDown: ChevronDownIcon,
  arrowLeft: ArrowLeftIcon,
  arrowRight: ArrowRightIcon,

  // Actions
  plus: PlusIcon,
  minus: MinusIcon,
  check: CheckIcon,
  edit: EditIcon,
  trash: TrashIcon,
  copy: CopyIcon,
  download: DownloadIcon,
  upload: UploadIcon,
  share: ShareIcon,
  refresh: RefreshIcon,

  // Status
  info: InfoIcon,
  warning: WarningIcon,
  error: ErrorIcon,
  success: SuccessIcon,
  loading: LoadingIcon,

  // Rating
  star: StarIcon,
  heart: HeartIcon,
  trophy: TrophyIcon,
  fire: FireIcon,

  // Layout
  grid: GridIcon,
  list: ListIcon,
  maximize: MaximizeIcon,
  minimize: MinimizeIcon,

  // Misc
  clock: ClockIcon,
  calendar: CalendarIcon,
  externalLink: ExternalLinkIcon,
  filter: FilterIcon,
  sort: SortIcon,
  moreHorizontal: MoreHorizontalIcon,
  moreVertical: MoreVerticalIcon,
  keyboard: KeyboardIcon,
} as const

export type IconName = keyof typeof iconMap

/**
 * Dynamic icon component that renders based on name
 */
export const DynamicIcon = forwardRef<SVGSVGElement, IconProps & { name: IconName }>(
  ({ name, ...props }, ref) => {
    const IconComponent = iconMap[name]
    return <IconComponent ref={ref} {...props} />
  }
)
DynamicIcon.displayName = 'DynamicIcon'
