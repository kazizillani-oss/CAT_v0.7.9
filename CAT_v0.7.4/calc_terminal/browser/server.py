"""CAT browser/ — the local live development server.

A threaded HTTP server that serves the CURRENT WORKSPACE only:

    http://127.0.0.1:<auto port>/
        ├── index.html            (directory -> index resolution)
        ├── style.css / app.js    (correct MIME types)
        ├── images / fonts / svg  (static assets)
        └── /__cat__/ws           (WebSocket hot-reload channel)

Hard guarantees:
* binds 127.0.0.1 ONLY (never 0.0.0.0) — the workspace is not exposed
  to the network unless a future feature explicitly opts in;
* the port is chosen by the OS at bind time (port 0), so collisions are
  impossible by construction; `url` reports the real one;
* every served path is resolved and verified to live UNDER the workspace
  root — no `..` traversal can turn this into a file-sharing server;
* responses carry no-cache headers so Chromium always revalidates against
  the files CAT's AI is actively rewriting;
* shutdown() stops listener + threads cleanly (idempotent), so CAT exit
  never leaves an orphan socket/process behind.

The WebSocket endpoint is a minimal RFC6455 server (text frames only)
implemented with the stdlib — no extra dependency. Browsers connect
through the injected hot-reload snippet (server.inject_hot_reload)
and receive JSON events: {"cmd": "reload"} or {"cmd": "hot_css",
"hrefs": [...]} for CSS-only updates.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import struct
import threading
import time
import webbrowser  # noqa: F401  (deliberately NOT used — terminal-first)
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ------------------------------------------------------------------ mimes --
_MIME = {
    ".html": "text/html; charset=utf-8", ".htm": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".mjs": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp",
    ".ico": "image/x-icon", ".bmp": "image/bmp", ".avif": "image/avif",
    ".woff": "font/woff", ".woff2": "font/woff2", ".ttf": "font/ttf",
    ".otf": "font/otf", ".eot": "application/vnd.ms-fontobject",
    ".txt": "text/plain; charset=utf-8", ".md": "text/plain; charset=utf-8",
    ".xml": "application/xml", ".pdf": "application/pdf",
    ".wasm": "application/wasm", ".map": "application/json",
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg",
    ".mp4": "video/mp4", ".webm": "video/webm",
}

WEB_EXTENSIONS = {".html", ".htm", ".css", ".js", ".mjs"}

HOT_RELOAD_SNIPPET = """
<script>
(function () {
  if (window.__CAT_HOT__) return; window.__CAT_HOT__ = true;
  function connect() {
    var ws;
    try { ws = new WebSocket("ws://127.0.0.1:" + location.port + "/__cat__/ws"); }
    catch (e) { return; }
    ws.onmessage = function (ev) {
      try {
        var msg = JSON.parse(ev.data);
        if (msg.cmd === "reload") { location.reload(); return; }
        if (msg.cmd === "hot_css") {
          (msg.hrefs || []).forEach(function (href) {
            var links = document.querySelectorAll('link[rel="stylesheet"]');
            links.forEach(function (l) {
              var key = l.getAttribute('href') || '';
              if (!href || key.indexOf(href.split('?')[0]) !== -1 ||
                  href.indexOf(key.split('?')[0]) !== -1) {
                var clone = l.cloneNode();
                var bust = "href=" + l.href.replace(/[?&]__cat=\\d+/, '') +
                           (l.href.indexOf("?") === -1 ? "?" : "&") +
                           "__cat=" + Date.now();
                clone.setAttribute("href", bust);
                l.parentNode.replaceChild(clone, l);
              }
            });
          });
        }
      } catch (e) {}
    };
    ws.onclose = function () { setTimeout(connect, 700); };
  }
  connect();
})();
</script>
"""


def find_free_port() -> int:
    """Ask the OS for a free localhost port (bind :0). The port stays
    free only momentarily — LiveServer binds immediately after."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


class _WSClient:
    """One connected preview browser (minimal RFC6455 text-frame peer)."""

    def __init__(self, sock):
        self.sock = sock
        self.alive = True
        self._lock = threading.Lock()

    def send_text(self, text: str) -> bool:
        try:
            payload = text.encode("utf-8")
            header = bytearray([0x81])  # FIN + text opcode
            n = len(payload)
            if n < 126:
                header.append(n)
            elif n < 65536:
                header.append(126)
                header += struct.pack(">H", n)
            else:
                header.append(127)
                header += struct.pack(">Q", n)
            with self._lock:
                self.sock.sendall(bytes(header) + payload)
            return True
        except Exception:
            self.alive = False
            return False

    def close(self):
        self.alive = False
        try:
            self.sock.close()
        except Exception:
            pass


