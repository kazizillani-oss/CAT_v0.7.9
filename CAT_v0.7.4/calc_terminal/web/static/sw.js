/**
 * FATTY CAT Service Worker
 * Provides offline support and caching for the PWA
 */

const CACHE_NAME = 'fatty-cat-v0.7.9';
const STATIC_CACHE = 'fatty-cat-static-v0.7.9';
const DYNAMIC_CACHE = 'fatty-cat-dynamic-v0.7.9';
const PREVIEW_CACHE = 'fatty-cat-preview-v0.7.9';

// Files to cache immediately on install
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/static/css/app.css',
  '/static/js/app.js',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
];

// Cache strategies
const CACHE_STRATEGIES = {
  // Cache first - for static assets
  cacheFirst: async (request) => {
    const cache = await caches.open(STATIC_CACHE);
    const cached = await cache.match(request);
    if (cached) return cached;
    
    try {
      const response = await fetch(request);
      if (response.ok) {
        cache.put(request, response.clone());
      }
      return response;
    } catch (error) {
      return new Response('Offline', { status: 503 });
    }
  },
  
  // Network first - for API calls
  networkFirst: async (request) => {
    const cache = await caches.open(DYNAMIC_CACHE);
    try {
      const response = await fetch(request);
      if (response.ok) {
        cache.put(request, response.clone());
      }
      return response;
    } catch (error) {
      const cached = await cache.match(request);
      if (cached) return cached;
      return new Response(JSON.stringify({ error: 'Offline' }), {
        status: 503,
        headers: { 'Content-Type': 'application/json' },
      });
    }
  },
  
  // Stale while revalidate - for preview content
  staleWhileRevalidate: async (request) => {
    const cache = await caches.open(PREVIEW_CACHE);
    const cached = await cache.match(request);
    
    const fetchPromise = fetch(request).then(response => {
      if (response.ok) {
        cache.put(request, response.clone());
      }
      return response;
    }).catch(() => cached);
    
    return cached || fetchPromise;
  },
};

// Install event - cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    }).then(() => self.skipWaiting())
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== STATIC_CACHE && name !== DYNAMIC_CACHE && name !== PREVIEW_CACHE)
          .map((name) => caches.delete(name))
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch event - route to appropriate strategy
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);
  
  // Skip non-GET requests
  if (request.method !== 'GET') return;
  
  // Skip cross-origin requests (except for preview proxy)
  if (url.origin !== location.origin && !url.pathname.startsWith('/preview/')) return;
  
  // Route based on path
  if (url.pathname.startsWith('/api/')) {
    // API calls - network first
    event.respondWith(CACHE_STRATEGIES.networkFirst(request));
  } else if (url.pathname.startsWith('/preview/') || url.pathname.startsWith('/ws/')) {
    // Preview content - stale while revalidate
    event.respondWith(CACHE_STRATEGIES.staleWhileRevalidate(request));
  } else if (
    url.pathname.endsWith('.css') ||
    url.pathname.endsWith('.js') ||
    url.pathname.endsWith('.png') ||
    url.pathname.endsWith('.ico') ||
    url.pathname.endsWith('.woff2') ||
    url.pathname === '/' ||
    url.pathname === '/index.html' ||
    url.pathname === '/manifest.json'
  ) {
    // Static assets - cache first
    event.respondWith(CACHE_STRATEGIES.cacheFirst(request));
  } else {
    // Default - network first
    event.respondWith(CACHE_STRATEGIES.networkFirst(request));
  }
});

// Background sync for offline actions
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-files') {
    event.waitUntil(syncFiles());
  } else if (event.tag === 'sync-commands') {
    event.waitUntil(syncCommands());
  }
});

// Push notifications
self.addEventListener('push', (event) => {
  if (!event.data) return;
  
  const data = event.data.json();
  const options = {
    body: data.body,
    icon: '/static/icons/icon-192.png',
    badge: '/static/icons/badge-72.png',
    vibrate: [200, 100, 200],
    data: data.data || {},
    actions: data.actions || [],
    requireInteraction: true,
  };
  
  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

// Notification click
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  
  if (event.action === 'open') {
    event.waitUntil(
      clients.openWindow(event.notification.data.url || '/')
    );
  } else if (event.action === 'dismiss') {
    // Just close
  } else {
    // Default click - open app
    event.waitUntil(
      clients.matchAll({ type: 'window' }).then((clientList) => {
        for (const client of clientList) {
          if (client.url === '/' && 'focus' in client) {
            return client.focus();
          }
        }
        return clients.openWindow('/');
      })
    );
  }
});

// Message from main thread
self.addEventListener('message', (event) => {
  if (event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  } else if (event.data.type === 'CACHE_PREVIEW') {
    cachePreviewFiles(event.data.files);
  } else if (event.data.type === 'CLEAR_CACHE') {
    clearCache(event.data.cacheName);
  }
});

// Sync functions
async function syncFiles() {
  // Implement file sync when back online
  console.log('[SW] Syncing files...');
}

async function syncCommands() {
  // Implement command sync when back online
  console.log('[SW] Syncing commands...');
}

async function cachePreviewFiles(files) {
  const cache = await caches.open(PREVIEW_CACHE);
  for (const file of files) {
    try {
      await cache.add(file);
    } catch (error) {
      console.warn('[SW] Failed to cache preview file:', file, error);
    }
  }
}

async function clearCache(cacheName) {
  if (cacheName) {
    await caches.delete(cacheName);
  } else {
    const cacheNames = await caches.keys();
    await Promise.all(cacheNames.map(name => caches.delete(name)));
  }
}

console.log('[SW] FATTY CAT Service Worker loaded');