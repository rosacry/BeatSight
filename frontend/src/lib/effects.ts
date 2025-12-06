/**
 * Visual Effects Utilities
 * Gradient generators, glass morphism, glow effects, and visual enhancements.
 */

// ============================================================================
// GRADIENT UTILITIES
// ============================================================================

/**
 * Predefined gradient presets for consistent branding
 */
export const gradients = {
  // Brand gradients
  primary: 'bg-gradient-to-r from-cyan-500 to-blue-600',
  secondary: 'bg-gradient-to-r from-fuchsia-500 to-purple-600',
  accent: 'bg-gradient-to-r from-cyan-400 via-fuchsia-500 to-amber-400',

  // Status gradients
  success: 'bg-gradient-to-r from-emerald-400 to-green-500',
  warning: 'bg-gradient-to-r from-amber-400 to-orange-500',
  danger: 'bg-gradient-to-r from-rose-400 to-red-500',
  info: 'bg-gradient-to-r from-sky-400 to-blue-500',

  // Atmospheric gradients
  sunset: 'bg-gradient-to-r from-orange-500 via-rose-500 to-purple-600',
  ocean: 'bg-gradient-to-r from-cyan-500 via-blue-500 to-indigo-600',
  forest: 'bg-gradient-to-r from-emerald-500 via-green-500 to-teal-600',
  aurora: 'bg-gradient-to-r from-green-400 via-cyan-500 to-purple-500',

  // Dark/Light mode gradients
  darkSurface: 'bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900',
  lightSurface: 'bg-gradient-to-br from-white via-slate-50 to-slate-100',

  // Radial gradients (use with arbitrary values)
  radialPrimary: 'bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-cyan-500/30 via-transparent to-transparent',
  radialAccent: 'bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-fuchsia-500/30 via-transparent to-transparent',

  // Mesh/multi-stop gradients for backgrounds
  mesh1: 'bg-[conic-gradient(at_top_right,_var(--tw-gradient-stops))] from-cyan-500 via-purple-500 to-cyan-500',
  mesh2: 'bg-[conic-gradient(at_bottom_left,_var(--tw-gradient-stops))] from-fuchsia-500 via-amber-500 to-fuchsia-500',

  // Text gradients (use with bg-clip-text text-transparent)
  textPrimary: 'bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent',
  textAccent: 'bg-gradient-to-r from-fuchsia-400 to-purple-500 bg-clip-text text-transparent',
  textRainbow: 'bg-gradient-to-r from-cyan-400 via-fuchsia-500 to-amber-400 bg-clip-text text-transparent',
} as const

/**
 * Generate a custom gradient string
 */
export function createGradient(
  direction: 'to-r' | 'to-l' | 'to-t' | 'to-b' | 'to-tr' | 'to-tl' | 'to-br' | 'to-bl',
  ...colors: string[]
): string {
  const colorStops = colors.map((color, index) => {
    if (index === 0) return `from-${color}`
    if (index === colors.length - 1) return `to-${color}`
    return `via-${color}`
  })
  return `bg-gradient-${direction} ${colorStops.join(' ')}`
}

// ============================================================================
// GLASS MORPHISM EFFECTS
// ============================================================================

/**
 * Glass morphism effect presets
 */
export const glass = {
  // Light glass effects
  light: 'bg-white/10 backdrop-blur-md border border-white/20',
  lightSubtle: 'bg-white/5 backdrop-blur-sm border border-white/10',
  lightStrong: 'bg-white/20 backdrop-blur-lg border border-white/30',

  // Dark glass effects  
  dark: 'bg-black/20 backdrop-blur-md border border-white/10',
  darkSubtle: 'bg-black/10 backdrop-blur-sm border border-white/5',
  darkStrong: 'bg-black/40 backdrop-blur-lg border border-white/20',

  // Colored glass effects
  cyan: 'bg-cyan-500/10 backdrop-blur-md border border-cyan-400/30',
  fuchsia: 'bg-fuchsia-500/10 backdrop-blur-md border border-fuchsia-400/30',
  amber: 'bg-amber-500/10 backdrop-blur-md border border-amber-400/30',

  // Card-style glass
  card: 'bg-slate-900/60 backdrop-blur-xl border border-slate-700/50 shadow-xl',
  cardHover: 'bg-slate-800/70 backdrop-blur-xl border border-slate-600/50 shadow-2xl',

  // Modal/overlay glass
  overlay: 'bg-slate-900/80 backdrop-blur-2xl',
  modal: 'bg-slate-900/90 backdrop-blur-2xl border border-slate-700/50 shadow-2xl',
} as const

