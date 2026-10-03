"""Static dev server for Borso Simulator HD.

Serves the project root and accepts `POST /save?name=<file>` to write the
request body into tools/out/<file> (used to dump the layout of the original game).
Usage: python tools/devserver.py [port]
"""
import http.server, os, sys, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'tools', 'out')


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      '.glb': 'model/gltf-binary', '.js': 'text/javascript', '.wasm': 'application/wasm'}

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        if u.path != '/save':
            self.send_error(404); return
        name = os.path.basename(urllib.parse.parse_qs(u.query).get('name', ['dump.json'])[0])
        n = int(self.headers.get('Content-Length', 0))
        os.makedirs(OUT, exist_ok=True)
        with open(os.path.join(OUT, name), 'wb') as f:
            f.write(self.rfile.read(n))
        self.send_response(200); self.end_headers(); self.wfile.write(b'ok')


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    http.server.ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
