const CACHE = 'hey-pulkit-v1';
const ASSETS = ['/', '/static/css/style.css', '/static/js/app.js'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)));
});

self.addEventListener('fetch', e => {
  if (e.request.url.includes('/api/')) return; // never cache API calls
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request))
  );
});
