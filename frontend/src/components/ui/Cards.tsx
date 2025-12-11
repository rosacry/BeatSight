import React, { useState } from 'react';
import {
    PlayIcon as Play,
    PauseIcon as Pause,
    HeartIcon as Heart,
    MoreHorizontalIcon as MoreHorizontal,
    MusicNoteIcon as Music,
    ClockIcon as Clock,
    ChevronRightIcon as ChevronRight,
    ExternalLinkIcon as ExternalLink,
    CopyIcon as Copy,
    CheckIcon as Check
} from './Icons';

// Trend icons - create inline since they don't exist
const TrendingUp: React.FC<{ className?: string }> = ({ className }) => (
    <svg className={className} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
        <polyline points="17 6 23 6 23 12" />
    </svg>
);

const TrendingDown: React.FC<{ className?: string }> = ({ className }) => (
    <svg className={className} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="23 18 13.5 8.5 8.5 13.5 1 6" />
        <polyline points="17 18 23 18 23 12" />
    </svg>
);

// ============================================================================
// Cards & Data Display Components
// ============================================================================

// ============================================================================
// Basic Card
// ============================================================================

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
    variant?: 'default' | 'elevated' | 'outlined' | 'glass';
    hover?: boolean;
    padding?: 'none' | 'sm' | 'md' | 'lg';
}

export const Card: React.FC<CardProps> = ({
    children,
    variant = 'default',
    hover = false,
    padding = 'md',
    className = '',
    ...props
}) => {
    const variantStyles = {
        default: 'bg-dark-400/50 border border-white/10/50',
        elevated: 'bg-dark-400 shadow-xl shadow-black/20',
        outlined: 'bg-transparent border-2 border-white/10',
        glass: 'bg-dark-400/30 backdrop-blur-md border border-white/10/30',
    };

    const paddingStyles = {
        none: '',
        sm: 'p-3',
        md: 'p-5',
        lg: 'p-6',
    };

    return (
        <div
            className={`
        rounded-2xl transition-all duration-300
        ${variantStyles[variant]}
        ${paddingStyles[padding]}
        ${hover ? 'hover:border-primary-500/30 hover:shadow-lg hover:shadow-primary-500/5 hover:-translate-y-0.5' : ''}
        ${className}
      `}
            {...props}
        >
            {children}
        </div>
    );
};

// ============================================================================
// Track Card - Music track display
// ============================================================================

export interface TrackCardProps {
    title: string;
    artist: string;
    duration: string;
    coverUrl?: string;
    isPlaying?: boolean;
    isFavorite?: boolean;
    difficulty?: 'easy' | 'medium' | 'hard' | 'expert';
    onPlay?: () => void;
    onFavorite?: () => void;
    onMore?: () => void;
}

export const TrackCard: React.FC<TrackCardProps> = ({
    title,
    artist,
    duration,
    coverUrl,
    isPlaying = false,
    isFavorite = false,
    difficulty,
    onPlay,
    onFavorite,
    onMore,
}) => {
    const difficultyColors = {
        easy: 'bg-emerald-500/20 text-emerald-400',
        medium: 'bg-amber-500/20 text-amber-400',
        hard: 'bg-orange-500/20 text-orange-400',
        expert: 'bg-red-500/20 text-red-400',
    };

    return (
        <Card hover className="group">
            <div className="flex items-center gap-4">
                {/* Album Art */}
                <div className="relative w-16 h-16 rounded-xl overflow-hidden bg-dark-300 flex-shrink-0">
                    {coverUrl ? (
                        <img src={coverUrl} alt={title} className="w-full h-full object-cover" />
                    ) : (
                        <div className="w-full h-full flex items-center justify-center">
                            <Music className="w-8 h-8 text-gray-500" />
                        </div>
                    )}
                    {/* Play Overlay */}
                    <button
                        onClick={onPlay}
                        className="absolute inset-0 bg-black/60 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                        {isPlaying ? (
                            <Pause className="w-8 h-8 text-white" />
                        ) : (
                            <Play className="w-8 h-8 text-white ml-1" />
                        )}
                    </button>
                    {/* Playing Indicator */}
                    {isPlaying && (
                        <div className="absolute bottom-1 right-1 w-2 h-2 rounded-full bg-primary-500 animate-pulse" />
                    )}
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-white truncate">{title}</h3>
                    <p className="text-sm text-gray-400 truncate">{artist}</p>
                    <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs text-gray-500 flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {duration}
                        </span>
                        {difficulty && (
                            <span className={`text-xs px-2 py-0.5 rounded-full ${difficultyColors[difficulty]}`}>
                                {difficulty}
                            </span>
                        )}
                    </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                        onClick={onFavorite}
                        className={`p-2 rounded-lg transition-colors ${isFavorite ? 'text-red-400' : 'text-gray-400 hover:text-white hover:bg-dark-300/50'
                            }`}
                    >
                        <Heart className={`w-5 h-5 ${isFavorite ? 'fill-current' : ''}`} />
                    </button>
                    <button
                        onClick={onMore}
                        className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-dark-300/50 transition-colors"
                    >
                        <MoreHorizontal className="w-5 h-5" />
                    </button>
                </div>
            </div>
        </Card>
    );
};

