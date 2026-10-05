// Connectivity indicator only: do not cache API state or silently show stale financial decisions.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
