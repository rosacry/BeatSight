import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'
import { registerServiceWorker } from './hooks/usePWA'
import { initErrorReporting, ErrorBoundary, captureError } from './lib/errorReporting'

// Initialize error reporting early
initErrorReporting();

const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            staleTime: 1000 * 60, // 1 minute
            gcTime: 1000 * 60 * 5, // 5 minutes garbage collection time
            retry: (failureCount, error) => {
                // Don't retry on auth errors or client errors
                if (error instanceof Error && 'status' in error) {
                    const status = (error as { status: number }).status
                    if (status === 401 || status === 403 || status === 404) {
                        return false
                    }
                }
                return failureCount < 2
            },
            retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
            refetchOnWindowFocus: import.meta.env.PROD, // Only in production
        },
        mutations: {
            retry: false, // Don't retry mutations by default
            onError: (error) => {
                // Report mutation errors to error tracking
                captureError(error instanceof Error ? error : new Error(String(error)), {
                    type: 'mutation',
                })
            },
        },
    },
})

// Register service worker for PWA support
if (import.meta.env.PROD) {
    registerServiceWorker()
}

ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
        <ErrorBoundary>
            <QueryClientProvider client={queryClient}>
                <BrowserRouter>
                    <App />
                </BrowserRouter>
            </QueryClientProvider>
        </ErrorBoundary>
    </React.StrictMode>,
)
