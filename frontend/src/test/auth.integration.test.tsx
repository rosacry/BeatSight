import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '../test/utils';
import userEvent from '@testing-library/user-event';
import { LoginPage } from '../pages/LoginPage';
import { RegisterPage } from '../pages/RegisterPage';
import { useAuthStore } from '../stores/authStore';

// Helper to create a mock JWT token with a future expiration
function createMockJwt(expiresInSeconds: number = 3600): string {
    const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
    const payload = btoa(JSON.stringify({
        sub: 'user123',
        exp: Math.floor(Date.now() / 1000) + expiresInSeconds,
        iat: Math.floor(Date.now() / 1000),
    }));
    // Mock signature (not actually valid, but good enough for tests)
    const signature = btoa('mock-signature');
    return `${header}.${payload}.${signature}`;
}

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
    const actual = await vi.importActual('react-router-dom');
    return {
        ...actual,
        useNavigate: () => mockNavigate,
        useLocation: () => ({ state: null }),
    };
});

describe('Authentication Integration Tests', () => {
    beforeEach(() => {
        // Reset auth store before each test
        useAuthStore.setState({
            user: null,
            accessToken: null,
            refreshToken: null,
            isLoading: false,
        });
        mockNavigate.mockClear();
        localStorage.clear();
    });

    describe('LoginPage', () => {
        it('renders login form correctly', () => {
            render(<LoginPage />);

            expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
            expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
            expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
        });

        it('shows validation errors for empty fields', async () => {
            const user = userEvent.setup();
            render(<LoginPage />);

            const submitButton = screen.getByRole('button', { name: /sign in/i });
            await user.click(submitButton);

            // HTML5 validation should prevent submission
            expect(screen.getByLabelText(/email/i)).toBeInvalid();
        });

        it('successfully logs in with valid credentials', async () => {
            const user = userEvent.setup();
            render(<LoginPage />);

            await user.type(screen.getByLabelText(/email/i), 'test@example.com');
            await user.type(screen.getByLabelText(/password/i), 'password123');
            await user.click(screen.getByRole('button', { name: /sign in/i }));

            await waitFor(() => {
                const token = useAuthStore.getState().accessToken;
                // Token should be a JWT (three base64 parts separated by dots)
                expect(token).not.toBeNull();
                expect(token?.split('.').length).toBe(3);
            }, { timeout: 3000 });

            expect(mockNavigate).toHaveBeenCalled();
        });

        it('shows error message for invalid credentials', async () => {
            const user = userEvent.setup();
            render(<LoginPage />);

            await user.type(screen.getByLabelText(/email/i), 'wrong@example.com');
            await user.type(screen.getByLabelText(/password/i), 'wrongpassword');
            await user.click(screen.getByRole('button', { name: /sign in/i }));

            await waitFor(() => {
                expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument();
            }, { timeout: 3000 });
        });

        it('has link to registration page', () => {
            render(<LoginPage />);

            const registerLink = screen.getByRole('link', { name: /sign up/i });
            expect(registerLink).toHaveAttribute('href', '/register');
        });
    });

    describe('RegisterPage', () => {
        it('renders registration form correctly', () => {
            render(<RegisterPage />);

            expect(screen.getByLabelText(/display name/i)).toBeInTheDocument();
            expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
            expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
            expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
            expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument();
        });

        it('shows error when passwords do not match', async () => {
            const user = userEvent.setup();
            render(<RegisterPage />);

            await user.type(screen.getByLabelText(/display name/i), 'New User');
            await user.type(screen.getByLabelText(/email/i), 'new@example.com');
            await user.type(screen.getByLabelText(/^password$/i), 'password123');
            await user.type(screen.getByLabelText(/confirm password/i), 'different123');
            await user.click(screen.getByRole('button', { name: /create account/i }));

            await waitFor(() => {
                expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument();
            });
        });

        it('successfully registers with valid data', async () => {
            const user = userEvent.setup();
            render(<RegisterPage />);

            await user.type(screen.getByLabelText(/display name/i), 'New User');
            await user.type(screen.getByLabelText(/email/i), 'new@example.com');
            await user.type(screen.getByLabelText(/^password$/i), 'password123');
            await user.type(screen.getByLabelText(/confirm password/i), 'password123');
            await user.click(screen.getByRole('button', { name: /create account/i }));

            await waitFor(() => {
                expect(useAuthStore.getState().accessToken).toBeDefined();
            }, { timeout: 3000 });

            expect(mockNavigate).toHaveBeenCalled();
        });

        it('has link to login page', () => {
            render(<RegisterPage />);

            const loginLink = screen.getByRole('link', { name: /sign in/i });
            expect(loginLink).toHaveAttribute('href', '/login');
        });
    });

    describe('Auth State Management', () => {
        it('persists tokens to store on login', async () => {
            const user = userEvent.setup();
            render(<LoginPage />);

            await user.type(screen.getByLabelText(/email/i), 'test@example.com');
            await user.type(screen.getByLabelText(/password/i), 'password123');
            await user.click(screen.getByRole('button', { name: /sign in/i }));

            await waitFor(() => {
                const state = useAuthStore.getState();
                // Token should be a valid JWT format
                expect(state.accessToken?.split('.').length).toBe(3);
                expect(state.refreshToken).toBe('mock-refresh-token');
            }, { timeout: 3000 });
        });

        it('clears tokens on logout', async () => {
            // Set up authenticated state with valid mock JWT
            useAuthStore.setState({
                user: { id: '1', email: 'test@example.com', display_name: 'Test', email_verified: true, avatar_url: null, karma_score: 0, created_at: '2024-01-01' },
                accessToken: createMockJwt(3600),
                refreshToken: 'mock-refresh-token',
                isLoading: false,
            });

            // Verify authenticated
            expect(useAuthStore.getState().accessToken).not.toBeNull();

            // Logout
            useAuthStore.getState().logout();

            // Verify cleared
            expect(useAuthStore.getState().accessToken).toBeNull();
            expect(useAuthStore.getState().user).toBeNull();
        });

        it('isAuthenticated returns correct value', () => {
            // Not authenticated initially
            expect(useAuthStore.getState().isAuthenticated()).toBe(false);

            // Set authenticated state with a valid mock JWT
            useAuthStore.setState({
                user: { id: '1', email: 'test@example.com', display_name: 'Test', email_verified: true, avatar_url: null, karma_score: 0, created_at: '2024-01-01' },
                accessToken: createMockJwt(3600), // Valid for 1 hour
                refreshToken: 'mock-refresh-token',
                isLoading: false,
            });

            expect(useAuthStore.getState().isAuthenticated()).toBe(true);
        });
    });
});
