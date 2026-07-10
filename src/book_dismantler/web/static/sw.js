/* Book Dismantler Service Worker
 * 缓存静态资源（CSS/JS/字体），API 请求始终走网络。
 * 版本：v1
 */
var CACHE_NAME = "book-dismantler-v1";
var STATIC_ASSETS = [
  "/",
  "/static/css/style.css",
  "/static/js/utils.js",
  "/static/js/api.js",
  "/static/js/app.js",
  "/static/manifest.json",
];

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function (cache) {
      return cache.addAll(STATIC_ASSETS.map(function (url) {
        return new Request(url, { cache: "no-cache" });
      })).catch(function () {
        /* 静默失败：个别资源缓存失败不影响整体 */
      });
    })
  );
  self.skipWaiting();
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (names) {
      return Promise.all(
        names.filter(function (name) { return name !== CACHE_NAME; })
             .map(function (name) { return caches.delete(name); })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener("fetch", function (event) {
  var request = event.request;
  /* 仅处理 GET 请求 */
  if (request.method !== "GET") return;

  var url = new URL(request.url);

  /* API 请求、文件上传始终走网络 */
  if (url.pathname.startsWith("/api/")) {
    return;
  }

  /* 静态资源：缓存优先，网络回退 */
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(request).then(function (cached) {
        if (cached) {
          /* 后台更新缓存 */
          fetch(request).then(function (resp) {
            if (resp && resp.status === 200) {
              caches.open(CACHE_NAME).then(function (cache) {
                cache.put(request, resp.clone());
              });
            }
          }).catch(function () {});
          return cached;
        }
        return fetch(request).then(function (resp) {
          if (resp && resp.status === 200) {
            var respClone = resp.clone();
            caches.open(CACHE_NAME).then(function (cache) {
              cache.put(request, respClone);
            });
          }
          return resp;
        });
      })
    );
    return;
  }

  /* 页面导航：网络优先，离线时回退到缓存 */
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(function () {
        return caches.match("/");
      })
    );
  }
});
