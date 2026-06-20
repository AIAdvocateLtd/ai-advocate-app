/*
 * AI Advocate — Service Worker
 *
 * Minimal PWA-compliant service worker required by Google Play / PWABuilder.
 *
 * Strategy:
 *   - Network-first for HTML navigations (so the user always gets fresh React bundles).
 *   - Cache-first for hashed JS/CSS/static assets (instant repeat loads).
 *   - Bypass everything API-related (/api/*) — the app must never serve stale legal data.
 *
 * Versioning: bump CACHE_VERSION when shipping breaking changes to force clients to
 * drop the old cache on activate.
 */

const CACHE_VERSION = "aa-v1";
const STATIC_CACHE = `${CACHE_VERSION}-static`;

const PRECACHE_URLS = [
  "/",
  "/manifest.json",
  "/assets/icon-192.png",
  "/assets/icon-512.png",
  "/assets/apple-touch-icon.png",
  "/assets/splash-midframe.jpg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(STATIC_CACHE)
      .then((cache) => cache.addAll(PRECACHE_URLS).catch(() => null))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => k.startsWith("aa-") && !k.startsWith(CACHE_VERSION))
            .map((k) => caches.delete(k))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);

  // Never cache API calls — legal data must always be live.
  if (url.pathname.startsWith("/api/")) return;

  // Skip cross-origin (analytics, Stripe, etc.).
  if (url.origin !== self.location.origin) return;

  // Network-first for navigations / HTML.
  if (req.mode === "navigate" || (req.headers.get("accept") || "").includes("text/html")) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(STATIC_CACHE).then((c) => c.put(req, copy)).catch(() => null);
          return res;
        })
        .catch(() => caches.match(req).then((r) => r || caches.match("/")))
    );
    return;
  }

  // Cache-first for static assets.
  event.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;
      return fetch(req)
        .then((res) => {
          if (res && res.status === 200 && res.type === "basic") {
            const copy = res.clone();
            caches.open(STATIC_CACHE).then((c) => c.put(req, copy)).catch(() => null);
          }
          return res;
        })
        .catch(() => cached);
    })
  );
});

// Allow the page to trigger an immediate update.
self.addEventListener("message", (event) => {
  if (event.data === "SKIP_WAITING") self.skipWaiting();
});
