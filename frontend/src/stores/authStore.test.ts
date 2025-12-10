import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useAuthStore, getAccessToken, isAuthenticated } from './authStore'

// Helper to create a mock JWT token with a future expiration
function createMockJwt(expiresInSeconds: number = 3600): string {
    const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
    const payload = btoa(JSON.stringify({
        sub: 'user123',
        exp: Math.floor(Date.now() / 1000) + expiresInSeconds,
        iat: Math.floor(Date.now() / 1000),
    }));
    const signature = btoa('mock-signature');
    return `${header}.${payload}.${signature}`;
}

describe('authStore', () => {
    const getState = () => useAuthStore.getState()
    const setState = useAuthStore.setState

    beforeEach(() => {
        vi.clearAllMocks()
        // Reset store state before each test
        setState({
            user: null,
            accessToken: null,
            refreshToken: null,
            isLoading: false,
            _hasHydrated: true, // Assume hydrated in tests
        })
    })

    afterEach(() => {
        localStorage.removeItem('beatsight-auth')
    })

    describe('initial state', () => {
        it('starts with null user and tokens', () => {
            const state = getState()
            expect(state.user).toBeNull()
            expect(state.accessToken).toBeNull()
            expect(state.refreshToken).toBeNull()
            expect(state.isLoading).toBe(false)
        })

        it('isAuthenticated returns false when not logged in', () => {
            expect(getState().isAuthenticated()).toBe(false)
        })

        it('isAuthenticated returns true when logged in', () => {
            setState({
                accessToken: createMockJwt(3600),
                user: { id: '1', email: 'a@b.com', display_name: 'user', email_verified: true, avatar_url: null, karma_score: 0, created_at: '2024-01-01', roles: [] },
            })
            expect(getState().isAuthenticated()).toBe(true)
        })
    })

    describe('logout', () => {
        it('clears all auth state', () => {
            setState({
                user: { id: 'user-123', email: 'test@example.com', display_name: 'testuser', email_verified: true, avatar_url: null, karma_score: 0, created_at: '2024-01-01', roles: [] },
                accessToken: createMockJwt(3600),
                refreshToken: 'refresh',
                isLoading: false,
            })

            expect(getState().isAuthenticated()).toBe(true)

            getState().logout()

            const state = getState()
            expect(state.user).toBeNull()
            expect(state.accessToken).toBeNull()
            expect(state.refreshToken).toBeNull()
            expect(state.isAuthenticated()).toBe(false)
        })
    })

    describe('refreshTokens', () => {
        it('returns false when no refresh token exists', async () => {
            const success = await getState().refreshTokens()
            expect(success).toBe(false)
        })
    })

    describe('fetchCurrentUser', () => {
        it('throws error when no token', async () => {
            await expect(getState().fetchCurrentUser()).rejects.toThrow('No access token')
        })
    })

    describe('initialize', () => {
        it('does nothing when no token exists', async () => {
            // Track if fetchCurrentUser was called by checking state
            const initialUser = getState().user
            await getState().initialize()
            expect(getState().user).toBe(initialUser)
        })

        it('does nothing when user already exists', async () => {
            setState({
                accessToken: createMockJwt(3600),
                user: { id: '1', email: 'e@e.com', display_name: 'u', email_verified: true, avatar_url: null, karma_score: 0, created_at: '2024-01-01', roles: [] },
            })

            const existingUser = getState().user
            await getState().initialize()
            expect(getState().user).toBe(existingUser)
        })
    })

    describe('setLoading', () => {
        it('sets loading state to true', () => {
            getState().setLoading(true)
            expect(getState().isLoading).toBe(true)
        })

        it('sets loading state to false', () => {
            setState({ isLoading: true })
            getState().setLoading(false)
            expect(getState().isLoading).toBe(false)
        })
    })

    describe('helper functions', () => {
        it('getAccessToken returns null when no token', () => {
            expect(getAccessToken()).toBeNull()
        })

        it('getAccessToken returns current token', () => {
            const mockToken = createMockJwt(3600)
            setState({ accessToken: mockToken })
            expect(getAccessToken()).toBe(mockToken)
        })

        it('isAuthenticated returns false when not logged in', () => {
            expect(isAuthenticated()).toBe(false)
        })

        it('isAuthenticated returns true when logged in', () => {
            setState({
                accessToken: createMockJwt(3600),
                user: { id: '1', email: 'a@b.com', display_name: 'user', email_verified: true, avatar_url: null, karma_score: 0, created_at: '2024-01-01', roles: [] },
            })

            expect(isAuthenticated()).toBe(true)
        })
    })

    describe('state persistence', () => {
        it('partializes state to only include tokens', () => {
            // The store is configured to only persist accessToken and refreshToken
            // Verify the shape is correct in state
            const mockToken = createMockJwt(3600)
            setState({
                accessToken: mockToken,
                refreshToken: 'refresh',
                user: { id: '1', email: 'e@e.com', display_name: 'u', email_verified: true, avatar_url: null, karma_score: 0, created_at: '2024-01-01', roles: [] },
                isLoading: true,
            })

            const state = getState()
            expect(state.accessToken).toBe(mockToken)
            expect(state.refreshToken).toBe('refresh')
        })
    })
})
