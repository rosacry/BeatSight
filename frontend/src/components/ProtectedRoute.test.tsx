/**
 * Tests for ProtectedRoute component.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'
import { ProtectedRoute } from './ProtectedRoute'

// Track location for redirect tests
let testLocation: ReturnType<typeof useLocation> | null = null
function LocationTracker() {
    testLocation = useLocation()
    return null
}

// Mock the auth store
const mockAuthState = {
    isAuthenticated: true,
    isLoading: false,
    _hasHydrated: true,
}

vi.mock('@/stores/authStore', () => ({
    useAuthStore: vi.fn((selector) => {
        const state = {
            isAuthenticated: () => mockAuthState.isAuthenticated,
            isLoading: mockAuthState.isLoading,
            _hasHydrated: mockAuthState._hasHydrated,
        }
        return selector(state)
    }),
}))

beforeEach(() => {
    mockAuthState.isAuthenticated = true
    mockAuthState.isLoading = false
    mockAuthState._hasHydrated = true
    testLocation = null
})

function renderWithRouter(initialRoute = '/protected') {
    return render(
        <MemoryRouter initialEntries={[initialRoute]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
            <Routes>
                <Route path="/login" element={<><div data-testid="login-page">Login Page</div><LocationTracker /></>} />
                <Route
                    path="/protected"
                    element={
                        <ProtectedRoute>
                            <div data-testid="protected-content">Protected Content</div>
                        </ProtectedRoute>
                    }
                />
            </Routes>
        </MemoryRouter>
    )
}

describe('ProtectedRoute', () => {
    it('renders children when authenticated', () => {
        mockAuthState.isAuthenticated = true
        mockAuthState.isLoading = false

        renderWithRouter()

        expect(screen.getByTestId('protected-content')).toBeInTheDocument()
        expect(screen.getByText('Protected Content')).toBeInTheDocument()
    })

    it('redirects to login when not authenticated', () => {
        mockAuthState.isAuthenticated = false
        mockAuthState.isLoading = false

        renderWithRouter()

        expect(screen.getByTestId('login-page')).toBeInTheDocument()
        expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument()
    })

    it('shows loading state while checking auth', () => {
        mockAuthState.isAuthenticated = false
        mockAuthState.isLoading = true

        renderWithRouter()

        expect(screen.getByText('Loading...')).toBeInTheDocument()
        expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument()
        expect(screen.queryByTestId('login-page')).not.toBeInTheDocument()
    })

    it('shows loading state while waiting for hydration', () => {
        mockAuthState.isAuthenticated = true
        mockAuthState.isLoading = false
        mockAuthState._hasHydrated = false

        renderWithRouter()

        expect(screen.getByText('Loading...')).toBeInTheDocument()
        expect(screen.queryByTestId('protected-content')).not.toBeInTheDocument()
        expect(screen.queryByTestId('login-page')).not.toBeInTheDocument()
    })

    it('shows spinner during loading', () => {
        mockAuthState.isLoading = true

        const { container } = renderWithRouter()

        // Check for spinning animation class
        const spinner = container.querySelector('.animate-spin')
        expect(spinner).toBeInTheDocument()
    })

    it('preserves original path in location state when redirecting', () => {
        mockAuthState.isAuthenticated = false
        mockAuthState.isLoading = false

        renderWithRouter('/protected')

        // Check that location state contains the original path
        expect(testLocation?.state).toEqual({ from: '/protected' })
    })

    it('renders nested children correctly', () => {
        mockAuthState.isAuthenticated = true
        mockAuthState.isLoading = false

        render(
            <MemoryRouter initialEntries={['/protected']} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
                <Routes>
                    <Route
                        path="/protected"
                        element={
                            <ProtectedRoute>
                                <div data-testid="parent">
                                    <span data-testid="child">Nested content</span>
                                </div>
                            </ProtectedRoute>
                        }
                    />
                </Routes>
            </MemoryRouter>
        )

        expect(screen.getByTestId('parent')).toBeInTheDocument()
        expect(screen.getByTestId('child')).toBeInTheDocument()
    })
})