def _ws_accept(key: str) -> str:
    guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    digest = hashlib.sha1((key + guid).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


class _Handler(BaseHTTPRequestHandler):
    """Request handler bound to its LiveServer via the server class."""

    protocol_version = "HTTP/1.1"

    # ------------------------------------------------------------ utils --
    def log_message(self, fmt, *args):  # silence stderr spam
        pass

    def _no_cache(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")

    def _safe_path(self, url_path: str):
        """Resolve a URL path to a real file under the root. Returns
        (filesystem_path_or_None, status_code)."""
        root = self.server.cat_root
        clean = url_path.split("?", 1)[0].split("#", 1)[0]
        clean = clean.replace("\\", "/").lstrip("/")
        try:
            candidate = os.path.normpath(os.path.join(root, clean))
            # normcase both sides so Windows casing can't smuggle a path
            # outside the root either.
            if os.path.normcase(candidate).startswith(
                    os.path.normcase(root.rstrip(os.sep) + os.sep)) \
                    or os.path.normcase(candidate) == os.path.normcase(root):
                if os.path.isdir(candidate):
                    for name in ("index.html", "index.htm"):
                        p = os.path.join(candidate, name)
                        if os.path.isfile(p):
                            return p, 200
                    return None, 404
                if os.path.isfile(candidate):
                    return candidate, 200
                return None, 404
        except Exception:
            pass
        return None, 400

    def _inject(self, body: bytes) -> bytes:
        """Append the hot-reload snippet to HTML responses."""
        lower = bytes(body[-64:]).lower()
        marker = b"</body>"
        idx = bytes(body).lower().rfind(marker)
        if idx == -1:
            # plain append still works for sloppy HTML
            return body + HOT_RELOAD_SNIPPET.encode("utf-8")
        out = body[:idx] + HOT_RELOAD_SNIPPET.encode("utf-8") + body[idx:]
        del lower
        return out

    # ----------------------------------------------------------- verbs --
    def do_GET(self):
        # ---- WebSocket upgrade -----------------------------------------
        if self.path.startswith("/__cat__/ws"):
            key = self.headers.get("Sec-WebSocket-Key", "")
            if key:
                self.send_response(101, "Switching Protocols")
                self.send_header("Upgrade", "websocket")
                self.send_header("Connection", "Upgrade")
                self.send_header("Sec-WebSocket-Accept", _ws_accept(key))
                self.end_headers()
                self.close_connection = True
                try:
                    self.connection.settimeout(600)
                    client = _WSClient(self.connection)
                    self.server.cat_ws_register(client)
                    self.server.cat_ws_reader(client)
                except Exception:
                    pass
            else:
                self.send_error(400)
            return

        path, status = self._safe_path(self.path)
        if status != 200 or path is None:
            body = (f"<h1>404 — Not in workspace</h1>"
                    f"<p>{self.path} does not exist under "
                    f"{self.server.cat_root}</p>").encode("utf-8")
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self._no_cache()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            self.server.cat_note_hit(self.path, 404)
            return

        ext = os.path.splitext(path)[1].lower()
        ctype = _MIME.get(ext, "application/octet-stream")
        try:
            with open(path, "rb") as f:
                body = f.read()
        except OSError as e:
            body = f"<h1>500</h1><p>{e}</p>".encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self._no_cache()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if ext in (".html", ".htm"):
            body = self._inject(body)
            ctype = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self._no_cache()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError,
                ConnectionAbortedError, OSError):
            pass  # preview tab navigated away mid-response — harmless
        self.server.cat_note_hit(self.path, 200)


class LiveServer:
    """One running dev server for ONE workspace root.

    Usage:
        srv = LiveServer(root)
        srv.start()               # binds 127.0.0.1:<auto>
        srv.url                   # 'http://127.0.0.1:5173/'
        srv.stop()                # idempotent, joins threads
    """

    def __init__(self, root: str, server_class=ThreadingHTTPServer,
                 handler_class=_Handler):
        self.root = os.path.abspath(os.path.expanduser(root))
        self._httpd = None
        self._thread = None
        self._state_lock = threading.Lock()
        self.port = None
        self.hits = []                      # [(path, status)] recent
        self.ws_clients = []
        self._ws_lock = threading.Lock()
        # wire the handler-facing attributes onto the server class
        base = server_class

        class _S(base):
            cat_root = self.root
            cat_server = self

            def handle_error(srv, request, client_address):
                # Preview tabs disconnect constantly (navigation, reload,
                # shutdown) — a dropped connection is never an error worth
                # printing into CAT's terminal.
                pass

            def cat_note_hit(srv, path, status):
                self._note(path, status)

            def cat_ws_register(srv, client):
                with self._ws_lock:
                    self.ws_clients = [c for c in self.ws_clients if c.alive]
                    self.ws_clients.append(client)

            def cat_ws_reader(srv, client):
                # drain frames (we never require client messages); any
                # error just marks the client dead.
                try:
                    while client.alive:
                        hdr = client.sock.recv(2)
                        if len(hdr) < 2:
                            break
                        opcode = hdr[0] & 0x0F
                        masked = hdr[1] & 0x80
                        length = hdr[1] & 0x7F
                        if length == 126:
                            ext = client.sock.recv(2)
                            length = struct.unpack(">H", ext)[0]
                        elif length == 127:
                            ext = client.sock.recv(8)
                            length = struct.unpack(">Q", ext)[0]
                        mask = client.sock.recv(4) if masked else b""
                        payload = client.sock.recv(length) if length else b""
                        if masked and mask:
                            payload = bytes(b ^ mask[i % 4]
                                            for i, b in enumerate(payload))
                        if opcode == 0x8:      # close
                            break
                        if opcode == 0x9:      # ping → pong
                            try:
                                frame = bytearray([0x8A, len(payload)])
                                client.sock.sendall(bytes(frame) + payload)
                            except Exception:
                                break
                except Exception:
                    pass
                finally:
                    client.alive = False

        self._server_cls = _S

    # ------------------------------------------------------------ props --
    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/"

    @property
    def running(self) -> bool:
        return self._httpd is not None

    def _note(self, path, status):
        self.hits.append((path, status))
        del self.hits[:-200:]

    # ----------------------------------------------------------- start --
    def start(self) -> bool:
        """Bind 127.0.0.1 on an OS-assigned port and serve forever on a
        daemon thread. Returns False (without raising) when binding
        failed for any reason."""
        if self._httpd is not None:
            return True
        try:
            port = find_free_port()
            self._httpd = self._server_cls(("127.0.0.1", port), _Handler)
            self._httpd.daemon_threads = True
            self.port = self._httpd.server_address[1]
        except Exception:
            self._httpd = None
            return False
        self._thread = threading.Thread(
            target=self._serve_loop, name="cat-live-server", daemon=True)
        self._thread.start()
        return True

    def _serve_loop(self):
        try:
            self._httpd.serve_forever(poll_interval=0.25)
        except Exception:
            pass

    def wait_ready(self, timeout=3.0) -> bool:
        """Block until the socket answers (or timeout). Keeps start-up
        ordering honest for the engine's first navigation."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.port is not None:
                try:
                    with socket.create_connection(
                            ("127.0.0.1", self.port), timeout=0.4):
                        return True
                except OSError:
                    pass
            time.sleep(0.03)
        return False

    # ---------------------------------------------------- broadcast API --
    def broadcast(self, obj: dict) -> int:
        """Send one JSON event to every connected preview browser.
        Returns the number of live clients it reached."""
        data = json.dumps(obj)
        with self._ws_lock:
            clients = [c for c in self.ws_clients if c.alive]
        sent = 0
        for c in clients:
            if c.send_text(data):
                sent += 1
        with self._ws_lock:
            self.ws_clients = [c for c in self.ws_clients if c.alive]
        return sent

    def notify_reload(self):
        # counted so tests/probes can verify debounce coalescing
        self._reload_count = getattr(self, "_reload_count", 0) + 1
        return self.broadcast({"cmd": "reload"})

    def notify_hot_css(self, hrefs):
        return self.broadcast({"cmd": "hot_css", "hrefs": list(hrefs or [])})

    # ------------------------------------------------------------- stop --
    def stop(self):
        """Idempotent full teardown: WebSocket peers, listener, thread."""
        with self._ws_lock:
            clients = list(self.ws_clients)
            self.ws_clients = []
        for c in clients:
            c.close()
        httpd, self._httpd = self._httpd, None
        if httpd is not None:
            try:
                httpd.shutdown()
            except Exception:
                pass
            try:
                httpd.server_close()
            except Exception:
                pass
        thread, self._thread = self._thread, None
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        self.port = None