// ============================================================================
// Stat Card - Display metrics
// ============================================================================

export interface StatCardProps {
    label: string;
    value: string | number;
    change?: number;
    changeLabel?: string;
    icon?: React.ReactNode;
    trend?: 'up' | 'down' | 'neutral';
    variant?: 'default' | 'cyan' | 'purple' | 'amber' | 'emerald';
}

export const StatCard: React.FC<StatCardProps> = ({
    label,
    value,
    change,
    changeLabel,
    icon,
    trend,
    variant = 'default',
}) => {
    const variantStyles = {
        default: 'from-dark-400 to-dark-400/50',
        cyan: 'from-primary-500/20 to-dark-400/50',
        purple: 'from-purple-500/20 to-dark-400/50',
        amber: 'from-amber-500/20 to-dark-400/50',
        emerald: 'from-emerald-500/20 to-dark-400/50',
    };

    const iconBgStyles = {
        default: 'bg-dark-300',
        cyan: 'bg-primary-500/20',
        purple: 'bg-purple-500/20',
        amber: 'bg-amber-500/20',
        emerald: 'bg-emerald-500/20',
    };

    return (
        <div className={`rounded-2xl bg-gradient-to-br ${variantStyles[variant]} border border-white/10/50 p-5`}>
            <div className="flex items-start justify-between">
                <div className="space-y-2">
                    <p className="text-sm text-gray-400">{label}</p>
                    <p className="text-3xl font-bold text-white">{value}</p>
                    {change !== undefined && (
                        <div className="flex items-center gap-1.5">
                            {trend === 'up' && <TrendingUp className="w-4 h-4 text-emerald-400" />}
                            {trend === 'down' && <TrendingDown className="w-4 h-4 text-red-400" />}
                            <span className={`text-sm font-medium ${trend === 'up' ? 'text-emerald-400' : trend === 'down' ? 'text-red-400' : 'text-gray-400'
                                }`}>
                                {change > 0 ? '+' : ''}{change}%
                            </span>
                            {changeLabel && <span className="text-sm text-gray-500">{changeLabel}</span>}
                        </div>
                    )}
                </div>
                {icon && (
                    <div className={`p-3 rounded-xl ${iconBgStyles[variant]}`}>
                        {icon}
                    </div>
                )}
            </div>
        </div>
    );
};

// ============================================================================
// User Card / Avatar Card
// ============================================================================

export interface UserCardProps {
    name: string;
    subtitle?: string;
    avatarUrl?: string;
    stats?: Array<{ label: string; value: string | number }>;
    isOnline?: boolean;
    onFollow?: () => void;
    isFollowing?: boolean;
}

