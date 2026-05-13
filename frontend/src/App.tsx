import { Suspense, lazy, useEffect } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { Layout } from './components/NavigationShell'
import { ProtectedRoute } from './components/ProtectedRoute'
import { SensitiveRoute } from './components/SensitiveRoute'
import { ErrorBoundary } from './components/ErrorBoundary'
import { InstallPrompt, OfflineIndicator, UpdateNotification } from './components/PWAPrompts'
import { ToastProvider } from './components/Toast'
import { AchievementNotificationProvider } from './components/AchievementToast'
import { useAuthStore } from './stores/authStore'
import { useFeaturesStore } from './stores/featuresStore'
import { useServiceWorkerUpdate } from './hooks/usePWA'
import { KeyboardShortcutsProvider } from './hooks/useKeyboardShortcuts'
import { forceUnlockBodyScroll } from './lib/bodyScrollLock'
import {
    pageVariants as unifiedPageVariants,
    TRANSITION_DURATION
} from './components/ui/UnifiedTransitions'

// Page transition animation variants - using unified system
const pageVariants = unifiedPageVariants

const pageTransition = {
    duration: TRANSITION_DURATION,
    ease: 'easeOut',
}

// Route-level lazy loading keeps initial bundle smaller and pushes heavy pages
// to on-demand chunks when routes are visited.
const HomePage = lazy(() => import('./pages/HomePage').then((m) => ({ default: m.HomePage })))
const DashboardPage = lazy(() => import('./pages/DashboardPage').then((m) => ({ default: m.DashboardPage })))
const LeaderboardPage = lazy(() => import('./pages/LeaderboardPage').then((m) => ({ default: m.LeaderboardPage })))
const JobQueuePage = lazy(() => import('./pages/JobQueuePage').then((m) => ({ default: m.JobQueuePage })))
const JobDetailPage = lazy(() => import('./pages/JobDetailPage').then((m) => ({ default: m.JobDetailPage })))
const UploadPage = lazy(() => import('./pages/UploadPage').then((m) => ({ default: m.UploadPage })))
const LoginPage = lazy(() => import('./pages/LoginPage').then((m) => ({ default: m.LoginPage })))
const RegisterPage = lazy(() => import('./pages/RegisterPage').then((m) => ({ default: m.RegisterPage })))
const ForgotPasswordPage = lazy(() => import('./pages/ForgotPasswordPage').then((m) => ({ default: m.ForgotPasswordPage })))
const ResetPasswordPage = lazy(() => import('./pages/ResetPasswordPage').then((m) => ({ default: m.ResetPasswordPage })))
const LibraryPage = lazy(() => import('./pages/LibraryPage').then((m) => ({ default: m.LibraryPage })))
const ProfilePage = lazy(() => import('./pages/ProfilePage').then((m) => ({ default: m.ProfilePage })))
const UserProfilePage = lazy(() => import('./pages/UserProfilePage').then((m) => ({ default: m.UserProfilePage })))
const SettingsPage = lazy(() => import('./pages/SettingsPage').then((m) => ({ default: m.SettingsPage })))
const PricingPage = lazy(() => import('./pages/PricingPage').then((m) => ({ default: m.PricingPage })))
const AdminDashboardPage = lazy(() => import('./pages/AdminDashboardPage').then((m) => ({ default: m.AdminDashboardPage })))
const VerifierDashboardPage = lazy(() => import('./pages/VerifierDashboardPage').then((m) => ({ default: m.VerifierDashboardPage })))
const MapEditPage = lazy(() => import('./pages/MapEditPage').then((m) => ({ default: m.MapEditPage })))
const RecordPage = lazy(() => import('./pages/RecordPage').then((m) => ({ default: m.RecordPage })))
const CreditSuccessPage = lazy(() => import('./pages/CreditSuccessPage').then((m) => ({ default: m.CreditSuccessPage })))
const CreditCancelPage = lazy(() => import('./pages/CreditCancelPage').then((m) => ({ default: m.CreditCancelPage })))
const ForumPage = lazy(() => import('./pages/ForumPage').then((m) => ({ default: m.ForumPage })))
const ForumViewPage = lazy(() => import('./pages/ForumViewPage').then((m) => ({ default: m.ForumViewPage })))
const TopicViewPage = lazy(() => import('./pages/TopicViewPage').then((m) => ({ default: m.TopicViewPage })))
const MessagesPage = lazy(() => import('./pages/MessagesPage'))
const AccountVerificationPage = lazy(
    () => import('./pages/AccountVerificationPage').then((m) => ({ default: m.AccountVerificationPage }))
)
const VerificationSuccessPage = lazy(
    () => import('./pages/AccountVerificationPage').then((m) => ({ default: m.VerificationSuccessPage }))
)
const VerificationInvalidPage = lazy(
    () => import('./pages/AccountVerificationPage').then((m) => ({ default: m.VerificationInvalidPage }))
)

