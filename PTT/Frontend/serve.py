from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parent.parent
PUBLIC_FILES = {
    "/": (ROOT / "index.html", "text/html; charset=utf-8"),
    "/Frontend/SIGMAT_actualizado_v3/css/estilos.css": (
        ROOT / "Frontend/SIGMAT_actualizado_v3/css/estilos.css", "text/css; charset=utf-8"
    ),
    "/Frontend/SIGMAT_actualizado_v3/js/app.js": (
        ROOT / "Frontend/SIGMAT_actualizado_v3/js/app.js", "text/javascript; charset=utf-8"
    ),
}


class PublicFrontendHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_public_file(send_body=True)

    def do_HEAD(self):
        self.send_public_file(send_body=False)

    def send_public_file(self, send_body):
        resource = PUBLIC_FILES.get(urlsplit(self.path).path)
        if resource is None:
            self.send_error(404)
            return

        path, content_type = resource
        content = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if send_body:
            self.wfile.write(content)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 5173), PublicFrontendHandler).serve_forever()