export const UserCard: React.FC<UserCardProps> = ({
    name,
    subtitle,
    avatarUrl,
    stats,
    isOnline,
    onFollow,
    isFollowing,
}) => {
    return (
        <Card variant="glass" hover className="text-center">
            {/* Avatar */}
            <div className="relative inline-block mx-auto mb-4">
                <div className="w-20 h-20 rounded-full bg-gradient-to-br from-primary-500 to-purple-500 p-0.5">
                    <div className="w-full h-full rounded-full overflow-hidden bg-dark-400">
                        {avatarUrl ? (
                            <img src={avatarUrl} alt={name} className="w-full h-full object-cover" />
                        ) : (
                            <div className="w-full h-full flex items-center justify-center text-2xl font-bold text-white">
                                {name.charAt(0).toUpperCase()}
                            </div>
                        )}
                    </div>
                </div>
                {isOnline !== undefined && (
                    <div className={`absolute bottom-1 right-1 w-4 h-4 rounded-full border-2 border-white/10 ${isOnline ? 'bg-emerald-500' : 'bg-slate-500'
                        }`} />
                )}
            </div>

            {/* Info */}
            <h3 className="font-semibold text-white">{name}</h3>
            {subtitle && <p className="text-sm text-gray-400 mt-0.5">{subtitle}</p>}

            {/* Stats */}
            {stats && stats.length > 0 && (
                <div className="flex justify-center gap-6 mt-4 pt-4 border-t border-white/10/50">
                    {stats.map((stat, index) => (
                        <div key={index} className="text-center">
                            <p className="font-semibold text-white">{stat.value}</p>
                            <p className="text-xs text-gray-500">{stat.label}</p>
                        </div>
                    ))}
                </div>
            )}

            {/* Follow Button */}
            {onFollow && (
                <button
                    onClick={onFollow}
                    className={`mt-4 w-full py-2 rounded-xl font-medium transition-colors ${isFollowing
                        ? 'bg-dark-300 text-white hover:bg-dark-300'
                        : 'bg-primary-500 text-white hover:bg-primary-400'
                        }`}
                >
                    {isFollowing ? 'Following' : 'Follow'}
                </button>
            )}
        </Card>
    );
};

// ============================================================================
// Feature Card - Highlight features
// ============================================================================

export interface FeatureCardProps {
    title: string;
    description: string;
    icon: React.ReactNode;
    gradient?: 'cyan' | 'purple' | 'amber' | 'emerald';
    action?: {
        label: string;
        onClick: () => void;
    };
}

export const FeatureCard: React.FC<FeatureCardProps> = ({
    title,
    description,
    icon,
    gradient = 'cyan',
    action,
}) => {
    const gradientStyles = {
        cyan: 'from-primary-500/20 via-transparent to-transparent',
        purple: 'from-purple-500/20 via-transparent to-transparent',
        amber: 'from-amber-500/20 via-transparent to-transparent',
        emerald: 'from-emerald-500/20 via-transparent to-transparent',
    };

    const iconColors = {
        cyan: 'text-primary-400',
        purple: 'text-purple-400',
        amber: 'text-amber-400',
        emerald: 'text-emerald-400',
    };

    return (
        <Card hover className={`bg-gradient-to-br ${gradientStyles[gradient]} relative overflow-hidden`}>
            {/* Decorative Glow */}
            <div className={`absolute -top-10 -right-10 w-32 h-32 rounded-full ${gradientStyles[gradient]} blur-2xl opacity-50`} />

            <div className="relative">
                <div className={`w-12 h-12 rounded-xl bg-dark-300/50 flex items-center justify-center mb-4 ${iconColors[gradient]}`}>
                    {icon}
                </div>
                <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
                <p className="text-gray-400 text-sm leading-relaxed">{description}</p>
                {action && (
                    <button
                        onClick={action.onClick}
                        className={`mt-4 text-sm font-medium ${iconColors[gradient]} hover:underline flex items-center gap-1`}
                    >
                        {action.label}
                        <ChevronRight className="w-4 h-4" />
                    </button>
                )}
            </div>
        </Card>
    );
};

// ============================================================================
// Pricing Card
// ============================================================================

