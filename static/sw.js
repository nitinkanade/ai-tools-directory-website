/**
 * AI Tools Directory — Offline Service Worker
 * Provides offline navigation fallback, static asset caching, and search persistence.
 */

const CACHE_NAME = 'ai-tools-dir-v1';
const PRECACHE_ASSETS = [
  './',
  './tools/',
  './collections/',
  './static/css/styles.css',
  './static/js/app.js',
  './static/manifest.webmanifest',
  './static/img/favicon-32x32.png',
  './static/img/logo.png',
  './data/search-index.json',
  './data/categories.json',
  './data/manifest.json'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_ASSETS).catch((err) => {
        console.warn('[SW] Precache partial error (ignored):', err);
      });
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);

  // Same origin requests
  if (url.origin === location.origin) {
    // For HTML page navigations: Network-first with cache fallback
    if (req.mode === 'navigate' || req.headers.get('accept')?.includes('text/html')) {
      event.respondWith(
        fetch(req)
          .then((res) => {
            if (res.status === 200) {
              const copy = res.clone();
              caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
            }
            return res;
          })
          .catch(() => {
            return caches.match(req).then((cached) => {
              if (cached) return cached;
              return caches.match('./404.html') || caches.match('./');
            });
          })
      );
      return;
    }

    // For static assets and data: Stale-While-Revalidate
    event.respondWith(
      caches.match(req).then((cached) => {
        const fetchPromise = fetch(req)
          .then((res) => {
            if (res.status === 200) {
              const copy = res.clone();
              caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
            }
            return res;
          })
          .catch(() => cached);

        return cached || fetchPromise;
      })
    );
  }
});
