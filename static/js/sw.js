/* BOS GEMN Web Push & Notification Service Worker */

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
