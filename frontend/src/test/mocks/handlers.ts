import { http, HttpResponse } from 'msw';

// Mock user data
const mockUser = {
    id: '1',
    email: 'test@example.com',
    username: 'testuser',
    display_name: 'Test User',
    avatar_url: null,
    created_at: '2024-01-01T00:00:00Z',
    roles: ['user'],
};

const mockTokens = {
    access_token: 'mock-access-token',
    refresh_token: 'mock-refresh-token',
    token_type: 'bearer',
    expires_in: 3600,
};

// Mock songs data
const mockSongs = [
    {
        id: '1',
        title: 'Test Song 1',
        artist: 'Test Artist',
        duration: 180,
        bpm: 120,
        audio_url: 'https://example.com/audio1.mp3',
        cover_url: null,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
        user_id: '1',
    },
    {
        id: '2',
        title: 'Test Song 2',
        artist: 'Another Artist',
        duration: 240,
        bpm: 140,
        audio_url: 'https://example.com/audio2.mp3',
        cover_url: 'https://example.com/cover.jpg',
        created_at: '2024-01-02T00:00:00Z',
        updated_at: '2024-01-02T00:00:00Z',
        user_id: '1',
    },
];

// Mock AI job
const mockJob = {
    id: '1',
    song_id: '1',
    status: 'pending',
    progress: 0,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
};

export const handlers = [
    // Auth endpoints
    http.post('/api/auth/register', async ({ request }) => {
        const body = await request.json() as Record<string, string>;
        if (!body.email || !body.password || !body.display_name) {
            return HttpResponse.json(
                { detail: 'Missing required fields' },
                { status: 400 }
            );
        }
        return HttpResponse.json({
            access_token: mockTokens.access_token,
            refresh_token: mockTokens.refresh_token,
            token_type: mockTokens.token_type,
        });
    }),

    http.post('/api/auth/login', async ({ request }) => {
        const body = await request.json() as Record<string, string>;
        if (body.email === 'test@example.com' && body.password === 'password123') {
            return HttpResponse.json({
                user: mockUser,
                ...mockTokens,
            });
        }
        return HttpResponse.json(
            { detail: 'Invalid credentials' },
            { status: 401 }
        );
    }),

    http.post('/api/auth/refresh', async ({ request }) => {
        const body = await request.json() as { refresh_token?: string };
        if (body.refresh_token === 'mock-refresh-token') {
            return HttpResponse.json(mockTokens);
        }
        return HttpResponse.json(
            { detail: 'Invalid refresh token' },
            { status: 401 }
        );
    }),

    http.post('/api/auth/logout', () => {
        return HttpResponse.json({ message: 'Logged out successfully' });
    }),

    http.get('/api/auth/me', ({ request }) => {
        const authHeader = request.headers.get('Authorization');
        if (authHeader === 'Bearer mock-access-token') {
            return HttpResponse.json(mockUser);
        }
        return HttpResponse.json(
            { detail: 'Not authenticated' },
            { status: 401 }
        );
    }),

    // Songs endpoints
    http.get('/api/songs', ({ request }) => {
        const authHeader = request.headers.get('Authorization');
        if (!authHeader) {
            return HttpResponse.json(
                { detail: 'Not authenticated' },
                { status: 401 }
            );
        }
        return HttpResponse.json({
            items: mockSongs,
            total: mockSongs.length,
            page: 1,
            per_page: 20,
            total_pages: 1,
        });
    }),

    http.get('/api/songs/:id', ({ params, request }) => {
        const authHeader = request.headers.get('Authorization');
        if (!authHeader) {
            return HttpResponse.json(
                { detail: 'Not authenticated' },
                { status: 401 }
            );
        }
        const song = mockSongs.find((s) => s.id === params.id);
        if (song) {
            return HttpResponse.json(song);
        }
        return HttpResponse.json(
            { detail: 'Song not found' },
            { status: 404 }
        );
    }),

    http.post('/api/songs', async ({ request }) => {
        const authHeader = request.headers.get('Authorization');
        if (!authHeader) {
            return HttpResponse.json(
                { detail: 'Not authenticated' },
                { status: 401 }
            );
        }
        const body = await request.json() as Record<string, unknown>;
        return HttpResponse.json({
            ...mockSongs[0],
            id: '3',
            ...body,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
        }, { status: 201 });
    }),

    http.delete('/api/songs/:id', ({ params, request }) => {
        const authHeader = request.headers.get('Authorization');
        if (!authHeader) {
            return HttpResponse.json(
                { detail: 'Not authenticated' },
                { status: 401 }
            );
        }
        const song = mockSongs.find((s) => s.id === params.id);
        if (song) {
            return new HttpResponse(null, { status: 204 });
        }
        return HttpResponse.json(
            { detail: 'Song not found' },
            { status: 404 }
        );
    }),

    // AI Jobs endpoints
    http.post('/api/ai-jobs', async ({ request }) => {
        const authHeader = request.headers.get('Authorization');
        if (!authHeader) {
            return HttpResponse.json(
                { detail: 'Not authenticated' },
                { status: 401 }
            );
        }
        return HttpResponse.json(mockJob, { status: 201 });
    }),

    http.get('/api/ai-jobs/:id', ({ params, request }) => {
        const authHeader = request.headers.get('Authorization');
        if (!authHeader) {
            return HttpResponse.json(
                { detail: 'Not authenticated' },
                { status: 401 }
            );
        }
        if (params.id === '1') {
            return HttpResponse.json({
                ...mockJob,
                status: 'completed',
                progress: 100,
            });
        }
        return HttpResponse.json(
            { detail: 'Job not found' },
            { status: 404 }
        );
    }),

    // Storage endpoints
    http.post('/api/storage/upload/:category', async ({ request }) => {
        const authHeader = request.headers.get('Authorization');
        if (!authHeader) {
            return HttpResponse.json(
                { detail: 'Not authenticated' },
                { status: 401 }
            );
        }
        return HttpResponse.json({
            url: 'https://storage.example.com/uploads/test-file.mp3',
            key: 'uploads/test-file.mp3',
        });
    }),

    // Health check
    http.get('/health/live', () => {
        return HttpResponse.json({ status: 'healthy' });
    }),

    http.get('/api/health/live', () => {
        return HttpResponse.json({ status: 'healthy' });
    }),
];
