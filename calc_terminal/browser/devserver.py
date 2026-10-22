"""CAT browser/ — external framework dev-server runner (spec §19–20).

For Vite / Next / CRA workspaces the project ALREADY ships a dev server
with real HMR. CAT must not stack its own LiveServer on top of it; it
should start (or reuse) the project's own `npm run dev`-style process,
discover the local URL it prints, and point the embedded Chromium at
that URL.

Lifecycle contract (mirrors PreviewController's):

    DevServerProcess(root, command)   created (nothing spawned yet)
    .start() -> bool                  spawn + wait for URL (≤ timeout)
    .url                              "http://localhost:5173/" once up
    .running                          process alive AND url known
    .stop()                           kill the WHOLE process tree;
                                      idempotent, safe after exit

The reader threads are daemons and every wait is bounded, so a wedged
npm can never freeze CAT. On Windows the tree is killed with
`taskkill /T /F` (npm spawns children npm/node that plain terminate()
leaks); elsewhere terminate() then kill().
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
import time
from typing import Callable, List, Optional, Tuple

# Any localhost URL the dev server prints (Vite: "Local: http://…",
# Next: "- Local: http://localhost:3000", CRA: "http://localhost:3000").
_URL_RE = re.compile(
    r"https?://(?:[a-z0-9.\-]*?)?(?:localhost|127\.0\.0\.1|0\.0\.0\.0"
    r"|\[::1\]):(\d+)[^\s\"'<>]*", re.IGNORECASE)

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

DEFAULT_TIMEOUT = 15.0


def is_fomoji_server(port: int, host: str = "127.0.0.1") -> bool:
    """Check if the service at host:port is CAT's Fomoji auth server."""
    try:
        f_url = os.environ.get("FOMOJI_URL", "http://localhost:3000").rstrip("/")
        import urllib.parse
        parsed = urllib.parse.urlparse(f_url)
        f_port = parsed.port or (443 if parsed.scheme == "https" else 3000)
        f_host = parsed.hostname or "127.0.0.1"
        if port == f_port and host in (f_host, "127.0.0.1", "localhost"):
            import http.client
            conn = http.client.HTTPConnection(host, port, timeout=0.25)
            conn.request("GET", "/api/connector/applications")
            res = conn.getresponse()
            raw = res.read(512).decode("utf-8", errors="ignore")
            conn.close()
            if res.status == 200 and ("applications" in raw or "fomoji" in raw.lower()):
                return True
            conn = http.client.HTTPConnection(host, port, timeout=0.25)
            conn.request("GET", "/")
            res = conn.getresponse()
            raw = res.read(1024).decode("utf-8", errors="ignore")
            conn.close()
            if "fomoji" in raw.lower():
                return True
    except Exception:
        pass
    return False


def probe_local_server(port: int, host: str = "127.0.0.1", path: str = "/") -> bool:
    """Check if a local HTTP server is already responding on host:port,
    ensuring CAT's Fomoji auth server is NEVER mistaken for a project dev server."""
    if is_fomoji_server(port, host):
        return False
    try:
        import http.client
        conn = http.client.HTTPConnection(host, port, timeout=0.25)
        conn.request("GET", path)
        res = conn.getresponse()
        conn.close()
        return res.status < 500
    except Exception:
        return False


def extract_local_url(line: str) -> Optional[str]:
    """One stdout/stderr line -> the first local URL in it (or None).
    Normalized: bind addresses become 127.0.0.1, bare-host URLs get a
    trailing '/', trailing punctuation and ANSI escape codes are trimmed.
    Pure function; unit-tested without any subprocess."""
    if not line:
        return None
    clean = _ANSI_RE.sub("", line)
    m = _URL_RE.search(clean)
    if not m:
        return None
    url = m.group(0).rstrip(".,;)'\"\x1b")
    url = _ANSI_RE.sub("", url).rstrip(".,;)'\"")
    # 0.0.0.0/[::1] are bind addresses, not browsable — normalize.
    url = url.replace("://0.0.0.0:", "://127.0.0.1:")
    url = url.replace("://[::1]:", "://127.0.0.1:")
    # A scheme+host with no path at all means the site root.
    if re.match(r"^https?://[^/]+$", url):
        url += "/"
    return url


