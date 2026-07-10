// Service Worker for OCG Rulebook QA
const CACHE_NAME = 'ocg-rulebook-qa-v1';
const ASSETS_TO_CACHE = [
  '/',
  '/index.html',
  '/manifest.json',
  '/favicon.ico'
];

// 安装Service Worker
self.addEventListener('install', event => {
  console.log('[ServiceWorker] 正在安装...');
  
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('[ServiceWorker] 正在缓存资源...');
        return cache.addAll(ASSETS_TO_CACHE);
      })
      .then(() => {
        console.log('[ServiceWorker] 安装完成！');
        return self.skipWaiting();
      })
  );
});

// 激活Service Worker
self.addEventListener('activate', event => {
  console.log('[ServiceWorker] 正在激活...');
  
  const cacheWhitelist = [CACHE_NAME];
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (!cacheWhitelist.includes(cacheName)) {
            console.log('[ServiceWorker] 删除旧缓存:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => {
      console.log('[ServiceWorker] 激活完成！');
      return self.clients.claim();
    })
  );
});

// 网络请求拦截
self.addEventListener('fetch', event => {
  const request = event.request;

  // API请求使用网络优先策略
  if (request.url.includes('/api/')) {
    event.respondWith(
      fetch(request)
        .then(networkResponse => {
          // 缓存API响应
          if (networkResponse.ok) {
            caches.open(CACHE_NAME).then(cache => {
              cache.put(request, networkResponse.clone());
            });
          }
          return networkResponse;
        })
        .catch(() => {
          // 网络失败时，返回缓存
          return caches.match(request).then(cachedResponse => {
            return cachedResponse || new Response('网络错误', {
              status: 503,
              statusText: '服务不可用'
            });
          });
        })
    );
    return;
  }

  // 静态资源使用缓存优先策略
  event.respondWith(
    caches.match(request)
      .then(cachedResponse => {
        if (cachedResponse) {
          return cachedResponse;
        }

        return fetch(request).then(networkResponse => {
          if (!networkResponse || networkResponse.status !== 200) {
            return networkResponse;
          }

          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then(cache => {
            cache.put(request, responseToCache);
          });

          return networkResponse;
        }).catch(() => {
          // 网络失败时，显示离线页面
          return new Response('您现在离线了', {
            status: 503,
            statusText: '离线'
          });
        });
      })
  );
});

// 处理消息
self.addEventListener('message', event => {
  if (event.data === 'skipWaiting') {
    self.skipWaiting();
  }
  
  if (event.data === 'clearCache') {
    caches.keys().then(cacheNames => {
      cacheNames.forEach(cacheName => {
        caches.delete(cacheName);
      });
    });
  }
});
