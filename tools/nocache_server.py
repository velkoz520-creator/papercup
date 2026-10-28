# 本地预览专用：禁缓存 http 服务器（省得浏览器拿旧图制造冤案）
import http.server, functools, sys

class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.send_header('Expires', '0')
        super().end_headers()

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8317
    handler = functools.partial(NoCacheHandler, directory='.')
    http.server.ThreadingHTTPServer(('127.0.0.1', port), handler).serve_forever()
