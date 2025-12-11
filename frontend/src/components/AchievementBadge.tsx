/**
 * Achievement badge component.
 * Displays a single achievement with icon, name, and earned status.
 */

import { type Achievement } from '@/api/client'
import { cn } from '@/lib/utils'

// Map achievement icon names to SVG paths
const ICON_PATHS: Record<string, string> = {
    trophy: 'M8.21 14.77L7 14.5V14L6 13V12L7 12.5V11L9 10.5L10.5 10V9L10 7L11 6L12 7L13 6L14 7L13.5 9L13.5 10L15 10.5L17 11V12.5L18 12V13L17 14V14.5L15.79 14.77L14 17H10L8.21 14.77Z',
    music: 'M12 3V13.55C11.41 13.21 10.73 13 10 13C7.79 13 6 14.79 6 17S7.79 21 10 21 14 19.21 14 17V7H18V3H12Z',
    collection: 'M4 6H2V20C2 21.1 2.9 22 4 22H18V20H4V6ZM20 2H8C6.9 2 6 2.9 6 4V16C6 17.1 6.9 18 8 18H20C21.1 18 22 17.1 22 16V4C22 2.9 21.1 2 20 2ZM14 14L11 10.5L8 14H20L16 8L14 11L12 9L14 14Z',
    star: 'M12 17.27L18.18 21L16.54 13.97L22 9.24L14.81 8.63L12 2L9.19 8.63L2 9.24L7.46 13.97L5.82 21L12 17.27Z',
    crown: 'M5 16L3 5L8.5 10L12 4L15.5 10L21 5L19 16H5ZM19 19C19 19.55 18.55 20 18 20H6C5.45 20 5 19.55 5 19V18H19V19Z',
    'graduation-cap': 'M12 3L1 9L12 15L21 10.09V17H23V9M5 13.18V17.18L12 21L19 17.18V13.18L12 17L5 13.18Z',
    clock: 'M12 2C6.5 2 2 6.5 2 12S6.5 22 12 22 22 17.5 22 12 17.5 2 12 2ZM12.5 13H11V7H12.5V11.26L16.2 13.27L15.45 14.54L12.5 13Z',
    fire: 'M17.66 11.2C17.43 10.9 17.15 10.64 16.89 10.38C16.22 9.78 15.46 9.35 14.82 8.72C13.33 7.26 13 4.85 13.95 3C13 3.23 12.17 3.75 11.46 4.32C8.87 6.4 7.85 10.07 9.07 13.22C9.11 13.32 9.15 13.42 9.15 13.55C9.15 13.77 9 13.97 8.8 14.05C8.57 14.15 8.33 14.09 8.14 13.93C8.08 13.88 8.04 13.83 8 13.76C6.87 12.33 6.69 10.28 7.45 8.64C5.78 10 4.87 12.3 5 14.47C5.06 14.97 5.12 15.47 5.29 15.97C5.43 16.57 5.7 17.17 6 17.7C7.08 19.43 8.95 20.67 10.96 20.92C13.1 21.19 15.39 20.8 17.03 19.32C18.86 17.66 19.5 15 18.56 12.72L18.43 12.46C18.22 12 17.66 11.2 17.66 11.2Z',
    pencil: 'M20.71 7.04C21.1 6.65 21.1 6 20.71 5.63L18.37 3.29C18 2.9 17.35 2.9 16.96 3.29L15.12 5.12L18.87 8.87M3 17.25V21H6.75L17.81 9.93L14.06 6.18L3 17.25Z',
    'check-circle': 'M12 2C6.5 2 2 6.5 2 12S6.5 22 12 22 22 17.5 22 12 17.5 2 12 2ZM10 17L5 12L6.41 10.59L10 14.17L17.59 6.58L19 8L10 17Z',
    'arrow-up': 'M13 20H11V8L5.5 13.5L4.08 12.08L12 4.16L19.92 12.08L18.5 13.5L13 8V20Z',
    rocket: 'M12 2.5C8.69 2.5 6 5.19 6 8.5C6 12.5 12 19.5 12 19.5S18 12.5 18 8.5C18 5.19 15.31 2.5 12 2.5ZM12 11C10.62 11 9.5 9.88 9.5 8.5S10.62 6 12 6 14.5 7.12 14.5 8.5 13.38 11 12 11ZM5 20.5C5 22.16 8.13 23.5 12 23.5S19 22.16 19 20.5C19 19.5 17.89 18.62 16.13 18.12L15.21 19.04C16.35 19.28 17 19.63 17 20C17 20.78 14.76 21.5 12 21.5S7 20.78 7 20C7 19.63 7.65 19.28 8.79 19.04L7.87 18.12C6.11 18.62 5 19.5 5 20.5Z',
}

