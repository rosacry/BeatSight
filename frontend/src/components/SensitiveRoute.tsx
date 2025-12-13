/**
 * Sensitive route wrapper that requires session verification.
 * 
 * Similar to osu!'s approach: when users access sensitive areas
 * (settings, credits, etc.) after a period of inactivity, they
 * must verify their identity via email code.
 * 
 * This wraps ProtectedRoute with an additional verification check.
 */

import { useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { useVerificationStore } from '@/stores/verificationStore'

interface SensitiveRouteProps {
    children: React.ReactNode
}

export function SensitiveRoute({ children }: SensitiveRouteProps) {
    const location = useLocation()
    const isAuthenticated = useAuthStore((state) => state.isAuthenticated())
    const isAuthLoading = useAuthStore((state) => state.isLoading)
    const hasHydrated = useAuthStore((state) => state._hasHydrated)

    const needsVerification = useVerificationStore((state) => state.needsVerification())
    const isVerified = useVerificationStore((state) => state.isVerified)
    const checkVerificationStatus = useVerificationStore((state) => state.checkVerificationStatus)

    const [isChecking, setIsChecking] = useState(true)
    const [shouldVerify, setShouldVerify] = useState(false)

    // Build full path for redirect-back functionality
    const fullPath = location.pathname + location.search

    // Check verification status on mount
    useEffect(() => {
        async function checkStatus() {
            if (!isAuthenticated) {
                setIsChecking(false)
                return
            }

            // If local state says we're verified and not expired, skip API check
            if (isVerified && !needsVerification) {
                setIsChecking(false)
                setShouldVerify(false)
                return
            }

            // Otherwise, check with backend
            const verified = await checkVerificationStatus()
            setShouldVerify(!verified)
            setIsChecking(false)
        }

        if (hasHydrated && !isAuthLoading) {
            checkStatus()
        }
    }, [isAuthenticated, isVerified, needsVerification, hasHydrated, isAuthLoading, checkVerificationStatus])

    // Show loading while checking auth or verification status
    if (isAuthLoading || !hasHydrated || isChecking) {
        return (
            <div className="min-h-[60vh] flex items-center justify-center">
                <div className="flex flex-col items-center gap-4">
                    <svg className="animate-spin h-8 w-8 text-primary-500" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    <p className="text-gray-400">Checking verification status...</p>
                </div>
            </div>
        )
    }

    // Redirect to login if not authenticated
    if (!isAuthenticated) {
        return <Navigate to="/login" state={{ from: fullPath }} replace />
    }

    // Redirect to verification if session needs verification
    if (shouldVerify) {
        return (
            <Navigate
                to="/account/verify"
                state={{ from: fullPath }}
                replace
            />
        )
    }

    return <>{children}</>
}

export default SensitiveRoute
