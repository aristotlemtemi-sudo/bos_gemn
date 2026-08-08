/* BOS GEMN Progressive Web App Service Worker */

const CACHE_NAME = 'bos-gemn-cache-v2';
const STATIC_PREFIXES = ['/static/', '/sw.js', '/manifest.json', '/offline.html'];
const ASSETS_TO_CACHE = [
    '/',
    '/offline.html',
    '/static/manifest.json',
    '/static/css/style.css',
    '/static/js/sw.js',
    '/static/uploads/icon-192.png',
    '/static/uploads/icon-512.png'
];

self.addEventListener('install', function(event) {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(ASSETS_TO_CACHE))
            .then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', function(event) {
    event.waitUntil(
        caches.keys().then(keys => Promise.all(
            keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
        )).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', function(event) {
    if (event.request.method !== 'GET') {
        return;
    }

    const requestURL = new URL(event.request.url);
    if (requestURL.origin !== self.location.origin) {
        return;
    }

    // NEVER cache API responses: follow-up marks, settings, reports, PDFs, etc.
    // must always come fresh from the network or the user sees stale data.
    if (requestURL.pathname.startsWith('/api/')) {
        return;
    }

    // HTML / navigation: network-first, fall back to cached home page.
    if (requestURL.pathname === '/' || requestURL.pathname.endsWith('.html')) {
        event.respondWith(
            fetch(event.request).catch(() => caches.match('/'))
        );
        return;
    }

    // Static assets (CSS/JS/images): cache-first with runtime caching.
    if (STATIC_PREFIXES.some(p => requestURL.pathname.startsWith(p))) {
        event.respondWith(
            caches.match(event.request).then(cachedResponse => {
                return cachedResponse || fetch(event.request).then(networkResponse => {
                    if (networkResponse && networkResponse.ok) {
                        caches.open(CACHE_NAME).then(cache => {
                            cache.put(event.request, networkResponse.clone());
                        });
                    }
                    return networkResponse;
                }).catch(() => {
                    if (event.request.headers.get('accept')?.includes('image')) {
                        return caches.match('/static/uploads/icon-192.png');
                    }
                    return caches.match('/offline.html');
                });
            })
        );
        return;
    }

    // Anything else (unhandled routes): network-first.
    event.respondWith(
        fetch(event.request).catch(() => caches.match('/offline.html'))
    );
});

self.addEventListener('push', function(event) {
    let data = { title: 'BOS GEMN Notification', message: 'You have a new alert!' };
    if (event.data) {
        try {
            data = event.data.json();
        } catch (e) {
            data.message = event.data.text();
        }
    }

    const options = {
        body: data.message || data.body || 'New notification',
        icon: '/static/uploads/icon-192.png',
        badge: '/static/uploads/icon-192.png',
        vibrate: [100, 50, 100],
        data: {
            url: data.url || '/'
        }
    };

    event.waitUntil(
        self.registration.showNotification(data.title || 'BOS GEMN', options)
    );
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    event.waitUntil(
        clients.openWindow(event.notification.data.url || '/')
    );
});
