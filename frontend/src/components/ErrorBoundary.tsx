/**
 * Error boundary component.
 * Catches JavaScript errors in child components and displays a fallback UI.
 */

import { Component, ErrorInfo, ReactNode } from 'react'
import { captureError } from '../lib/errorReporting'

interface Props {
    children: ReactNode
    fallback?: ReactNode
}

interface State {
    hasError: boolean
    error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
    constructor(props: Props) {
        super(props)
        this.state = { hasError: false, error: null }
    }

    static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error }
    }

    componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error('Error caught by boundary:', error, errorInfo)
        // Send to error reporting service
        captureError(error, {
            componentStack: errorInfo.componentStack,
            boundary: 'ErrorBoundary',
        })
    }

    render() {
        if (this.state.hasError) {
            if (this.props.fallback) {
                return this.props.fallback
            }

            return (
                <div className="min-h-[60vh] flex items-center justify-center p-4">
                    <div className="max-w-md text-center">
                        <div className="w-16 h-16 bg-red-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
                            <svg className="w-8 h-8 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                        </div>
                        <h2 className="text-xl font-semibold text-white mb-2">Something went wrong</h2>
                        <p className="text-gray-400 mb-6">
                            Something went wrong. Try refreshing the page.
                        </p>
                        <div className="space-y-3">
                            <button
                                onClick={() => window.location.reload()}
                                className="btn btn-primary w-full"
                            >
                                Refresh Page
                            </button>
                            <button
                                onClick={() => this.setState({ hasError: false, error: null })}
                                className="btn btn-secondary w-full"
                            >
                                Try Again
                            </button>
                        </div>
                        {import.meta.env.DEV && this.state.error && (
                            <details className="mt-6 text-left">
                                <summary className="text-sm text-gray-500 cursor-pointer hover:text-gray-400">
                                    Error Details (Dev Only)
                                </summary>
                                <pre className="mt-2 p-4 bg-dark-400 rounded-lg text-xs text-red-400 overflow-auto">
                                    {this.state.error.message}
                                    {'\n\n'}
                                    {this.state.error.stack}
                                </pre>
                            </details>
                        )}
                    </div>
                </div>
            )
        }

        return this.props.children
    }
}

/**
 * Loading spinner component.
 */
interface LoadingSpinnerProps {
    size?: 'sm' | 'md' | 'lg'
    text?: string
}

export function LoadingSpinner({ size = 'md', text }: LoadingSpinnerProps) {
    const sizeClasses = {
        sm: 'h-4 w-4',
        md: 'h-8 w-8',
        lg: 'h-12 w-12',
    }

    return (
        <div className="flex flex-col items-center justify-center gap-3">
            <svg
                className={`animate-spin text-primary-500 ${sizeClasses[size]}`}
                viewBox="0 0 24 24"
            >
                <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                    fill="none"
                />
                <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
            </svg>
            {text && <p className="text-gray-400 text-sm">{text}</p>}
        </div>
    )
}

/**
 * Full page loading state.
 */
interface PageLoaderProps {
    text?: string
}

export function PageLoader({ text = 'Loading...' }: PageLoaderProps) {
    return (
        <div className="min-h-[60vh] flex items-center justify-center">
            <LoadingSpinner size="lg" text={text} />
        </div>
    )
}

/**
 * Empty state component.
 */
interface EmptyStateProps {
    icon?: ReactNode
    title: string
    description?: string
    action?: ReactNode
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
    return (
        <div className="text-center py-12">
            {icon && <div className="mb-4">{icon}</div>}
            <h3 className="text-lg font-medium text-white mb-2">{title}</h3>
            {description && <p className="text-gray-400 mb-6 max-w-md mx-auto">{description}</p>}
            {action}
        </div>
    )
}