// ============================================================================
// GLOW EFFECTS
// ============================================================================

/**
 * Glow effect presets using box-shadow
 */
export const glow = {
  // Color glows
  cyan: 'shadow-[0_0_20px_rgba(0,212,255,0.3)]',
  cyanStrong: 'shadow-[0_0_40px_rgba(0,212,255,0.5)]',
  cyanSubtle: 'shadow-[0_0_10px_rgba(0,212,255,0.2)]',

  fuchsia: 'shadow-[0_0_20px_rgba(217,70,239,0.3)]',
  fuchsiaStrong: 'shadow-[0_0_40px_rgba(217,70,239,0.5)]',
  fuchsiaSubtle: 'shadow-[0_0_10px_rgba(217,70,239,0.2)]',

  amber: 'shadow-[0_0_20px_rgba(245,158,11,0.3)]',
  amberStrong: 'shadow-[0_0_40px_rgba(245,158,11,0.5)]',
  amberSubtle: 'shadow-[0_0_10px_rgba(245,158,11,0.2)]',

  // Status glows
  success: 'shadow-[0_0_20px_rgba(34,197,94,0.3)]',
  warning: 'shadow-[0_0_20px_rgba(245,158,11,0.3)]',
  danger: 'shadow-[0_0_20px_rgba(239,68,68,0.3)]',

  // White/neutral glows
  white: 'shadow-[0_0_20px_rgba(255,255,255,0.2)]',
  whiteStrong: 'shadow-[0_0_40px_rgba(255,255,255,0.3)]',

  // Ring glows (outline style)
  ringCyan: 'ring-2 ring-cyan-500/50 ring-offset-2 ring-offset-slate-900',
  ringFuchsia: 'ring-2 ring-fuchsia-500/50 ring-offset-2 ring-offset-slate-900',
} as const

/**
 * Generate a custom glow effect
 */
export function createGlow(color: string, intensity: number = 0.3, spread: number = 20): string {
  return `shadow-[0_0_${spread}px_${color}${Math.round(intensity * 255).toString(16).padStart(2, '0')}]`
}

// ============================================================================
// TEXT EFFECTS
// ============================================================================

/**
 * Text effect presets
 */
export const textEffects = {
  // Gradient text
  gradientCyan: 'bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent',
  gradientFuchsia: 'bg-gradient-to-r from-fuchsia-400 to-purple-500 bg-clip-text text-transparent',
  gradientRainbow: 'bg-gradient-to-r from-cyan-400 via-fuchsia-500 to-amber-400 bg-clip-text text-transparent',
  gradientSunset: 'bg-gradient-to-r from-orange-400 via-rose-500 to-purple-500 bg-clip-text text-transparent',

  // Text shadows
  glow: 'drop-shadow-[0_0_10px_rgba(0,212,255,0.5)]',
  glowStrong: 'drop-shadow-[0_0_20px_rgba(0,212,255,0.7)]',
  glowFuchsia: 'drop-shadow-[0_0_10px_rgba(217,70,239,0.5)]',

  // Outlined text (requires specific font)
  outline: '[text-shadow:_-1px_-1px_0_#000,_1px_-1px_0_#000,_-1px_1px_0_#000,_1px_1px_0_#000]',

  // 3D text effect
  shadow3d: '[text-shadow:_2px_2px_0_rgba(0,0,0,0.3)]',
} as const

// ============================================================================
// PATTERN BACKGROUNDS
// ============================================================================

/**
 * Decorative pattern backgrounds
 */
