/**
 * BeatSight Theme System
 * 
 * A comprehensive theming system with support for:
 * - Light/Dark/System mode
 * - Custom accent colors
 * - CSS variable-based theming
 * - Smooth transitions between themes
 */

import {
    createContext,
    useContext,
    useState,
    useEffect,
    useCallback,
    useMemo,
    type ReactNode,
} from 'react'

// ============================================================================
// TYPES
// ============================================================================

export type ThemeMode = 'light' | 'dark' | 'system'

export interface ThemeColors {
    // Primary brand color (cyan)
    primary: {
        50: string
        100: string
        200: string
        300: string
        400: string
        500: string
        600: string
        700: string
        800: string
        900: string
        950: string
    }
    // Accent color (pink)
    accent: {
        50: string
        100: string
        200: string
        300: string
        400: string
        500: string
        600: string
        700: string
        800: string
        900: string
        950: string
    }
    // Background colors
    background: {
        primary: string
        secondary: string
        tertiary: string
        elevated: string
        overlay: string
    }
    // Text colors
    text: {
        primary: string
        secondary: string
        tertiary: string
        disabled: string
        inverse: string
    }
    // Border colors
    border: {
        default: string
        subtle: string
        strong: string
    }
    // Status colors
    status: {
        success: string
        warning: string
        error: string
        info: string
    }
}

export interface Theme {
    mode: 'light' | 'dark'
    colors: ThemeColors
}

export interface ThemeContextValue {
    mode: ThemeMode
    resolvedMode: 'light' | 'dark'
    theme: Theme
    setMode: (mode: ThemeMode) => void
    setAccentColor: (color: string) => void
    accentColor: string
}

// ============================================================================
// DEFAULT THEMES
// ============================================================================

const darkTheme: ThemeColors = {
    primary: {
        50: '#ecfeff',
        100: '#cffafe',
        200: '#a5f3fc',
        300: '#67e8f9',
        400: '#22d3ee',
        500: '#0ea5e9',
        600: '#0891b2',
        700: '#0e7490',
        800: '#155e75',
        900: '#164e63',
        950: '#083344',
    },
    accent: {
        50: '#fdf2f8',
        100: '#fce7f3',
        200: '#fbcfe8',
        300: '#f9a8d4',
        400: '#f472b6',
        500: '#ec4899',
        600: '#db2777',
        700: '#be185d',
        800: '#9d174d',
        900: '#831843',
        950: '#500724',
    },
    background: {
        primary: '#0a0b10',
        secondary: '#0f111a',
        tertiary: '#151722',
        elevated: '#1a1d2e',
        overlay: 'rgba(0, 0, 0, 0.8)',
    },
    text: {
        primary: '#ffffff',
        secondary: '#94a3b8',
        tertiary: '#64748b',
        disabled: '#475569',
        inverse: '#0f172a',
    },
    border: {
        default: '#334155',
        subtle: '#1e293b',
        strong: '#475569',
    },
    status: {
        success: '#22c55e',
        warning: '#f59e0b',
        error: '#ef4444',
        info: '#3b82f6',
    },
}

const lightTheme: ThemeColors = {
    primary: {
        50: '#ecfeff',
        100: '#cffafe',
        200: '#a5f3fc',
        300: '#67e8f9',
        400: '#22d3ee',
        500: '#0ea5e9',
        600: '#0891b2',
        700: '#0e7490',
        800: '#155e75',
        900: '#164e63',
        950: '#083344',
    },
    accent: {
        50: '#fdf2f8',
        100: '#fce7f3',
        200: '#fbcfe8',
        300: '#f9a8d4',
        400: '#f472b6',
        500: '#ec4899',
        600: '#db2777',
        700: '#be185d',
        800: '#9d174d',
        900: '#831843',
        950: '#500724',
    },
    background: {
        primary: '#ffffff',
        secondary: '#f8fafc',
        tertiary: '#f1f5f9',
        elevated: '#ffffff',
        overlay: 'rgba(0, 0, 0, 0.5)',
    },
    text: {
        primary: '#0f172a',
        secondary: '#475569',
        tertiary: '#64748b',
        disabled: '#94a3b8',
        inverse: '#ffffff',
    },
    border: {
        default: '#e2e8f0',
        subtle: '#f1f5f9',
        strong: '#cbd5e1',
    },
    status: {
        success: '#16a34a',
        warning: '#d97706',
        error: '#dc2626',
        info: '#2563eb',
    },
}

// ============================================================================
// CONTEXT
// ============================================================================

