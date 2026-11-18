/* terradoc v2 service worker: the site keeps working with a weak or no connection.
   - assets/ (hashed names: never change) and the search index: cache first;
   - pages: network first, the copy kept for later (the last MAX_PAGES visited);
   - audio and photos: not stored (they would fill a cheap phone).
   The build writes VERSION and PRECACHE into the first lines. */
var VERSION = '__VERSION__';
var PRECACHE = __PRECACHE__;
var OFFLINE = '__OFFLINE__';  // shown for a page never visited, when there is no connection
var SHELL = 'td-shell-' + VERSION, PAGES = 'td-pages', MAX_PAGES = 300;

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(SHELL).then(function (c) {
    return c.addAll(PRECACHE.map(function (p) { return new Request(p, { cache: 'reload' }); }));
  }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k.indexOf('td-shell-') === 0 && k !== SHELL; })
      .map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

function trim(cache) {
  return cache.keys().then(function (keys) {
    if (keys.length > MAX_PAGES) return cache.delete(keys[0]).then(function () { return trim(cache); });
  });
}

self.addEventListener('fetch', function (e) {
  var req = e.request, url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== location.origin) return;
  if (/\/assets\//.test(url.pathname)) {
    e.respondWith(caches.match(req).then(function (hit) {
      return hit || fetch(req).then(function (res) {
        if (res.ok) { var copy = res.clone(); caches.open(SHELL).then(function (c) { c.put(req, copy); }); }
        return res;
      });
    }));
    return;
  }
  if (req.mode === 'navigate' || /\.html$/.test(url.pathname)) {
    e.respondWith(fetch(req).then(function (res) {
      if (res.ok) {
        var copy = res.clone();
        caches.open(PAGES).then(function (c) { return c.put(req, copy).then(function () { return trim(c); }); });
      }
      return res;
    }).catch(function () {
      return caches.match(req, { ignoreSearch: true }).then(function (hit) {
        return hit || caches.match(new URL(OFFLINE, self.registration.scope).href);
      });
    }));
  }
});
