export {
    registerServiceWorker,
    usePWAInstall,
    useOnlineStatus,
    useServiceWorkerUpdate,
    usePWAStatus,
} from './usePWA'

export {
    KeyboardShortcutsProvider,
    useKeyboardShortcuts,
    useShortcut,
    commonShortcuts,
} from './useKeyboardShortcuts'
export type { Shortcut } from './useKeyboardShortcuts'

export { useJobWebSocket } from './useJobWebSocket'
export type { JobProgressUpdate, JobCompleteUpdate, JobFailedUpdate, JobUpdate } from './useJobWebSocket'

export {
    useStripeConfig,
    useSubscription,
    useUpgradeSubscription,
    useManageSubscription,
    useIsPro,
    useAiQuota,
} from './useBilling'

export {
    useCreditBalance,
    useCreditPacks,
    usePurchaseCredits,
    useCreditHistory,
    useConfigureAutoTopup,
    useDisableAutoTopup,
    useHasCredits,
    useCreditCount,
    useCanPerformAiAction,
    useRefreshCreditBalance,
} from './useCredits'

export {
    useDebounce,
    useDebouncedCallback,
    useThrottledCallback,
    useLeadingThrottle,
    useLeadingDebounce,
} from './useDebounce'

// Real-time connection hooks
export {
    useRealtime,
    useSSE,
    usePresence,
} from './useRealtime'
export type {
    ConnectionState,
    ConnectionStats,
    UseRealtimeOptions,
    UseSSEOptions,
    PresenceUser,
} from './useRealtime'

// Feature flags system
export {
    FeatureFlagsProvider,
    useFeatureFlags,
    useFeatureFlag,
    useFeatureVariant,
    Feature,
    Variant,
    withFeature,
    FeatureFlagsDebugPanel,
    DEFAULT_FLAGS,
} from './useFeatureFlags'
export type {
    FeatureFlag,
    FeatureFlagConfig,
    UserContext,
} from './useFeatureFlags'

// Auto-save hooks for osu!-style settings
export {
    useAutoSave,
    useMultiAutoSave,
} from './useAutoSave'
export type { SaveState } from './useAutoSave'
