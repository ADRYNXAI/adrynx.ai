self.addEventListener('install',e=>{
  self.skipWaiting();
  e.waitUntil(
    caches.open('adrynx-v12-4').then(c=>c.addAll([
      '/',
      '/index.html',
      '/landing.html',
      '/orb.mp4'
    ]))
  );
});

self.addEventListener('activate',e=>{
  e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!=='adrynx-v12-4').map(k=>caches.delete(k)))));
});

self.addEventListener('fetch',e=>{
  // Orbe = cache d'abord pour souffle vivant même offline
  if(e.request.url.includes('orb.mp4')){
    e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request).then(res=>{
      caches.open('adrynx-v12-4').then(c=>c.put(e.request,res.clone()));
      return res;
    })));
    return;
  }
  // Reste = ton code actuel intact
  e.respondWith(fetch(e.request).catch(()=>caches.match(e.request)));
});