function RouteLoadingFallback() {
    return (
        <div className="min-h-[60vh] flex items-center justify-center">
            <svg className="animate-spin h-8 w-8 text-primary-500" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
        </div>
    )
}

// Scroll restoration and modal cleanup component - runs on route change
function ScrollToTop() {
    const { pathname } = useLocation()

    useEffect(() => {
        // Scroll to top
        window.scrollTo(0, 0)

        // Force unlock all body scroll locks on navigation
        // This is a safety net that catches any dialogs/modals that didn't clean up properly
        forceUnlockBodyScroll()

        // Additional delayed cleanup to catch race conditions with exit animations
        // Some modals use AnimatePresence which can delay cleanup
        const timeoutId = setTimeout(() => {
            forceUnlockBodyScroll()
        }, 150)

        return () => clearTimeout(timeoutId)
    }, [pathname])

    return null
}

// Auth-aware home page - shows Dashboard for logged in users, HomePage for guests
// Similar to osu!'s behavior where logged in users see their personalized dashboard
function AuthAwareHome() {
    const isAuthenticated = useAuthStore((state) => state.isAuthenticated())
    const isLoading = useAuthStore((state) => state.isLoading)
    const hasHydrated = useAuthStore((state) => state._hasHydrated)

    // Show loading while auth state is being determined
    // This prevents the flash of HomePage for logged-in users
    if (isLoading || !hasHydrated) {
        return (
            <div className="relative min-h-screen">
                {/* Dark background to prevent any flash */}
                <div className="fixed inset-0 bg-gradient-to-b from-dark-500 via-dark-500 to-black" />

                {/* Centered loading spinner */}
                <div className="relative z-10 flex items-center justify-center min-h-[60vh]">
                    <svg className="animate-spin h-8 w-8 text-primary-500" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                </div>
            </div>
        )
    }

    if (isAuthenticated) {
        return <DashboardPage />
    }

    return <HomePage />
}