export const patterns = {
  // Dot patterns
  dots: `bg-[radial-gradient(circle,_rgba(255,255,255,0.1)_1px,_transparent_1px)] bg-[size:20px_20px]`,
  dotsLarge: `bg-[radial-gradient(circle,_rgba(255,255,255,0.1)_2px,_transparent_2px)] bg-[size:40px_40px]`,

  // Grid patterns
  grid: `bg-[linear-gradient(rgba(255,255,255,0.05)_1px,_transparent_1px),_linear-gradient(90deg,_rgba(255,255,255,0.05)_1px,_transparent_1px)] bg-[size:20px_20px]`,
  gridLarge: `bg-[linear-gradient(rgba(255,255,255,0.05)_1px,_transparent_1px),_linear-gradient(90deg,_rgba(255,255,255,0.05)_1px,_transparent_1px)] bg-[size:40px_40px]`,

  // Stripe patterns
  stripes: `bg-[repeating-linear-gradient(45deg,_transparent,_transparent_10px,_rgba(255,255,255,0.03)_10px,_rgba(255,255,255,0.03)_20px)]`,
  stripesHorizontal: `bg-[repeating-linear-gradient(0deg,_transparent,_transparent_10px,_rgba(255,255,255,0.03)_10px,_rgba(255,255,255,0.03)_20px)]`,

  // Noise texture (requires noise.png or SVG filter)
  noise: `before:content-[''] before:absolute before:inset-0 before:bg-[url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIzMDAiIGhlaWdodD0iMzAwIj48ZmlsdGVyIGlkPSJhIiB4PSIwIiB5PSIwIj48ZmVUdXJidWxlbmNlIGJhc2VGcmVxdWVuY3k9Ii43NSIgc3RpdGNoVGlsZXM9InN0aXRjaCIgdHlwZT0iZnJhY3RhbE5vaXNlIi8+PC9maWx0ZXI+PHJlY3QgZmlsdGVyPSJ1cmwoI2EpIiBoZWlnaHQ9IjEwMCUiIG9wYWNpdHk9IjAuMDUiIHdpZHRoPSIxMDAlIi8+PC9zdmc+')] before:opacity-50 before:pointer-events-none`,
} as const

// ============================================================================
// BORDER EFFECTS
// ============================================================================

/**
 * Border effect presets
 */
export const borders = {
  // Gradient borders (requires wrapper technique)
  gradientCyan: 'relative before:absolute before:inset-0 before:rounded-[inherit] before:p-[1px] before:bg-gradient-to-r before:from-cyan-500 before:to-blue-500 before:-z-10',
  gradientFuchsia: 'relative before:absolute before:inset-0 before:rounded-[inherit] before:p-[1px] before:bg-gradient-to-r before:from-fuchsia-500 before:to-purple-500 before:-z-10',
  gradientRainbow: 'relative before:absolute before:inset-0 before:rounded-[inherit] before:p-[1px] before:bg-gradient-to-r before:from-cyan-500 before:via-fuchsia-500 before:to-amber-500 before:-z-10',

  // Animated gradient border
  animatedGradient: 'relative before:absolute before:inset-0 before:rounded-[inherit] before:p-[2px] before:bg-[conic-gradient(from_var(--border-angle),_#00d4ff,_#d946ef,_#f59e0b,_#00d4ff)] before:-z-10 before:animate-spin-slow',

  // Subtle borders
  subtle: 'border border-slate-700/50',
  subtleHover: 'border border-slate-700/50 hover:border-slate-600/70 transition-colors',

  // Glow borders
  glowCyan: 'border border-cyan-500/50 shadow-[0_0_10px_rgba(0,212,255,0.2)]',
  glowFuchsia: 'border border-fuchsia-500/50 shadow-[0_0_10px_rgba(217,70,239,0.2)]',
} as const

// ============================================================================
// ANIMATION UTILITIES
// ============================================================================

/**
 * Common transition presets
 */
