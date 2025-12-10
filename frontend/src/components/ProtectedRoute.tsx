/**
 * Protected route wrapper.
 * Redirects unauthenticated users to login page.
 * Optionally requires specific roles.
 */

import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import type { UserRole } from '@/types/auth'

interface ProtectedRouteProps {
    children: React.ReactNode
    /** If specified, user must have at least one of these roles */
    requiredRoles?: UserRole[]
}

export function ProtectedRoute({ children, requiredRoles }: ProtectedRouteProps) {
    const isAuthenticated = useAuthStore((state) => state.isAuthenticated())
    const isLoading = useAuthStore((state) => state.isLoading)
    const hasHydrated = useAuthStore((state) => state._hasHydrated)
    const hasRole = useAuthStore((state) => state.hasRole)
    const location = useLocation()

    // Build full path including search params for redirect-back functionality
    const fullPath = location.pathname + location.search

    // Show loading state while checking auth or waiting for hydration
    // This prevents the redirect flash to /login on page refresh
    if (isLoading || !hasHydrated) {
        return (
            <div className="min-h-[60vh] flex items-center justify-center">
                <div className="flex flex-col items-center gap-4">
                    <svg className="animate-spin h-8 w-8 text-primary-500" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    <p className="text-gray-400">Loading...</p>
                </div>
            </div>
        )
    }

    // Redirect to login if not authenticated
    if (!isAuthenticated) {
        return <Navigate to="/login" state={{ from: fullPath }} replace />
    }

    // Check role requirements if specified
    if (requiredRoles && requiredRoles.length > 0) {
        const hasRequiredRole = requiredRoles.some(role => hasRole(role))
        if (!hasRequiredRole) {
            // User is authenticated but doesn't have required role
            return (
                <div className="min-h-[60vh] flex items-center justify-center">
                    <div className="flex flex-col items-center gap-4 text-center p-8">
                        <div className="w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center">
                            <svg className="w-8 h-8 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                        </div>
                        <h2 className="text-xl font-semibold text-white">Access Denied</h2>
                        <p className="text-gray-400 max-w-md">
                            You don't have permission to access this page.
                            {requiredRoles.includes('admin') && ' This page requires admin privileges.'}
                            {requiredRoles.includes('verifier') && !requiredRoles.includes('admin') && ' This page requires verifier privileges.'}
                        </p>
                        <a href="/" className="mt-4 text-cyan-400 hover:text-cyan-300 transition-colors">
                            Return to home
                        </a>
                    </div>
                </div>
            )
        }
    }

    return <>{children}</>
}
