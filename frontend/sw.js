// Service Worker for Dashboard PWA
const CACHE_NAME = 'dashboard-v1';
const STATIC_ASSETS = [
    '/',
    '/static/common.js',
    '/static/common.css',
    '/static/tasks.html',
    '/static/stats.html',
    '/static/manifest.json',
];

// 安装 - 缓存静态资源
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(STATIC_ASSETS);
        })
    );
    self.skipWaiting();
});

// 激活 - 清理旧缓存
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.filter((key) => key !== CACHE_NAME)
                    .map((key) => caches.delete(key))
            );
        })
    );
    self.clients.claim();
});

// 请求拦截 - 网络优先，失败时使用缓存
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // API 请求不缓存，直接走网络
    if (url.pathname.startsWith('/api/')) {
        return;
    }

    event.respondWith(
        fetch(event.request)
            .then((response) => {
                // 成功获取，更新缓存
                if (response.ok) {
                    const responseClone = response.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, responseClone);
                    });
                }
                return response;
            })
            .catch(() => {
                // 网络失败，尝试从缓存获取
                return caches.match(event.request);
            })
    );
});
