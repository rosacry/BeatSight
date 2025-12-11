import { http, HttpResponse, PathParams, HttpResponseResolver } from 'msw';

// Helper to create a mock JWT token with a future expiration
// This creates a structurally valid JWT (header.payload.signature)
function createMockJwt(expiresInSeconds: number = 3600): string {
    const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
    const payload = btoa(JSON.stringify({
        sub: 'user123',
        exp: Math.floor(Date.now() / 1000) + expiresInSeconds,
        iat: Math.floor(Date.now() / 1000),
    }));
    // Mock signature (not cryptographically valid, but structurally correct)
    const signature = btoa('mock-signature');
    return `${header}.${payload}.${signature}`;
}

// Export for use in tests that need to create tokens
export { createMockJwt };

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

// Generate fresh tokens each time to ensure they have valid expiration
const getMockTokens = () => ({
    access_token: createMockJwt(3600),  // Valid for 1 hour
    refresh_token: 'mock-refresh-token',
    token_type: 'bearer',
    expires_in: 3600,
});

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

// Handler logic functions
const handleRegister = async ({ request }: { request: Request }) => {
    const body = await request.json() as Record<string, string>;
    if (!body.email || !body.password || !body.display_name) {
        return HttpResponse.json(
            { detail: 'Missing required fields' },
            { status: 400 }
        );
    }
    const tokens = getMockTokens();
    return HttpResponse.json({
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token,
        token_type: tokens.token_type,
    });
};

const handleLogin = async ({ request }: { request: Request }) => {
    const body = await request.json() as Record<string, string>;
    if (body.email === 'test@example.com' && body.password === 'password123') {
        return HttpResponse.json({
            user: mockUser,
            ...getMockTokens(),
        });
    }
    return HttpResponse.json(
        { detail: 'Invalid credentials' },
        { status: 401 }
    );
};

const handleRefresh = async ({ request }: { request: Request }) => {
    const body = await request.json() as { refresh_token?: string };
    if (body.refresh_token === 'mock-refresh-token') {
        return HttpResponse.json(getMockTokens());
    }
    return HttpResponse.json(
        { detail: 'Invalid refresh token' },
        { status: 401 }
    );
};

const handleLogout = () => {
    return HttpResponse.json({ message: 'Logged out successfully' });
};

const handleMe = ({ request }: { request: Request }) => {
    const authHeader = request.headers.get('Authorization');
    if (authHeader?.startsWith('Bearer ')) {
        return HttpResponse.json(mockUser);
    }
    return HttpResponse.json(
        { detail: 'Not authenticated' },
        { status: 401 }
    );
};

const handleGetSongs = ({ request }: { request: Request }) => {
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
};

const handleGetSong: HttpResponseResolver<PathParams<'id'>> = ({ params, request }) => {
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
};

const handleCreateSong = async ({ request }: { request: Request }) => {
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
};

const handleDeleteSong: HttpResponseResolver<PathParams<'id'>> = ({ params, request }) => {
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
};

const handleCreateJob = ({ request }: { request: Request }) => {
    const authHeader = request.headers.get('Authorization');
    if (!authHeader) {
        return HttpResponse.json(
            { detail: 'Not authenticated' },
            { status: 401 }
        );
    }
    return HttpResponse.json(mockJob, { status: 201 });
};

const handleGetJob: HttpResponseResolver<PathParams<'id'>> = ({ params, request }) => {
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
};

const handleUpload = ({ request }: { request: Request }) => {
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
};

const handleHealth = () => {
    return HttpResponse.json({ status: 'healthy' });
};

const handleHealthFeatures = () => {
    return HttpResponse.json({
        cloud_sync: false,
        phone_verification: false,
        two_factor_auth: true,
        stripe_payments: false,
    });
};

export const handlers = [
    // Auth endpoints - both /api/auth/* and /api/api/auth/* patterns
    // Direct API calls use /api/auth/*
    http.post('/api/auth/register', handleRegister),
    http.post('/api/auth/login', handleLogin),
    http.post('/api/auth/refresh', handleRefresh),
    http.post('/api/auth/logout', handleLogout),
    http.get('/api/auth/me', handleMe),

    // authStore uses /api/api/auth/* (API_BASE + /api/auth/*)
    http.post('/api/api/auth/register', handleRegister),
    http.post('/api/api/auth/login', handleLogin),
    http.post('/api/api/auth/refresh', handleRefresh),
    http.post('/api/api/auth/logout', handleLogout),
    http.get('/api/api/auth/me', handleMe),

    // Songs endpoints - both patterns
    http.get('/api/songs', handleGetSongs),
    http.get('/api/songs/:id', handleGetSong),
    http.post('/api/songs', handleCreateSong),
    http.delete('/api/songs/:id', handleDeleteSong),

    http.get('/api/api/songs', handleGetSongs),
    http.get('/api/api/songs/:id', handleGetSong),
    http.post('/api/api/songs', handleCreateSong),
    http.delete('/api/api/songs/:id', handleDeleteSong),

    // AI Jobs endpoints - both patterns
    http.post('/api/ai-jobs', handleCreateJob),
    http.get('/api/ai-jobs/:id', handleGetJob),

    http.post('/api/api/ai-jobs', handleCreateJob),
    http.get('/api/api/ai-jobs/:id', handleGetJob),

    // Storage endpoints - both patterns
    http.post('/api/storage/upload/:category', handleUpload),
    http.post('/api/api/storage/upload/:category', handleUpload),

    // Health check - all patterns
    http.get('/health/live', handleHealth),
    http.get('/health/features', handleHealthFeatures),
    http.get('/api/health/live', handleHealth),
    http.get('/api/health/features', handleHealthFeatures),
    http.get('/api/api/health/live', handleHealth),
];
