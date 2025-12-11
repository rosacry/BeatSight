/**
 * Feature Flags System
 * 
 * Client-side feature flag management with remote config support,
 * user targeting, and A/B testing capabilities.
 */

import React, { createContext, useContext, useState, useEffect, useCallback, useMemo, ReactNode } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

// ============================================================================
// Types
// ============================================================================

export interface FeatureFlag {
    key: string;
    enabled: boolean;
    variant?: string;
    payload?: Record<string, unknown>;
}

export interface FeatureFlagConfig {
    key: string;
    defaultValue: boolean;
    description?: string;
    variants?: string[];
}

export interface UserContext {
    id?: string;
    email?: string;
    plan?: 'free' | 'pro' | 'enterprise';
    createdAt?: Date;
    attributes?: Record<string, string | number | boolean>;
}

interface FeatureFlagsContextValue {
    flags: Map<string, FeatureFlag>;
    isEnabled: (key: string) => boolean;
    getVariant: (key: string) => string | undefined;
    getPayload: <T = unknown>(key: string) => T | undefined;
    refresh: () => Promise<void>;
    isLoading: boolean;
    setUserContext: (context: UserContext) => void;
}

// ============================================================================
// Default Flags Configuration
// ============================================================================

export const DEFAULT_FLAGS: FeatureFlagConfig[] = [
    {
        key: 'new_dashboard',
        defaultValue: false,
        description: 'New analytics dashboard UI',
    },
    {
        key: 'ai_suggestions',
        defaultValue: true,
        description: 'Smart beatmap suggestions',
    },
    {
        key: 'social_features',
        defaultValue: false,
        description: 'Social features like following and activity feed',
    },
    {
        key: 'advanced_editor',
        defaultValue: false,
        description: 'Advanced beatmap editor with automation lanes',
        variants: ['basic', 'advanced', 'pro'],
    },
    {
        key: 'dark_mode_v2',
        defaultValue: false,
        description: 'New dark mode color scheme',
    },
    {
        key: 'credits_system',
        defaultValue: true,
        description: 'Credits-based transcription system',
    },
    {
        key: 'bulk_upload',
        defaultValue: false,
        description: 'Bulk song upload feature',
    },
    {
        key: 'realtime_collaboration',
        defaultValue: false,
        description: 'Real-time collaborative editing',
    },
];

// ============================================================================
// Context
// ============================================================================

const FeatureFlagsContext = createContext<FeatureFlagsContextValue | null>(null);

// ============================================================================
// Provider
// ============================================================================

interface FeatureFlagsProviderProps {
    children: ReactNode;
    apiUrl?: string;
    defaultFlags?: FeatureFlagConfig[];
    refreshInterval?: number;
    userContext?: UserContext;
}

export function FeatureFlagsProvider({
    children,
    apiUrl = '/api/v1/feature-flags',
    defaultFlags = DEFAULT_FLAGS,
    refreshInterval = 300000, // 5 minutes
    userContext: initialUserContext,
}: FeatureFlagsProviderProps) {
    const [flags, setFlags] = useState<Map<string, FeatureFlag>>(() => {
        // Initialize with defaults
        const initial = new Map<string, FeatureFlag>();
        for (const config of defaultFlags) {
            initial.set(config.key, {
                key: config.key,
                enabled: config.defaultValue,
                variant: config.variants?.[0],
            });
        }
        return initial;
    });

    const [userContext, setUserContext] = useState<UserContext | undefined>(initialUserContext);
    const [isLoading, setIsLoading] = useState(false);

    // Fetch flags from server
    const fetchFlags = useCallback(async () => {
        setIsLoading(true);
        try {
            const params = new URLSearchParams();
            if (userContext?.id) params.set('user_id', userContext.id);
            if (userContext?.plan) params.set('plan', userContext.plan);

            const response = await fetch(`${apiUrl}?${params}`);
            if (!response.ok) throw new Error('Failed to fetch feature flags');

            const data = await response.json() as { flags: FeatureFlag[] };

            setFlags(prev => {
                const next = new Map(prev);
                for (const flag of data.flags) {
                    next.set(flag.key, flag);
                }
                return next;
            });

            // Cache in localStorage
            localStorage.setItem('beatsight_feature_flags', JSON.stringify(
                Object.fromEntries(flags)
            ));
        } catch (error) {
            console.warn('Failed to fetch feature flags, using cached/defaults:', error);

            // Try to load from cache
            const cached = localStorage.getItem('beatsight_feature_flags');
            if (cached) {
                try {
                    const parsed = JSON.parse(cached);
                    setFlags(new Map(Object.entries(parsed)));
                } catch {
                    // Invalid cache, ignore
                }
            }
        } finally {
            setIsLoading(false);
        }
    }, [apiUrl, userContext, flags]);

    // Fetch on mount and when user context changes
    useEffect(() => {
        fetchFlags();
    }, [fetchFlags]);

    // Periodic refresh
    useEffect(() => {
        if (refreshInterval <= 0) return;

        const interval = setInterval(fetchFlags, refreshInterval);
        return () => clearInterval(interval);
    }, [fetchFlags, refreshInterval]);

    // Check if flag is enabled
    const isEnabled = useCallback((key: string): boolean => {
        const flag = flags.get(key);
        if (!flag) {
            // Check defaults
            const defaultConfig = defaultFlags.find(f => f.key === key);
            return defaultConfig?.defaultValue ?? false;
        }
        return flag.enabled;
    }, [flags, defaultFlags]);

    // Get variant for A/B testing
    const getVariant = useCallback((key: string): string | undefined => {
        return flags.get(key)?.variant;
    }, [flags]);

    // Get payload data
    const getPayload = useCallback(<T = unknown>(key: string): T | undefined => {
        return flags.get(key)?.payload as T | undefined;
    }, [flags]);

    const value = useMemo(() => ({
        flags,
        isEnabled,
        getVariant,
        getPayload,
        refresh: fetchFlags,
        isLoading,
        setUserContext,
    }), [flags, isEnabled, getVariant, getPayload, fetchFlags, isLoading]);

    return (
        <FeatureFlagsContext.Provider value={value}>
            {children}
        </FeatureFlagsContext.Provider>
    );
}