const ThemeContext = createContext<ThemeContextValue | null>(null)

export function useTheme() {
    const context = useContext(ThemeContext)
    if (!context) {
        throw new Error('useTheme must be used within a ThemeProvider')
    }
    return context
}

// ============================================================================
// PROVIDER
// ============================================================================

export interface ThemeProviderProps {
    children: ReactNode
    defaultMode?: ThemeMode
    defaultAccentColor?: string
    storageKey?: string
}

export function ThemeProvider({
    children,
    defaultMode = 'dark',
    defaultAccentColor = '#0ea5e9',
    storageKey = 'beatsight-theme',
}: ThemeProviderProps) {
    const [mode, setModeState] = useState<ThemeMode>(() => {
        if (typeof window !== 'undefined') {
            const stored = localStorage.getItem(`${storageKey}-mode`)
            if (stored === 'light' || stored === 'dark' || stored === 'system') {
                return stored
            }
        }
        return defaultMode
    })

    const [accentColor, setAccentColorState] = useState(() => {
        if (typeof window !== 'undefined') {
            return localStorage.getItem(`${storageKey}-accent`) || defaultAccentColor
        }
        return defaultAccentColor
    })

    const [systemMode, setSystemMode] = useState<'light' | 'dark'>('dark')

    // Listen for system theme changes
    useEffect(() => {
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
        setSystemMode(mediaQuery.matches ? 'dark' : 'light')

        const handler = (e: MediaQueryListEvent) => {
            setSystemMode(e.matches ? 'dark' : 'light')
        }

        mediaQuery.addEventListener('change', handler)
        return () => mediaQuery.removeEventListener('change', handler)
    }, [])

    const resolvedMode = mode === 'system' ? systemMode : mode

    const setMode = useCallback((newMode: ThemeMode) => {
        setModeState(newMode)
        localStorage.setItem(`${storageKey}-mode`, newMode)
    }, [storageKey])

    const setAccentColor = useCallback((color: string) => {
        setAccentColorState(color)
        localStorage.setItem(`${storageKey}-accent`, color)
    }, [storageKey])

    // Apply theme to document
    useEffect(() => {
        const root = document.documentElement
        const colors = resolvedMode === 'dark' ? darkTheme : lightTheme

        // Apply class for Tailwind
        if (resolvedMode === 'dark') {
            root.classList.add('dark')
            root.classList.remove('light')
        } else {
            root.classList.add('light')
            root.classList.remove('dark')
        }

        // Set CSS variables
        root.style.setProperty('--color-background-primary', colors.background.primary)
        root.style.setProperty('--color-background-secondary', colors.background.secondary)
        root.style.setProperty('--color-background-tertiary', colors.background.tertiary)
        root.style.setProperty('--color-background-elevated', colors.background.elevated)
        root.style.setProperty('--color-background-overlay', colors.background.overlay)

        root.style.setProperty('--color-text-primary', colors.text.primary)
        root.style.setProperty('--color-text-secondary', colors.text.secondary)
        root.style.setProperty('--color-text-tertiary', colors.text.tertiary)
        root.style.setProperty('--color-text-disabled', colors.text.disabled)

        root.style.setProperty('--color-border-default', colors.border.default)
        root.style.setProperty('--color-border-subtle', colors.border.subtle)
        root.style.setProperty('--color-border-strong', colors.border.strong)

        root.style.setProperty('--color-status-success', colors.status.success)
        root.style.setProperty('--color-status-warning', colors.status.warning)
        root.style.setProperty('--color-status-error', colors.status.error)
        root.style.setProperty('--color-status-info', colors.status.info)

        // Apply accent color
        root.style.setProperty('--color-accent', accentColor)

        // Apply primary colors
        Object.entries(colors.primary).forEach(([key, value]) => {
            root.style.setProperty(`--color-primary-${key}`, value)
        })

        Object.entries(colors.accent).forEach(([key, value]) => {
            root.style.setProperty(`--color-accent-${key}`, value)
        })
    }, [resolvedMode, accentColor])

    const theme = useMemo<Theme>(() => ({
        mode: resolvedMode,
        colors: resolvedMode === 'dark' ? darkTheme : lightTheme,
    }), [resolvedMode])

    const value = useMemo<ThemeContextValue>(() => ({
        mode,
        resolvedMode,
        theme,
        setMode,
        setAccentColor,
        accentColor,
    }), [mode, resolvedMode, theme, setMode, setAccentColor, accentColor])

    return (
        <ThemeContext.Provider value={value}>
            {children}
        </ThemeContext.Provider>
    )
}