export interface PricingCardProps {
    name: string;
    price: string | number;
    period?: string;
    description?: string;
    features: Array<{ text: string; included: boolean }>;
    isPopular?: boolean;
    ctaText?: string;
    onSelect?: () => void;
}

export const PricingCard: React.FC<PricingCardProps> = ({
    name,
    price,
    period = '/month',
    description,
    features,
    isPopular,
    ctaText = 'Get Started',
    onSelect,
}) => {
    return (
        <Card
            variant={isPopular ? 'elevated' : 'default'}
            className={`relative ${isPopular ? 'ring-2 ring-primary-500' : ''}`}
        >
            {isPopular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <span className="px-3 py-1 rounded-full bg-gradient-to-r from-primary-500 to-purple-500 text-white text-xs font-medium">
                        Most Popular
                    </span>
                </div>
            )}

            <div className="text-center mb-6">
                <h3 className="text-lg font-semibold text-white">{name}</h3>
                {description && <p className="text-sm text-gray-400 mt-1">{description}</p>}
                <div className="mt-4">
                    <span className="text-4xl font-bold text-white">${price}</span>
                    <span className="text-gray-400">{period}</span>
                </div>
            </div>

            <ul className="space-y-3 mb-6">
                {features.map((feature, index) => (
                    <li key={index} className="flex items-center gap-3">
                        <div className={`w-5 h-5 rounded-full flex items-center justify-center ${feature.included ? 'bg-primary-500/20' : 'bg-dark-300'
                            }`}>
                            {feature.included ? (
                                <Check className="w-3 h-3 text-primary-400" />
                            ) : (
                                <span className="w-1.5 h-0.5 bg-slate-500 rounded-full" />
                            )}
                        </div>
                        <span className={feature.included ? 'text-gray-300' : 'text-gray-500'}>
                            {feature.text}
                        </span>
                    </li>
                ))}
            </ul>

            <button
                onClick={onSelect}
                className={`w-full py-3 rounded-xl font-medium transition-colors ${isPopular
                    ? 'bg-gradient-to-r from-primary-500 to-purple-500 text-white hover:opacity-90'
                    : 'bg-dark-300 text-white hover:bg-dark-300'
                    }`}
            >
                {ctaText}
            </button>
        </Card>
    );
};

// ============================================================================
// Data Table Row
// ============================================================================

export interface DataTableColumn<T> {
    key: keyof T;
    header: string;
    render?: (value: T[keyof T], item: T) => React.ReactNode;
    width?: string;
}

export interface DataTableProps<T> {
    columns: DataTableColumn<T>[];
    data: T[];
    onRowClick?: (item: T) => void;
    emptyMessage?: string;
}