export const transitions = {
  // Basic transitions
  default: 'transition-all duration-200 ease-out',
  fast: 'transition-all duration-150 ease-out',
  slow: 'transition-all duration-300 ease-out',

  // Specific property transitions
  colors: 'transition-colors duration-200 ease-out',
  transform: 'transition-transform duration-200 ease-out',
  opacity: 'transition-opacity duration-200 ease-out',
  shadow: 'transition-shadow duration-200 ease-out',

  // Bouncy transitions
  bounce: 'transition-all duration-300 ease-[cubic-bezier(0.34,1.56,0.64,1)]',
  bounceFast: 'transition-all duration-200 ease-[cubic-bezier(0.34,1.56,0.64,1)]',

  // Spring transitions
  spring: 'transition-all duration-500 ease-[cubic-bezier(0.175,0.885,0.32,1.275)]',
} as const

/**
 * Hover effect presets
 */
export const hoverEffects = {
  // Scale effects
  lift: 'hover:-translate-y-1 hover:shadow-lg',
  liftSubtle: 'hover:-translate-y-0.5 hover:shadow-md',
  grow: 'hover:scale-105',
  growSubtle: 'hover:scale-102',
  shrink: 'hover:scale-95',

  // Glow effects
  glowCyan: 'hover:shadow-[0_0_20px_rgba(0,212,255,0.3)]',
  glowFuchsia: 'hover:shadow-[0_0_20px_rgba(217,70,239,0.3)]',

  // Border effects
  borderGlow: 'hover:border-cyan-500/50 hover:shadow-[0_0_10px_rgba(0,212,255,0.2)]',

  // Combined effects
  card: 'hover:-translate-y-1 hover:shadow-xl hover:border-slate-600/70',
  button: 'hover:scale-105 hover:shadow-lg active:scale-95',
  link: 'hover:text-cyan-400 hover:underline underline-offset-4',
} as const

// ============================================================================
// RESPONSIVE UTILITIES
// ============================================================================

/**
 * Container width presets
 */
export const containers = {
  xs: 'max-w-xs mx-auto',      // 320px
  sm: 'max-w-sm mx-auto',      // 384px
  md: 'max-w-md mx-auto',      // 448px
  lg: 'max-w-lg mx-auto',      // 512px
  xl: 'max-w-xl mx-auto',      // 576px
  '2xl': 'max-w-2xl mx-auto',  // 672px
  '3xl': 'max-w-3xl mx-auto',  // 768px
  '4xl': 'max-w-4xl mx-auto',  // 896px
  '5xl': 'max-w-5xl mx-auto',  // 1024px
  '6xl': 'max-w-6xl mx-auto',  // 1152px
  '7xl': 'max-w-7xl mx-auto',  // 1280px
  full: 'max-w-full',
  prose: 'max-w-prose mx-auto', // 65ch
  screen: 'max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-8',
} as const

/**
 * Aspect ratio presets
 */
export const aspectRatios = {
  square: 'aspect-square',
  video: 'aspect-video',      // 16:9
  portrait: 'aspect-[3/4]',
  wide: 'aspect-[21/9]',
  album: 'aspect-square',     // CD artwork
  banner: 'aspect-[4/1]',
} as const

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Combine multiple effect classes
 */
export function combine(...effects: (string | undefined | false)[]): string {
  return effects.filter(Boolean).join(' ')
}

/**
 * Create a CSS variable-based color with opacity
 */
export function withOpacity(colorVar: string, opacity: number): string {
  return `rgba(var(${colorVar}), ${opacity})`
}

/**
 * Generate a shimmer/loading gradient animation style
 */
export function shimmerStyle(baseColor: string = '#1e293b', shimmerColor: string = '#334155'): React.CSSProperties {
  return {
    background: `linear-gradient(90deg, ${baseColor} 0%, ${shimmerColor} 50%, ${baseColor} 100%)`,
    backgroundSize: '200% 100%',
    animation: 'shimmer 1.5s infinite',
  }
}

/**
 * Create a pulsing glow animation style
 */
export function pulseGlowStyle(color: string, intensity: number = 0.5): React.CSSProperties {
  return {
    animation: 'pulse-glow 2s ease-in-out infinite',
    '--glow-color': color,
    '--glow-intensity': intensity,
  } as React.CSSProperties
}
