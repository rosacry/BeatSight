import { useEffect } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { Layout } from './components/NavigationShell'
import { ProtectedRoute } from './components/ProtectedRoute'
import { ErrorBoundary } from './components/ErrorBoundary'
import { InstallPrompt, OfflineIndicator, UpdateNotification } from './components/PWAPrompts'
import { ToastProvider } from './components/Toast'
import { AchievementNotificationProvider } from './components/AchievementToast'
import { HomePage } from './pages/HomePage'
import { DashboardPage } from './pages/DashboardPage'
import { LeaderboardPage } from './pages/LeaderboardPage'
import { JobQueuePage } from './pages/JobQueuePage'
import { JobDetailPage } from './pages/JobDetailPage'
import { UploadPage } from './pages/UploadPage'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { ForgotPasswordPage } from './pages/ForgotPasswordPage'
import { ResetPasswordPage } from './pages/ResetPasswordPage'
import { LibraryPage } from './pages/LibraryPage'
import { ProfilePage } from './pages/ProfilePage'
import { SettingsPage } from './pages/SettingsPage'
import { PricingPage } from './pages/PricingPage'
import { AdminDashboardPage } from './pages/AdminDashboardPage'
import { VerifierDashboardPage } from './pages/VerifierDashboardPage'
import { MapEditPage } from './pages/MapEditPage'
import { RecordPage } from './pages/RecordPage'
import { CreditSuccessPage } from './pages/CreditSuccessPage'
import { CreditCancelPage } from './pages/CreditCancelPage'
import { ForumPage } from './pages/ForumPage'
import { ForumViewPage } from './pages/ForumViewPage'
import { TopicViewPage } from './pages/TopicViewPage'
import { useAuthStore } from './stores/authStore'
import { useServiceWorkerUpdate } from './hooks/usePWA'
import { KeyboardShortcutsProvider } from './hooks/useKeyboardShortcuts'
import { forceUnlockBodyScroll } from './lib/bodyScrollLock'

// Page transition animation variants
const pageVariants = {
    initial: { opacity: 0, y: 8 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -8 },
}

const pageTransition = {
    duration: 0.2,
    ease: [0.25, 0.46, 0.45, 0.94],
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
            <div className="min-h-[60vh] flex items-center justify-center">
                <div className="flex flex-col items-center gap-4">
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
            <AnimatePresence mode="popLayout">
                <motion.div
                    key={location.pathname}
                    initial="initial"
                    animate="animate"
                    exit="exit"
                    variants={pageVariants}
                    transition={pageTransition}
                    className="min-h-full"
                >
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
                                <ProtectedRoute>
                                    <SettingsPage />
                                </ProtectedRoute>
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
                    </Routes>
                </motion.div>
            </AnimatePresence>
        </>
    )
}

function App() {
    const initialize = useAuthStore((state) => state.initialize)
    const { updateAvailable, applyUpdate } = useServiceWorkerUpdate()

    // Initialize auth state on app load
    useEffect(() => {
        initialize()
    }, [initialize])

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
                            <ErrorBoundary>
                                <AnimatedRoutes />
                            </ErrorBoundary>
                        </Layout>
                    </KeyboardShortcutsProvider>
                </AchievementNotificationProvider>
            </ToastProvider>
        </ErrorBoundary>
    )
}

export default App
