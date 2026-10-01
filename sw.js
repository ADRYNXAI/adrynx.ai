const CACHE_NAME = "adrynx-v9";

self.addEventListener('install', e => {
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys => 
      Promise.all(keys.map(k => { if(k !== CACHE_NAME) return caches.delete(k) }))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  e.respondWith(
    fetch(e.request)
      .then(res => {
        return res;
      })
      .catch(() => caches.match(e.request))
  );
});
