/**
 * Error reporting and monitoring integration.
 * 
 * This module provides a simple abstraction over error tracking.
 * In production, this would integrate with Sentry or similar service.
 * 
 * To enable Sentry:
 * 1. Install @sentry/react: npm install @sentry/react
 * 2. Set VITE_SENTRY_DSN in your environment
 * 3. Uncomment the Sentry imports and initialization below
 */

import React from 'react';
// import * as Sentry from '@sentry/react';

interface ErrorContext {
    [key: string]: unknown;
}

interface UserContext {
    id?: string;
    email?: string;
    username?: string;
}

let isInitialized = false;
let currentUser: UserContext | null = null;

/**
 * Initialize error reporting.
 * Call this once at app startup.
 */
export function initErrorReporting(): void {
    if (isInitialized) return;

    const dsn = import.meta.env.VITE_SENTRY_DSN;

    if (!dsn) {
        console.info('[ErrorReporting] No DSN configured, using console fallback');
        isInitialized = true;
        return;
    }

    // Uncomment when Sentry is installed:
    // Sentry.init({
    //     dsn,
    //     environment: import.meta.env.MODE,
    //     release: `beatsight-web@${import.meta.env.VITE_APP_VERSION || '0.0.0'}`,
    //     tracesSampleRate: import.meta.env.PROD ? 0.1 : 1.0,
    //     replaysSessionSampleRate: 0.1,
    //     replaysOnErrorSampleRate: 1.0,
    //     integrations: [
    //         Sentry.browserTracingIntegration(),
    //         Sentry.replayIntegration(),
    //     ],
    //     beforeSend(event) {
    //         // Filter out development errors
    //         if (import.meta.env.DEV) {
    //             console.log('[Sentry] Would send event:', event);
    //             return null;
    //         }
    //         return event;
    //     },
    // });

    console.info('[ErrorReporting] Initialized');
    isInitialized = true;
}

/**
 * Set the current user for error context.
 */
export function setUser(user: UserContext | null): void {
    currentUser = user;

    // Uncomment when Sentry is installed:
    // if (user) {
    //     Sentry.setUser({
    //         id: user.id,
    //         email: user.email,
    //         username: user.username,
    //     });
    // } else {
    //     Sentry.setUser(null);
    // }
}

/**
 * Capture and report an error.
 */
export function captureError(error: Error, context?: ErrorContext): void {
    const enrichedContext = {
        ...context,
        user: currentUser,
        url: window.location.href,
        timestamp: new Date().toISOString(),
    };

    // Always log errors (they're important for debugging)
     
    console.error('[ErrorReporting] Captured error:', error, enrichedContext);

    // Uncomment when Sentry is installed:
    // Sentry.captureException(error, {
    //     extra: enrichedContext,
    // });
}

/**
 * Capture a message/breadcrumb.
 */
export function captureMessage(message: string, level: 'info' | 'warning' | 'error' = 'info', context?: ErrorContext): void {
    const enrichedContext = {
        ...context,
        user: currentUser,
        timestamp: new Date().toISOString(),
    };

    // Only log in development for non-errors
    const isDev = import.meta.env.DEV;

    if (level === 'error') {
         
        console.error('[ErrorReporting]', message, enrichedContext);
    } else if (level === 'warning' && isDev) {
         
        console.warn('[ErrorReporting]', message, enrichedContext);
    } else if (isDev) {
         
        console.info('[ErrorReporting]', message, enrichedContext);
    }

    // Uncomment when Sentry is installed:
    // Sentry.captureMessage(message, {
    //     level: level as Sentry.SeverityLevel,
    //     extra: enrichedContext,
    // });
}

/**
 * Add a breadcrumb for debugging.
 */
export function addBreadcrumb(_message: string, _category: string, _data?: Record<string, unknown>): void {
    // Uncomment when Sentry is installed:
    // Sentry.addBreadcrumb({
    //     message: _message,
    //     category: _category,
    //     data: _data,
    //     level: 'info',
    // });
}

/**
 * Start a performance transaction.
 */
export function startTransaction(name: string, op: string): { finish: () => void } {
    const startTime = performance.now();

    // Uncomment when Sentry is installed:
    // const transaction = Sentry.startTransaction({ name, op });
    // Sentry.getCurrentHub().getScope()?.setSpan(transaction);

    return {
        finish: () => {
            const duration = performance.now() - startTime;
            console.debug(`[Performance] ${name} (${op}): ${duration.toFixed(2)}ms`);
            // transaction.finish();
        }
    };
}

/**
 * Error boundary wrapper component props.
 */
interface ErrorBoundaryProps {
    children: React.ReactNode;
    fallback?: React.ReactNode;
    onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
}

/**
 * Simple error boundary for React components.
 * Use Sentry.ErrorBoundary when Sentry is installed for better integration.
 */
export class ErrorBoundary extends React.Component<
    ErrorBoundaryProps,
    { hasError: boolean; error: Error | null }
> {
    constructor(props: ErrorBoundaryProps) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error) {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
        captureError(error, {
            componentStack: errorInfo.componentStack,
        });
        this.props.onError?.(error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return this.props.fallback ?? (
                <div className="flex flex-col items-center justify-center min-h-[200px] p-8 text-center">
                    <h2 className="text-xl font-bold text-red-500 mb-2">Something went wrong</h2>
                    <p className="text-gray-600 mb-4">
                        An unexpected error occurred. Please try refreshing the page.
                    </p>
                    <button
                        onClick={() => this.setState({ hasError: false, error: null })}
                        className="px-4 py-2 bg-cyan-500 text-white rounded hover:bg-cyan-600"
                    >
                        Try Again
                    </button>
                </div>
            );
        }

        return this.props.children;
    }
}