function AnimatedRoutes() {
    const location = useLocation()

    return (
        <>
            <ScrollToTop />
            <AnimatePresence mode="wait" initial={false}>
                <motion.div
                    key={location.pathname}
                    initial="initial"
                    animate="animate"
                    exit="exit"
                    variants={pageVariants}
                    transition={pageTransition}
                    className="min-h-full"
                >
                    <Suspense fallback={<RouteLoadingFallback />}>
                        <Routes location={location}>
                            {/* Public routes */}
                            <Route path="/" element={<AuthAwareHome />} />
                            <Route path="/queue" element={<JobQueuePage />} />
                            <Route path="/jobs/:jobId" element={<JobDetailPage />} />
                            <Route path="/login" element={<LoginPage />} />
                            <Route path="/register" element={<RegisterPage />} />
                            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
                            <Route path="/reset-password" element={<ResetPasswordPage />} />
                            <Route path="/pricing" element={<PricingPage />} />
                            <Route path="/credits/success" element={<CreditSuccessPage />} />
                            <Route path="/credits/cancel" element={<CreditCancelPage />} />
                            <Route path="/leaderboard" element={<LeaderboardPage />} />

                            {/* Account verification routes (osu!-style) */}
                            <Route
                                path="/account/verify"
                                element={
                                    <ProtectedRoute>
                                        <AccountVerificationPage />
                                    </ProtectedRoute>
                                }
                            />
                            <Route path="/account/verify/success" element={<VerificationSuccessPage />} />
                            <Route path="/account/verify/invalid" element={<VerificationInvalidPage />} />

                            {/* Public user profile */}
                            <Route path="/user/:userId" element={<UserProfilePage />} />

                            {/* Forum routes (public, posting requires auth) */}
                            <Route path="/forum" element={<ForumPage />} />
                            <Route path="/forum/:forumId" element={<ForumViewPage />} />
                            <Route path="/forum/topics/:topicId" element={<TopicViewPage />} />

                            {/* Protected routes */}
                            <Route
                                path="/upload"
                                element={
                                    <ProtectedRoute>
                                        <UploadPage />
                                    </ProtectedRoute>
                                }
                            />
                            <Route
                                path="/library"
                                element={
                                    <ProtectedRoute>
                                        <LibraryPage />
                                    </ProtectedRoute>
                                }
                            />
                            <Route
                                path="/profile"
                                element={
                                    <ProtectedRoute>
                                        <ProfilePage />
                                    </ProtectedRoute>
                                }
                            />
                            <Route
                                path="/settings"
                                element={
                                    <SensitiveRoute>
                                        <SettingsPage />
                                    </SensitiveRoute>
                                }
                            />
                            <Route
                                path="/admin"
                                element={
                                    <ProtectedRoute requiredRoles={['staff', 'admin']}>
                                        <AdminDashboardPage />
                                    </ProtectedRoute>
                                }
                            />
                            <Route
                                path="/verifier"
                                element={
                                    <ProtectedRoute requiredRoles={['verifier', 'staff', 'admin']}>
                                        <VerifierDashboardPage />
                                    </ProtectedRoute>
                                }
                            />
                            <Route
                                path="/maps/:mapId/edit"
                                element={
                                    <ProtectedRoute>
                                        <MapEditPage />
                                    </ProtectedRoute>
                                }
                            />
                            <Route
                                path="/record"
                                element={
                                    <ProtectedRoute>
                                        <RecordPage />
                                    </ProtectedRoute>
                                }
                            />

                            {/* Messages routes */}
                            <Route
                                path="/messages"
                                element={
                                    <ProtectedRoute>
                                        <MessagesPage />
                                    </ProtectedRoute>
                                }
                            />
                            <Route
                                path="/messages/:partnerId"
                                element={
                                    <ProtectedRoute>
                                        <MessagesPage />
                                    </ProtectedRoute>
                                }
                            />
                        </Routes>
                    </Suspense>
                </motion.div>
            </AnimatePresence>
        </>
    )
}

function App() {
    const initialize = useAuthStore((state) => state.initialize)
    const fetchFeatures = useFeaturesStore((state) => state.fetchFeatures)
    const { updateAvailable, applyUpdate } = useServiceWorkerUpdate()

    // Initialize auth state and fetch features on app load
    useEffect(() => {
        initialize()
        fetchFeatures()
    }, [initialize, fetchFeatures])

    return (
        <ErrorBoundary>
            <ToastProvider>
                <AchievementNotificationProvider>
                    <KeyboardShortcutsProvider>
                        {/* PWA Components */}
                        <OfflineIndicator />
                        <InstallPrompt />
                        {updateAvailable && <UpdateNotification onUpdate={applyUpdate} />}

                        <Layout>
                            <AnimatedRoutesWithErrorBoundary />
                        </Layout>
                    </KeyboardShortcutsProvider>
                </AchievementNotificationProvider>
            </ToastProvider>
        </ErrorBoundary>
    )
}

/**
 * Wrapper that provides an ErrorBoundary that resets on navigation.
 * Uses location.key as the ErrorBoundary key so that navigating away
 * from an error page clears the error state.
 */
function AnimatedRoutesWithErrorBoundary() {
    const location = useLocation()

    return (
        <ErrorBoundary key={location.key}>
            <AnimatedRoutes />
        </ErrorBoundary>
    )
}

export default App
