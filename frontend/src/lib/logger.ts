/**
 * Production-safe logging utility.
 * 
 * In production, logs are suppressed by default unless the user has enabled
 * Developer Mode in settings. In development, all logs are shown.
 * 
 * Usage:
 *   import { logger } from '@/lib/logger';
 *   logger.info('Service started');
 *   logger.error('Failed to load', error);
 *   logger.debug('Detailed info', { data });
 */

const isDevelopment = import.meta.env.DEV;

/**
 * Check if developer mode is enabled.
 * This is checked dynamically to support runtime toggling.
 */
function isDeveloperModeEnabled(): boolean {
    if (typeof localStorage === 'undefined') return false;
    return localStorage.getItem('beatsight:developerMode') === 'true';
}

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface Logger {
    debug: (message: string, ...args: unknown[]) => void;
    info: (message: string, ...args: unknown[]) => void;
    warn: (message: string, ...args: unknown[]) => void;
    error: (message: string, ...args: unknown[]) => void;
    group: (label: string) => void;
    groupEnd: () => void;
}

function shouldLog(level: LogLevel): boolean {
    // Always log errors
    if (level === 'error') return true;

    // In development, log everything
    if (isDevelopment) return true;

    // In production, only log if Developer Mode is enabled
    if (isDeveloperModeEnabled()) return true;

    return false;
}

function formatMessage(prefix: string, message: string): string {
    return `[${prefix}] ${message}`;
}

/**
 * Create a namespaced logger instance.
 * 
 * @param namespace - Logger namespace (e.g., 'PWA', 'WebSocket', 'Auth')
 * @returns Logger instance with debug, info, warn, error methods
 */
export function createLogger(namespace: string): Logger {
    return {
        debug: (message: string, ...args: unknown[]) => {
            if (shouldLog('debug')) {
                 
                console.debug(formatMessage(namespace, message), ...args);
            }
        },
        info: (message: string, ...args: unknown[]) => {
            if (shouldLog('info')) {
                 
                console.info(formatMessage(namespace, message), ...args);
            }
        },
        warn: (message: string, ...args: unknown[]) => {
            if (shouldLog('warn')) {
                 
                console.warn(formatMessage(namespace, message), ...args);
            }
        },
        error: (message: string, ...args: unknown[]) => {
            if (shouldLog('error')) {
                 
                console.error(formatMessage(namespace, message), ...args);
            }
        },
        group: (label: string) => {
            if (shouldLog('debug')) {
                 
                console.group(formatMessage(namespace, label));
            }
        },
        groupEnd: () => {
            if (shouldLog('debug')) {
                 
                console.groupEnd();
            }
        },
    };
}

/**
 * Default application logger.
 */
export const logger = createLogger('BeatSight');

/**
 * Enable Developer Mode (enables console logging in production).
 * This persists to localStorage.
 */
export function enableDeveloperMode(): void {
    if (typeof localStorage !== 'undefined') {
        localStorage.setItem('beatsight:developerMode', 'true');
        logger.info('Developer Mode enabled.');
    }
}

/**
 * Disable Developer Mode.
 */
export function disableDeveloperMode(): void {
    if (typeof localStorage !== 'undefined') {
        localStorage.removeItem('beatsight:developerMode');
        // Use console directly since logger might now be silenced
         
        console.info('[BeatSight] Developer Mode disabled.');
    }
}

/**
 * Check if Developer Mode is currently enabled.
 */
export function getDeveloperModeEnabled(): boolean {
    return isDeveloperModeEnabled();
}

// Expose developer mode controls on window for production debugging
if (typeof window !== 'undefined') {
    (window as unknown as { beatsightDev: { enable: () => void; disable: () => void; isEnabled: () => boolean } }).beatsightDev = {
        enable: enableDeveloperMode,
        disable: disableDeveloperMode,
        isEnabled: getDeveloperModeEnabled,
    };
}