export function DataTable<T extends { id: string | number }>({
    columns,
    data,
    onRowClick,
    emptyMessage = 'No data available',
}: DataTableProps<T>) {
    return (
        <div className="overflow-x-auto rounded-xl border border-white/10/50">
            <table className="w-full">
                <thead>
                    <tr className="bg-dark-400/50">
                        {columns.map((col) => (
                            <th
                                key={String(col.key)}
                                className="px-4 py-3 text-left text-sm font-medium text-gray-400"
                                style={{ width: col.width }}
                            >
                                {col.header}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {data.length === 0 ? (
                        <tr>
                            <td colSpan={columns.length} className="px-4 py-8 text-center text-gray-500">
                                {emptyMessage}
                            </td>
                        </tr>
                    ) : (
                        data.map((item) => (
                            <tr
                                key={item.id}
                                onClick={() => onRowClick?.(item)}
                                className={`
                  border-t border-white/10/30 transition-colors
                  ${onRowClick ? 'cursor-pointer hover:bg-dark-400/50' : ''}
                `}
                            >
                                {columns.map((col) => (
                                    <td key={String(col.key)} className="px-4 py-3 text-sm text-gray-300">
                                        {col.render ? col.render(item[col.key], item) : String(item[col.key])}
                                    </td>
                                ))}
                            </tr>
                        ))
                    )}
                </tbody>
            </table>
        </div>
    );
}

// ============================================================================
// Code Block with Copy
// ============================================================================

export interface CodeBlockProps {
    code: string;
    language?: string;
    title?: string;
    showLineNumbers?: boolean;
}

export const CodeBlock: React.FC<CodeBlockProps> = ({
    code,
    language = 'text',
    title,
    showLineNumbers = false,
}) => {
    const [copied, setCopied] = useState(false);

    const handleCopy = async () => {
        await navigator.clipboard.writeText(code);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const lines = code.split('\n');

    return (
        <div className="rounded-xl overflow-hidden border border-white/10/50">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-2 bg-dark-400/80 border-b border-white/10/50">
                <div className="flex items-center gap-2">
                    <div className="flex gap-1.5">
                        <div className="w-3 h-3 rounded-full bg-red-500/80" />
                        <div className="w-3 h-3 rounded-full bg-amber-500/80" />
                        <div className="w-3 h-3 rounded-full bg-emerald-500/80" />
                    </div>
                    {title && <span className="text-sm text-gray-400 ml-2">{title}</span>}
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-500">{language}</span>
                    <button
                        onClick={handleCopy}
                        className="p-1.5 rounded-md text-gray-400 hover:text-white hover:bg-dark-300 transition-colors"
                    >
                        {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                    </button>
                </div>
            </div>

            {/* Code */}
            <div className="bg-dark-500/50 overflow-x-auto">
                <pre className="p-4 text-sm">
                    <code className="text-gray-300">
                        {showLineNumbers ? (
                            <table className="w-full">
                                <tbody>
                                    {lines.map((line, i) => (
                                        <tr key={i}>
                                            <td className="pr-4 text-right text-slate-600 select-none w-8">
                                                {i + 1}
                                            </td>
                                            <td className="whitespace-pre">{line}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        ) : (
                            code
                        )}
                    </code>
                </pre>
            </div>
        </div>
    );
};

// ============================================================================
// Link Card - External resource preview
// ============================================================================

export interface LinkCardProps {
    title: string;
    description?: string;
    url: string;
    imageUrl?: string;
    favicon?: string;
    domain?: string;
}

export const LinkCard: React.FC<LinkCardProps> = ({
    title,
    description,
    url,
    imageUrl,
    favicon,
    domain,
}) => {
    return (
        <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="block group"
        >
            <Card hover className="overflow-hidden">
                <div className="flex gap-4">
                    {/* Image Preview */}
                    {imageUrl && (
                        <div className="w-32 h-24 rounded-lg overflow-hidden bg-dark-300 flex-shrink-0">
                            <img src={imageUrl} alt="" className="w-full h-full object-cover" />
                        </div>
                    )}

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                            {favicon && <img src={favicon} alt="" className="w-4 h-4" />}
                            <span className="text-xs text-gray-500">{domain}</span>
                            <ExternalLink className="w-3 h-3 text-gray-500 opacity-0 group-hover:opacity-100 transition-opacity" />
                        </div>
                        <h3 className="font-medium text-white group-hover:text-primary-400 transition-colors truncate">
                            {title}
                        </h3>
                        {description && (
                            <p className="text-sm text-gray-400 line-clamp-2 mt-1">{description}</p>
                        )}
                    </div>
                </div>
            </Card>
        </a>
    );
};

// ============================================================================
// Quick Stats Row
// ============================================================================

export interface QuickStatsProps {
    stats: Array<{
        icon: React.ReactNode;
        label: string;
        value: string | number;
    }>;
}

export const QuickStats: React.FC<QuickStatsProps> = ({ stats }) => {
    return (
        <div className="flex items-center gap-6 flex-wrap">
            {stats.map((stat, index) => (
                <div key={index} className="flex items-center gap-2 text-gray-400">
                    {stat.icon}
                    <span className="font-medium text-white">{stat.value}</span>
                    <span className="text-sm">{stat.label}</span>
                </div>
            ))}
        </div>
    );
};

export default Card;