// Category colors
const CATEGORY_COLORS: Record<string, { bg: string; border: string; icon: string }> = {
    generation: { bg: 'bg-blue-500/20', border: 'border-blue-500/50', icon: 'text-blue-400' },
    learning: { bg: 'bg-green-500/20', border: 'border-green-500/50', icon: 'text-green-400' },
    contribution: { bg: 'bg-purple-500/20', border: 'border-purple-500/50', icon: 'text-purple-400' },
    social: { bg: 'bg-yellow-500/20', border: 'border-yellow-500/50', icon: 'text-yellow-400' },
    special: { bg: 'bg-pink-500/20', border: 'border-pink-500/50', icon: 'text-pink-400' },
}

interface AchievementBadgeProps {
    achievement: Achievement
    size?: 'sm' | 'md' | 'lg'
    showDescription?: boolean
}

export function AchievementBadge({
    achievement,
    size = 'md',
    showDescription = true,
}: AchievementBadgeProps) {
    const colors = CATEGORY_COLORS[achievement.category] || CATEGORY_COLORS.generation
    const iconPath = ICON_PATHS[achievement.icon] || ICON_PATHS.trophy

    const sizeClasses = {
        sm: 'w-10 h-10',
        md: 'w-14 h-14',
        lg: 'w-20 h-20',
    }

    const iconSizes = {
        sm: 'w-5 h-5',
        md: 'w-7 h-7',
        lg: 'w-10 h-10',
    }

    return (
        <div
            className={cn(
                'flex items-center gap-3 rounded-lg border p-3 transition-all',
                achievement.earned
                    ? `${colors.bg} ${colors.border}`
                    : 'bg-dark-400/50 border-white/10 opacity-50 grayscale'
            )}
        >
            {/* Icon */}
            <div
                className={cn(
                    'flex items-center justify-center rounded-full',
                    sizeClasses[size],
                    achievement.earned ? colors.bg : 'bg-dark-300'
                )}
            >
                <svg
                    viewBox="0 0 24 24"
                    className={cn(
                        iconSizes[size],
                        achievement.earned ? colors.icon : 'text-gray-500'
                    )}
                    fill="currentColor"
                >
                    <path d={iconPath} />
                </svg>
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                    <h3
                        className={cn(
                            'font-semibold truncate',
                            achievement.earned ? 'text-white' : 'text-gray-400'
                        )}
                    >
                        {achievement.name}
                    </h3>
                    {achievement.earned && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-primary-500/20 text-primary-400">
                            +{achievement.points}
                        </span>
                    )}
                </div>
                {showDescription && (
                    <p className="text-sm text-gray-400 truncate">{achievement.description}</p>
                )}
                {achievement.earned && achievement.earned_at && (
                    <p className="text-xs text-gray-500 mt-1">
                        Earned {new Date(achievement.earned_at).toLocaleDateString()}
                    </p>
                )}
            </div>
        </div>
    )
}

interface AchievementGridProps {
    achievements: Achievement[]
    size?: 'sm' | 'md' | 'lg'
}

export function AchievementGrid({ achievements, size = 'md' }: AchievementGridProps) {
    // Group by category
    const byCategory = achievements.reduce(
        (acc, achievement) => {
            const cat = achievement.category
            if (!acc[cat]) acc[cat] = []
            acc[cat].push(achievement)
            return acc
        },
        {} as Record<string, Achievement[]>
    )

    const categoryLabels: Record<string, string> = {
        generation: 'Beatmap Generation',
        learning: 'Learning & Practice',
        contribution: 'Community Contribution',
        social: 'Social',
        special: 'Special',
    }

    return (
        <div className="space-y-6">
            {Object.entries(byCategory).map(([category, categoryAchievements]) => (
                <div key={category}>
                    <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">
                        {categoryLabels[category] || category}
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {categoryAchievements.map((achievement) => (
                            <AchievementBadge
                                key={achievement.id}
                                achievement={achievement}
                                size={size}
                            />
                        ))}
                    </div>
                </div>
            ))}
        </div>
    )
}
