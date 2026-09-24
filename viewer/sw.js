// ------------------------------------------------------------------
// Service worker: lets the reader open and work offline.
//  - App shell (HTML/CSS/JS/data/font/icons + Swiper from the CDN): stored at install, then served
//    from the cache and refreshed in the background, so an update shows on the next launch.
//    Bump SHELL_VERSION when you change which files make up the shell.
//  - Pages/NNN.html: stored the first time each is read (or all at once by the app's
//    "download for offline" button) and served from the cache from then on. app.js clears this
//    cache when build_app_data.py reports a new pages version.
// ------------------------------------------------------------------

const SHELL_VERSION = 'v6';
const SHELL_CACHE = `quran-shell-${SHELL_VERSION}`;
const PAGES_CACHE = 'quran-pages';

const SWIPER_CSS = 'https://cdn.jsdelivr.net/npm/swiper@11/swiper-bundle.min.css';
const SWIPER_JS = 'https://cdn.jsdelivr.net/npm/swiper@11/swiper-bundle.min.js';

const SHELL_FILES = [
  './', './index.html', './style.css', './app.js', './manifest.webmanifest',
  './data/app_index.js', './data/quran_text.js',
  './fonts/KFGQPC-Hafs-V30.ttf',
  './icons/icon-192.png', './icons/icon-512.png', './icons/favicon.png', './icons/apple-touch-icon.png',
  SWIPER_CSS, SWIPER_JS,
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE)
      .then((cache) => cache.addAll(SHELL_FILES.map((u) => new Request(u, { cache: 'reload' }))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys
        .filter((k) => k.startsWith('quran-shell-') && k !== SHELL_CACHE)
        .map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

const isPage = (url) => /\/Pages\/\d{3}\.html$/.test(url.pathname);

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  if (isPage(url)) {
    event.respondWith(cacheFirst(req, PAGES_CACHE));
    return;
  }
  if (req.mode === 'navigate') {
    // Any navigation inside the app gets index.html (the page number lives in the #hash).
    event.respondWith(staleWhileRevalidate(event, new Request(new URL('./index.html', self.registration.scope))));
    return;
  }
  if (url.origin === self.location.origin || url.href === SWIPER_CSS || url.href === SWIPER_JS) {
    event.respondWith(staleWhileRevalidate(event, req));
  }
});

async function cacheFirst(req, cacheName) {
  const cache = await caches.open(cacheName);
  const hit = await cache.match(req, { ignoreSearch: true });
  if (hit) return hit;
  const res = await fetch(req);
  if (res.ok) cache.put(req, res.clone());
  return res;
}

async function staleWhileRevalidate(event, req) {
  const cache = await caches.open(SHELL_CACHE);
  const hit = await cache.match(req, { ignoreSearch: true });
  const refresh = fetch(req)
    .then((res) => { if (res.ok) cache.put(req, res.clone()); return res; })
    .catch(() => null);
  event.waitUntil(refresh);
  if (hit) return hit;
  return (await refresh) || new Response('غير متوفر دون اتصال', { status: 503, headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
}
