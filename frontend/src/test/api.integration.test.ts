import { describe, it, expect, beforeEach } from 'vitest';
import { useAuthStore } from '../stores/authStore';

// Simple fetch wrapper for testing API endpoints directly
const API_BASE = '/api';

class ApiError extends Error {
    constructor(public status: number, message: string) {
        super(message);
        this.name = 'ApiError';
    }
}

const apiClient = {
    async get<T = unknown>(endpoint: string): Promise<T> {
        const token = localStorage.getItem('access_token');
        const headers: Record<string, string> = {
            'Content-Type': 'application/json',
        };
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        const response = await fetch(endpoint.startsWith('/api') ? endpoint : `${API_BASE}${endpoint}`, { headers });
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
            throw new ApiError(response.status, error.detail || 'Request failed');
        }
        if (response.status === 204) return undefined as T;
        return response.json();
    },
    async post<T = unknown>(endpoint: string, body: unknown): Promise<T> {
        const token = localStorage.getItem('access_token');
        const headers: Record<string, string> = {
            'Content-Type': 'application/json',
        };
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        const response = await fetch(endpoint.startsWith('/api') ? endpoint : `${API_BASE}${endpoint}`, {
            method: 'POST',
            headers,
            body: JSON.stringify(body),
        });
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
            throw new ApiError(response.status, error.detail || 'Request failed');
        }
        if (response.status === 204) return undefined as T;
        return response.json();
    },
    async delete(endpoint: string): Promise<void> {
        const token = localStorage.getItem('access_token');
        const headers: Record<string, string> = {
            'Content-Type': 'application/json',
        };
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        const response = await fetch(endpoint.startsWith('/api') ? endpoint : `${API_BASE}${endpoint}`, {
            method: 'DELETE',
            headers,
        });
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
            throw new ApiError(response.status, error.detail || 'Request failed');
        }
    },
};

describe('API Client Integration Tests', () => {
    beforeEach(() => {
        useAuthStore.getState().logout();
        localStorage.clear();
    });

    describe('Health Check', () => {
        it('successfully calls health endpoint', async () => {
            const response = await apiClient.get<{ status: string }>('/health/live');
            expect(response.status).toBe('healthy');
        });
    });

    describe('Authentication API', () => {
        it('successfully logs in and stores tokens', async () => {
            interface LoginResponse {
                access_token: string;
                user: { email: string };
            }
            const response = await apiClient.post<LoginResponse>('/api/auth/login', {
                email: 'test@example.com',
                password: 'password123',
            });

            expect(response.access_token).toBe('mock-access-token');
            expect(response.user.email).toBe('test@example.com');
        });

        it('returns 401 for invalid credentials', async () => {
            try {
                await apiClient.post('/api/auth/login', {
                    email: 'wrong@example.com',
                    password: 'wrongpassword',
                });
                expect.fail('Should have thrown an error');
            } catch (error) {
                expect(error).toBeInstanceOf(ApiError);
                expect((error as ApiError).status).toBe(401);
            }
        });

        it('successfully registers new user', async () => {
            interface RegisterResponse {
                access_token: string;
            }
            const response = await apiClient.post<RegisterResponse>('/api/auth/register', {
                email: 'new@example.com',
                display_name: 'New User',
                password: 'password123',
            });

            expect(response.access_token).toBeDefined();
        });
    });

    describe('Protected Endpoints', () => {
        beforeEach(() => {
            // Setup authentication
            localStorage.setItem('access_token', 'mock-access-token');
            localStorage.setItem('refresh_token', 'mock-refresh-token');
        });

        it('successfully fetches current user', async () => {
            const response = await apiClient.get<{ email: string }>('/api/auth/me');
            expect(response.email).toBe('test@example.com');
        });

        it('successfully fetches songs list', async () => {
            interface SongsResponse {
                items: Array<{ title: string }>;
            }
            const response = await apiClient.get<SongsResponse>('/api/songs');

            expect(response.items).toBeDefined();
            expect(response.items.length).toBeGreaterThan(0);
            expect(response.items[0].title).toBe('Test Song 1');
        });

        it('successfully fetches single song', async () => {
            const response = await apiClient.get<{ title: string }>('/api/songs/1');
            expect(response.title).toBe('Test Song 1');
        });

        it('returns 404 for non-existent song', async () => {
            try {
                await apiClient.get('/api/songs/999');
                expect.fail('Should have thrown an error');
            } catch (error) {
                expect(error).toBeInstanceOf(ApiError);
                expect((error as ApiError).status).toBe(404);
            }
        });

        it('successfully creates new song', async () => {
            interface SongResponse {
                id: string;
                title: string;
            }
            const response = await apiClient.post<SongResponse>('/api/songs', {
                title: 'New Song',
                artist: 'New Artist',
                audio_url: 'https://example.com/new.mp3',
            });

            expect(response.id).toBeDefined();
            expect(response.title).toBe('New Song');
        });

        it('successfully deletes song', async () => {
            await expect(apiClient.delete('/api/songs/1')).resolves.not.toThrow();
        });
    });

    describe('AI Jobs API', () => {
        beforeEach(() => {
            localStorage.setItem('access_token', 'mock-access-token');
        });

        it('successfully creates AI job', async () => {
            interface JobResponse {
                id: string;
                status: string;
            }
            const response = await apiClient.post<JobResponse>('/api/ai-jobs', {
                song_id: '1',
            });

            expect(response.id).toBeDefined();
            expect(response.status).toBe('pending');
        });

        it('successfully fetches AI job status', async () => {
            interface JobResponse {
                status: string;
                progress: number;
            }
            const response = await apiClient.get<JobResponse>('/api/ai-jobs/1');

            expect(response.status).toBe('completed');
            expect(response.progress).toBe(100);
        });
    });

    describe('Storage API', () => {
        beforeEach(() => {
            localStorage.setItem('access_token', 'mock-access-token');
        });

        it('successfully uploads file', async () => {
            interface UploadResponse {
                url: string;
                key: string;
            }
            const response = await apiClient.post<UploadResponse>('/api/storage/upload/audio', {});

            expect(response.url).toBeDefined();
            expect(response.key).toBeDefined();
        });
    });

    describe('Error Handling', () => {
        it('handles network errors gracefully', async () => {
            // This would test actual network failures
            // In MSW, unhandled requests will throw errors
        });

        it('handles 401 errors for protected routes without auth', async () => {
            localStorage.removeItem('access_token');

            try {
                await apiClient.get('/api/songs');
                expect.fail('Should have thrown an error');
            } catch (error) {
                expect(error).toBeInstanceOf(ApiError);
                expect((error as ApiError).status).toBe(401);
            }
        });
    });
});