// ============================================================================
// Hooks
// ============================================================================

export function useFeatureFlags() {
    const context = useContext(FeatureFlagsContext);
    if (!context) {
        throw new Error('useFeatureFlags must be used within a FeatureFlagsProvider');
    }
    return context;
}

export function useFeatureFlag(key: string): boolean {
    const { isEnabled } = useFeatureFlags();
    return isEnabled(key);
}

export function useFeatureVariant(key: string): string | undefined {
    const { getVariant } = useFeatureFlags();
    return getVariant(key);
}

// ============================================================================
// Components
// ============================================================================

interface FeatureProps {
    flag: string;
    children: ReactNode;
    fallback?: ReactNode;
}

/**
 * Conditionally render content based on feature flag.
 * 
 * @example
 * <Feature flag="new_dashboard">
 *   <NewDashboard />
 * </Feature>
 */
export function Feature({ flag, children, fallback = null }: FeatureProps) {
    const isEnabled = useFeatureFlag(flag);
    return <>{isEnabled ? children : fallback}</>;
}

interface VariantProps {
    flag: string;
    variants: Record<string, ReactNode>;
    fallback?: ReactNode;
}

/**
 * Render different content based on feature variant.
 * 
 * @example
 * <Variant 
 *   flag="advanced_editor" 
 *   variants={{
 *     basic: <BasicEditor />,
 *     advanced: <AdvancedEditor />,
 *     pro: <ProEditor />,
 *   }}
 * />
 */
export function Variant({ flag, variants, fallback = null }: VariantProps) {
    const variant = useFeatureVariant(flag);
    if (!variant || !(variant in variants)) {
        return <>{fallback}</>;
    }
    return <>{variants[variant]}</>;
}

// ============================================================================
// Higher-Order Component
// ============================================================================

interface WithFeatureOptions {
    flag: string;
    fallback?: React.ComponentType;
}

/**
 * HOC to wrap component with feature flag check.
 * 
 * @example
 * const NewFeatureComponent = withFeature({ flag: 'new_feature' })(MyComponent);
 */
export function withFeature<P extends object>(options: WithFeatureOptions) {
    const { flag, fallback: FallbackComponent } = options;

    return function withFeatureWrapper(WrappedComponent: React.ComponentType<P>) {
        return function WithFeature(props: P) {
            const isEnabled = useFeatureFlag(flag);

            if (!isEnabled) {
                return FallbackComponent ? <FallbackComponent /> : null;
            }

            return <WrappedComponent {...props} />;
        };
    };
}

// ============================================================================
// Debug Panel (Development Only)
// ============================================================================

export function FeatureFlagsDebugPanel() {
    const { flags, refresh, isLoading } = useFeatureFlags();
    const [isOpen, setIsOpen] = useState(false);

    if (import.meta.env.PROD) {
        return null;
    }

    return (
        <div className="fixed bottom-4 right-4 z-[9999]">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="bg-gray-900 text-white px-3 py-2 rounded-lg shadow-lg text-sm font-medium hover:bg-gray-800"
            >
                🚩 Flags ({flags.size})
            </button>

            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95, y: 10 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95, y: 10 }}
                        transition={{ duration: 0.15, ease: [0.4, 0, 0.2, 1] }}
                        className="absolute bottom-12 right-0 w-80 bg-gray-900 border border-gray-700 rounded-lg shadow-2xl overflow-hidden"
                    >
                        <div className="p-3 border-b border-gray-700 flex items-center justify-between">
                            <span className="font-medium text-white">Feature Flags</span>
                            <button
                                onClick={refresh}
                                disabled={isLoading}
                                className="text-xs text-primary-400 hover:text-primary-300 disabled:opacity-50"
                            >
                                {isLoading ? 'Loading...' : 'Refresh'}
                            </button>
                        </div>

                        <div className="max-h-80 overflow-y-auto">
                            {Array.from(flags.values()).map((flag, index) => (
                                <motion.div
                                    key={flag.key}
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: index * 0.03, duration: 0.15 }}
                                    className="px-3 py-2 border-b border-gray-800 last:border-0 flex items-center justify-between"
                                >
                                    <div>
                                        <div className="text-sm text-white font-mono">{flag.key}</div>
                                        {flag.variant && (
                                            <div className="text-xs text-gray-400">variant: {flag.variant}</div>
                                        )}
                                    </div>
                                    <div className={`text-xs font-medium ${flag.enabled ? 'text-green-400' : 'text-red-400'}`}>
                                        {flag.enabled ? 'ON' : 'OFF'}
                                    </div>
                                </motion.div>
                            ))}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
