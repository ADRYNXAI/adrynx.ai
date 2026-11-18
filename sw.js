// ADRYNX V16 - FIX ENVOI - NE PLUS CACHER LE HTML
self.addEventListener('install', e => {
  self.skipWaiting();
  e.waitUntil(
    caches.open('adrynx-v16-fix-envoi-1').then(c => c.addAll(['/orb.mp4']).catch(()=>{}))
  );
});
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => k !== 'adrynx-v16-fix-envoi-1').map(k => caches.delete(k))
    )).then(()=> self.clients.claim())
  );
});
self.addEventListener('fetch', e => {
  let url = e.request.url;
  if (url.includes('/app') || url.includes('/index.html') || url.includes('/landing.html') || url.includes('/api/') || url.endsWith('/')) {
    e.respondWith(fetch(e.request));
    return;
  }
  if (url.includes('orb.mp4')) {
    e.respondWith(
      caches.match(e.request).then(r => r || fetch(e.request).then(res => {
        caches.open('adrynx-v16-fix-envoi-1').then(c => c.put(e.request, res.clone()));
        return res;
      }))
    );
    return;
  }
  e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
});
