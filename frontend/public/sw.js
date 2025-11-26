/**
 * BeatSight Service Worker
 * Provides offline support, caching, and background sync.
 */

const CACHE_VERSION = 'v1';
const STATIC_CACHE = `beatsight-static-${CACHE_VERSION}`;
const DYNAMIC_CACHE = `beatsight-dynamic-${CACHE_VERSION}`;
const API_CACHE = `beatsight-api-${CACHE_VERSION}`;

// Assets to cache on install
const STATIC_ASSETS = [
    '/',
    '/index.html',
    '/manifest.json',
    '/offline.html',
];

// API routes to cache
const CACHEABLE_API_ROUTES = [
    '/api/songs',
    '/api/ai-jobs/queue-length',
];

// Maximum age for cached API responses (in milliseconds)
const API_CACHE_MAX_AGE = 5 * 60 * 1000; // 5 minutes

// Install event - cache static assets
self.addEventListener('install', (event) => {
    console.log('[SW] Installing service worker...');

    event.waitUntil(
        caches.open(STATIC_CACHE).then((cache) => {
            console.log('[SW] Caching static assets');
            return cache.addAll(STATIC_ASSETS);
        })
    );

    // Activate immediately
    self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
    console.log('[SW] Activating service worker...');

    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys
                    .filter((key) => {
                        return (
                            key.startsWith('beatsight-') &&
                            key !== STATIC_CACHE &&
                            key !== DYNAMIC_CACHE &&
                            key !== API_CACHE
                        );
                    })
                    .map((key) => {
                        console.log('[SW] Deleting old cache:', key);
                        return caches.delete(key);
                    })
            );
        })
    );

    // Take control of all pages
    self.clients.claim();
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Skip non-GET requests
    if (request.method !== 'GET') {
        return;
    }

    // Skip chrome-extension and other non-http(s) requests
    if (!url.protocol.startsWith('http')) {
        return;
    }

    // Handle API requests
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(handleApiRequest(request));
        return;
    }

    // Handle static assets
    event.respondWith(handleStaticRequest(request));
});

/**
 * Handle API requests with stale-while-revalidate strategy.
 */
async function handleApiRequest(request) {
    const url = new URL(request.url);

    // Only cache specific API routes
    const shouldCache = CACHEABLE_API_ROUTES.some((route) =>
        url.pathname.startsWith(route)
    );

    if (!shouldCache) {
        return fetch(request);
    }

    const cache = await caches.open(API_CACHE);
    const cachedResponse = await cache.match(request);

    // Return cached response if fresh
    if (cachedResponse) {
        const cachedTime = cachedResponse.headers.get('sw-cached-at');
        if (cachedTime) {
            const age = Date.now() - parseInt(cachedTime, 10);
            if (age < API_CACHE_MAX_AGE) {
                // Revalidate in background
                revalidateCache(request, cache);
                return cachedResponse;
            }
        }
    }

    // Fetch fresh response
    try {
        const response = await fetch(request);

        if (response.ok) {
            // Clone and add cache timestamp
            const responseToCache = response.clone();
            const headers = new Headers(responseToCache.headers);
            headers.set('sw-cached-at', Date.now().toString());

            const body = await responseToCache.blob();
            const cachedResponse = new Response(body, {
                status: responseToCache.status,
                statusText: responseToCache.statusText,
                headers,
            });

            await cache.put(request, cachedResponse);
        }

        return response;
    } catch (error) {
        // Return cached response if network fails
        if (cachedResponse) {
            console.log('[SW] Network failed, returning cached response');
            return cachedResponse;
        }
        throw error;
    }
}

/**
 * Revalidate cache in background.
 */
async function revalidateCache(request, cache) {
    try {
        const response = await fetch(request);

        if (response.ok) {
            const headers = new Headers(response.headers);
            headers.set('sw-cached-at', Date.now().toString());

            const body = await response.blob();
            const cachedResponse = new Response(body, {
                status: response.status,
                statusText: response.statusText,
                headers,
            });

            await cache.put(request, cachedResponse);
        }
    } catch {
        // Silently fail background revalidation
    }
}

/**
 * Handle static requests with cache-first strategy.
 */
async function handleStaticRequest(request) {
    // Try static cache first
    const staticCache = await caches.open(STATIC_CACHE);
    const staticResponse = await staticCache.match(request);

    if (staticResponse) {
        return staticResponse;
    }

    // Try dynamic cache
    const dynamicCache = await caches.open(DYNAMIC_CACHE);
    const dynamicResponse = await dynamicCache.match(request);

    if (dynamicResponse) {
        return dynamicResponse;
    }

    // Fetch from network
    try {
        const response = await fetch(request);

        // Cache successful responses
        if (response.ok && response.type === 'basic') {
            const responseToCache = response.clone();
            await dynamicCache.put(request, responseToCache);
        }

        return response;
    } catch {
        // Return offline page for navigation requests
        if (request.mode === 'navigate') {
            const offlinePage = await staticCache.match('/offline.html');
            if (offlinePage) {
                return offlinePage;
            }
        }

        // Return generic offline response
        return new Response('Offline', {
            status: 503,
            statusText: 'Service Unavailable',
            headers: { 'Content-Type': 'text/plain' },
        });
    }
}

// Handle push notifications
self.addEventListener('push', (event) => {
    if (!event.data) {
        return;
    }

    try {
        const data = event.data.json();

        const options = {
            body: data.body || 'New notification from BeatSight',
            icon: '/icons/icon-192x192.png',
            badge: '/icons/badge-72x72.png',
            tag: data.tag || 'beatsight-notification',
            data: data.data || {},
        };

        event.waitUntil(
            self.registration.showNotification(data.title || 'BeatSight', options)
        );
    } catch {
        console.error('[SW] Failed to parse push notification data');
    }
});

// Handle notification clicks
self.addEventListener('notificationclick', (event) => {
    event.notification.close();

    const url = event.notification.data?.url || '/';

    event.waitUntil(
        self.clients.matchAll({ type: 'window' }).then((clients) => {
            // Focus existing window if available
            for (const client of clients) {
                if (client.url === url && 'focus' in client) {
                    return client.focus();
                }
            }

            // Open new window
            return self.clients.openWindow(url);
        })
    );
});

// Background sync for failed requests
self.addEventListener('sync', (event) => {
    if (event.tag === 'upload-retry') {
        event.waitUntil(retryFailedUploads());
    }
});

/**
 * Retry failed uploads from IndexedDB queue.
 */
async function retryFailedUploads() {
    // This would integrate with IndexedDB to retry failed uploads
    // Implementation depends on how uploads are queued in the main app
    console.log('[SW] Retrying failed uploads...');
}
