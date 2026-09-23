// 진짜맛집 PWA 서비스워커.
// 설치 조건(manifest + SW) 충족용 최소 구현: 정적 자원은 캐시 우선,
// 페이지는 네트워크 우선(실패 시 캐시 폴백)으로 오프라인에서도 마지막 화면 유지.
const CACHE = "matjib-v1";
const STATIC_ASSETS = [
  "/matjib/static/tailwind.js",
  "/matjib/static/material-symbols-outlined.woff2",
  "/matjib/static/icon-192.png",
  "/matjib/static/icon-512.png",
  "/matjib/static/manifest.webmanifest",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(STATIC_ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;

  // 정적 자원: 캐시 우선
  if (url.pathname.startsWith("/matjib/static/")) {
    e.respondWith(
      caches.match(e.request).then((hit) => hit || fetch(e.request).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
        return res;
      }))
    );
    return;
  }

  // 페이지: 네트워크 우선, 오프라인이면 캐시된 마지막 응답
  if (url.pathname.startsWith("/matjib")) {
    e.respondWith(
      fetch(e.request).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
        return res;
      }).catch(() => caches.match(e.request))
    );
  }
});
