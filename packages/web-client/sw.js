/* papercup PWA service worker —— 只当"可安装"门票，不缓存任何请求。
   前端天天换皮，浏览器缓存本来就是病根（CLIENT_BUILD ?v= 纪律），
   这里必须全部穿透直取网络，否则 PWA 会把换皮问题加倍放大。 */
const SW_BUILD = "20260920-pwa1";

self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  event.respondWith(fetch(event.request));
});
