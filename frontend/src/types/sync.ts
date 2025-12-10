/**
 * Types for cloud sync API.
 * Matches backend app/api/routes/sync.py schemas.
 */

/**
 * Custom settings stored in user preferences.
 * These sync across all devices.
 */
export interface CustomSettings {
    // Generation preferences
    autoGenerateBeatmap: boolean
    defaultQuantization: string
    defaultSensitivity: number
    showConfidenceOverlay: boolean
    enableOfflineMode: boolean

    // Notification preferences
    emailJobComplete: boolean
    emailJobFailed: boolean
    pushNotifications: boolean
    marketingEmails: boolean

    // Developer settings
    developerModeEnabled: boolean

    // Anonymous mode settings
    hideFromLeaderboards: boolean
    hideFromPublicQueues: boolean
}

/**
 * User preferences response from the server.
 */
export interface UserPreferences {
    version: number
    checksum: string
    scroll_speed: number
    note_skin: string
    audio_offset_ms: number
    visual_offset_ms: number
    background_dim: number
    master_volume: number
    music_volume: number
    effects_volume: number
    hitsound_volume: number
    theme: string
    language: string
    custom_settings: CustomSettings
    last_modified: string
}

/**
 * Request to update user preferences.
 */
export interface PreferencesUpdate {
    scroll_speed?: number
    note_skin?: string
    audio_offset_ms?: number
    visual_offset_ms?: number
    background_dim?: number
    master_volume?: number
    music_volume?: number
    effects_volume?: number
    hitsound_volume?: number
    theme?: string
    language?: string
    custom_settings?: Partial<CustomSettings>
    expected_version?: number
}

/**
 * Sync client (device) information.
 */
export interface SyncClient {
    id: string
    client_name: string
    client_type: 'desktop' | 'web' | 'mobile'
    last_sync_at: string | null
    last_ip: string | null
    created_at: string
}

/**
 * Default custom settings values.
 * Must match backend app/services/sync.py create_default_preferences
 */
export const DEFAULT_CUSTOM_SETTINGS: CustomSettings = {
    autoGenerateBeatmap: true,
    defaultQuantization: '16th',
    defaultSensitivity: 0.5,
    showConfidenceOverlay: true,
    enableOfflineMode: false,
    emailJobComplete: true,
    emailJobFailed: true,
    pushNotifications: true,
    marketingEmails: false,
    developerModeEnabled: false,
    hideFromLeaderboards: false,
    hideFromPublicQueues: false,
}

/**
 * Default preferences values.
 * Must match backend app/services/sync.py create_default_preferences
 */
export const DEFAULT_PREFERENCES: Omit<UserPreferences, 'version' | 'checksum' | 'last_modified'> = {
    scroll_speed: 1.0,
    note_skin: 'default',
    audio_offset_ms: 0,
    visual_offset_ms: 0,
    background_dim: 0.5,
    master_volume: 1.0,
    music_volume: 0.8,
    effects_volume: 0.8,
    hitsound_volume: 1.0,
    theme: 'dark',
    language: 'en',
    custom_settings: DEFAULT_CUSTOM_SETTINGS,
}