class DevServerProcess:
    """One external dev-server child process owned by the preview."""

    def __init__(self, root: str, command: Tuple[str, ...] = ("npm", "run", "dev"),
                 on_activity: Optional[Callable[[str], None]] = None):
        self.root = os.path.abspath(os.path.expanduser(root))
        self.command = tuple(command)
        self.url: str = ""
        self.proc: Optional[subprocess.Popen] = None
        self._tail: List[str] = []          # last output lines (errors)
        self._lock = threading.Lock()
        self._on_activity = on_activity or (lambda text: None)

    # ------------------------------------------------------------- props --
    @property
    def running(self) -> bool:
        return (self.proc is not None and self.proc.poll() is None
                and bool(self.url))

    @property
    def last_output(self) -> str:
        with self._lock:
            return "\n".join(self._tail[-8:])

    # -------------------------------------------------------------- spawn --
    def start(self, timeout: float = DEFAULT_TIMEOUT) -> bool:
        """Spawn the dev server and wait until it prints a local URL."""
        if self.running:
            return True

        # Fast probe: Check if a dev server is ALREADY running on common ports
        # (e.g. Vite 5173, Next/CRA 3001/3000, 8080) to reuse instantly
        for common_p in (5173, 3001, 8080, 5000, 4173, 3000):
            if probe_local_server(common_p):
                self.url = f"http://127.0.0.1:{common_p}/"
                self._note(f"● Reusing active local dev server — {self.url}")
                return True

        argv = list(self.command)
        exe = shutil.which(argv[0]) or shutil.which(argv[0] + ".cmd") or shutil.which(argv[0] + ".bat")
        if exe is None:
            self._note(f"✗ '{argv[0]}' not found — install Node.js to "
                       f"run this project's dev server.")
            return False
        argv[0] = exe
        kwargs = {
            "cwd": self.root,
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "bufsize": 1,
            "env": {
                **os.environ,
                "CI": "true",
                "npm_config_yes": "true",
                "NO_COLOR": "1",
                "FORCE_COLOR": "0",
            },
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            if argv[0].lower().endswith((".cmd", ".bat")):
                kwargs["shell"] = True
        try:
            self.proc = subprocess.Popen(argv, **kwargs)
        except Exception as e:
            self._note(f"✗ Failed to start dev server: {e}")
            return False

        reader = threading.Thread(target=self._pump, daemon=True,
                                  name="cat-devserver-reader")
        reader.start()

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                self._note("✗ Dev server exited immediately:\n"
                           + self.last_output)
                return False
            with self._lock:
                if self.url:
                    self._note(f"● Dev server ready — {self.url}")
                    return True
            # Fast probe during startup in case devserver buffered output
            for common_p in (5173, 3001, 8080, 5000, 4173, 3000):
                if probe_local_server(common_p):
                    with self._lock:
                        if not self.url:
                            self.url = f"http://127.0.0.1:{common_p}/"
                            self._note(f"● Dev server ready on port {common_p} — {self.url}")
                            return True
            time.sleep(0.05)
        self._note("✗ Dev server did not report a URL in time.")
        return False

    def _pump(self):
        """Reader thread: scan output lines for the local URL."""
        try:
            assert self.proc is not None and self.proc.stdout is not None
            for line in self.proc.stdout:
                line = line.rstrip()
                if not line:
                    continue
                with self._lock:
                    self._tail.append(line)
                    del self._tail[:-200:]
                found = extract_local_url(line)
                if found and not self.url:
                    try:
                        import urllib.parse
                        p = urllib.parse.urlparse(found)
                        if p.port and is_fomoji_server(p.port, p.hostname or "127.0.0.1"):
                            continue
                    except Exception:
                        pass
                    self.url = found
        except Exception:
            pass

    def _note(self, text):
        try:
            self._on_activity(text)
        except Exception:
            pass

    # --------------------------------------------------------------- stop --
    def stop(self):
        """Kill the whole process tree. Idempotent; never raises."""
        proc, self.proc = self.proc, None
        self.url = ""
        if proc is None or proc.poll() is not None:
            return
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                    capture_output=True, timeout=8)
            else:
                proc.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=6)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