// ============================================================================
// THEME TOGGLE COMPONENT
// ============================================================================

export interface ThemeToggleProps {
    className?: string
    showLabel?: boolean
}

export function ThemeToggle({ className, showLabel = false }: ThemeToggleProps) {
    const { mode, setMode } = useTheme()

    const cycleMode = () => {
        const modes: ThemeMode[] = ['light', 'dark', 'system']
        const currentIndex = modes.indexOf(mode)
        const nextIndex = (currentIndex + 1) % modes.length
        setMode(modes[nextIndex])
    }

    const icons = {
        light: (
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
        ),
        dark: (
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
            </svg>
        ),
        system: (
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
        ),
    }

    const labels = {
        light: 'Light',
        dark: 'Dark',
        system: 'System',
    }

    return (
        <button
            onClick={cycleMode}
            className={`flex items-center gap-2 p-2 rounded-lg transition-colors hover:bg-white/10 ${className}`}
            aria-label={`Switch theme (current: ${mode})`}
        >
            {icons[mode]}
            {showLabel && <span className="text-sm">{labels[mode]}</span>}
        </button>
    )
}

// ============================================================================
// ACCENT COLOR PICKER
// ============================================================================

const accentPresets = [
    { name: 'Cyan', color: '#0ea5e9' },
    { name: 'Pink', color: '#ec4899' },
    { name: 'Purple', color: '#8b5cf6' },
    { name: 'Blue', color: '#3b82f6' },
    { name: 'Green', color: '#22c55e' },
    { name: 'Orange', color: '#f97316' },
    { name: 'Red', color: '#ef4444' },
    { name: 'Yellow', color: '#eab308' },
]

export interface AccentColorPickerProps {
    className?: string
}

export function AccentColorPicker({ className }: AccentColorPickerProps) {
    const { accentColor, setAccentColor } = useTheme()

    return (
        <div className={`space-y-3 ${className}`}>
            <label className="block text-sm font-medium text-gray-300">
                Accent Color
            </label>
            <div className="flex flex-wrap gap-2">
                {accentPresets.map((preset) => (
                    <button
                        key={preset.color}
                        onClick={() => setAccentColor(preset.color)}
                        className={`w-8 h-8 rounded-lg border-2 transition-all ${
                            accentColor === preset.color
                                ? 'border-white scale-110'
                                : 'border-transparent hover:scale-105'
                        }`}
                        style={{ backgroundColor: preset.color }}
                        title={preset.name}
                    />
                ))}
            </div>
        </div>
    )
}

// ============================================================================
// UTILITY HOOKS
// ============================================================================

/**
 * Hook to get the current theme mode
 */
export function useThemeMode() {
    const { resolvedMode } = useTheme()
    return resolvedMode
}

/**
 * Hook to check if dark mode is active
 */
export function useIsDarkMode() {
    const { resolvedMode } = useTheme()
    return resolvedMode === 'dark'
}

/**
 * Hook to get theme colors
 */
export function useThemeColors() {
    const { theme } = useTheme()
    return theme.colors
}

// ============================================================================
// CSS UTILITIES
// ============================================================================

/**
 * Generate CSS variable reference for a color
 */
export function cssVar(name: string, fallback?: string) {
    return fallback ? `var(--color-${name}, ${fallback})` : `var(--color-${name})`
}

/**
 * Semantic color classes for Tailwind
 */
export const themeClasses = {
    // Backgrounds
    bgPrimary: 'bg-[var(--color-background-primary)]',
    bgSecondary: 'bg-[var(--color-background-secondary)]',
    bgTertiary: 'bg-[var(--color-background-tertiary)]',
    bgElevated: 'bg-[var(--color-background-elevated)]',

    // Text
    textPrimary: 'text-[var(--color-text-primary)]',
    textSecondary: 'text-[var(--color-text-secondary)]',
    textTertiary: 'text-[var(--color-text-tertiary)]',

    // Borders
    borderDefault: 'border-[var(--color-border-default)]',
    borderSubtle: 'border-[var(--color-border-subtle)]',
    borderStrong: 'border-[var(--color-border-strong)]',

    // Status
    statusSuccess: 'text-[var(--color-status-success)]',
    statusWarning: 'text-[var(--color-status-warning)]',
    statusError: 'text-[var(--color-status-error)]',
    statusInfo: 'text-[var(--color-status-info)]',
}

// ============================================================================
// EXPORTS
// ============================================================================

export {
    darkTheme,
    lightTheme,
    accentPresets,
}
