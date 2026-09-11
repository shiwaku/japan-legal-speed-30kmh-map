// キャッシュしない Service Worker。常に最新をネットワークから取得する。
// 有効化時に既存キャッシュをすべて削除する。
self.addEventListener('install', () => {
  self.skipWaiting()
})

self.addEventListener('activate', (e) => {
  e.waitUntil(
    (async () => {
      for (const k of await caches.keys()) await caches.delete(k)
      await self.clients.claim()
    })(),
  )
})

// HTML(ナビゲーション)だけネットワーク優先で、HTTP キャッシュもバイパスして取得する。
// GitHub Pages は index.html を max-age=600 で返すため、通常リロードでは最大 10 分
// 古い index.html(＝古い JS/CSS ハッシュ)が使われる。no-store で毎回最新を取る。
// PMTiles は Range リクエストで読むため介入しない。
self.addEventListener('fetch', (event) => {
  const req = event.request
  if (req.mode === 'navigate') {
    event.respondWith(fetch(req, { cache: 'no-store' }).catch(() => fetch(req)))
  }
})
