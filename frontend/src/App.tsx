import { useEffect } from 'react'
import { Routes, Route } from 'react-router-dom'
import { Layout } from './components/NavigationShell'
import { ProtectedRoute } from './components/ProtectedRoute'
import { ErrorBoundary } from './components/ErrorBoundary'
import { InstallPrompt, OfflineIndicator, UpdateNotification } from './components/PWAPrompts'
import { ToastProvider } from './components/Toast'
import { AchievementNotificationProvider } from './components/AchievementToast'
import { HomePage } from './pages/HomePage'
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
import { useAuthStore } from './stores/authStore'
import { useServiceWorkerUpdate } from './hooks/usePWA'
import { KeyboardShortcutsProvider } from './hooks/useKeyboardShortcuts'

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
                                <Routes>
                                    {/* Public routes */}
                                    <Route path="/" element={<HomePage />} />
                                    <Route path="/queue" element={<JobQueuePage />} />
                                    <Route path="/jobs/:jobId" element={<JobDetailPage />} />
                                    <Route path="/login" element={<LoginPage />} />
                                    <Route path="/register" element={<RegisterPage />} />
                                    <Route path="/forgot-password" element={<ForgotPasswordPage />} />
                                    <Route path="/reset-password" element={<ResetPasswordPage />} />
                                    <Route path="/pricing" element={<PricingPage />} />
                                    <Route path="/credits/success" element={<CreditSuccessPage />} />
                                    <Route path="/credits/cancel" element={<CreditCancelPage />} />

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
                                            <ProtectedRoute>
                                                <AdminDashboardPage />
                                            </ProtectedRoute>
                                        }
                                    />
                                    <Route
                                        path="/verifier"
                                        element={
                                            <ProtectedRoute>
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
                            </ErrorBoundary>
                        </Layout>
                    </KeyboardShortcutsProvider>
                </AchievementNotificationProvider>
            </ToastProvider>
        </ErrorBoundary>
    )
}

export default App
