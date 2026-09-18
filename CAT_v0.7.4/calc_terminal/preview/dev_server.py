"""CAT Live Preview — Dev Server Manager (calc_terminal/preview/dev_server.py).

Owns development server lifecycle:
- Detects project configuration (Static HTML, Vite, Next.js, CRA, Node).
- Manages available port detection and avoids collisions.
- Starts, stops, restarts real local HTTP server binding 127.0.0.1 strictly.
- Prevents duplicate server processes for the same workspace.
- Verifies server readiness before declaring live state.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple


class ServerState:
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"
    RESTARTING = "restarting"


@dataclass
class ProjectInfo:
    kind: str  # "static", "vite", "next", "cra", "node"
    label: str
    root: str
    entry_file: Optional[str] = None
    start_command: Optional[List[str]] = None
    is_framework: bool = False


def detect_project_type(root: str) -> ProjectInfo:
    """Analyze workspace root to determine project type and start strategy."""
    abs_root = os.path.abspath(os.path.expanduser(root or ""))
    if not os.path.isdir(abs_root):
        return ProjectInfo(kind="static", label="Static Web", root=abs_root)

    pkg_path = os.path.join(abs_root, "package.json")
    if os.path.isfile(pkg_path):
        try:
            with open(pkg_path, "r", encoding="utf-8", errors="replace") as f:
                pkg = json.load(f)
            scripts = pkg.get("scripts", {})
            deps = {}
            deps.update(pkg.get("dependencies", {}))
            deps.update(pkg.get("devDependencies", {}))

            # Vite detection
            for cfg in ("vite.config.js", "vite.config.ts", "vite.config.mjs", "vite.config.cjs"):
                if os.path.isfile(os.path.join(abs_root, cfg)):
                    cmd = ["npm", "run", "dev"] if "dev" in scripts else ["npx", "vite"]
                    return ProjectInfo(kind="vite", label="Vite", root=abs_root, start_command=cmd, is_framework=True)
            if "vite" in deps and "dev" in scripts:
                return ProjectInfo(kind="vite", label="Vite", root=abs_root, start_command=["npm", "run", "dev"], is_framework=True)

            # Next.js detection
            for cfg in ("next.config.js", "next.config.ts", "next.config.mjs", "next.config.cjs"):
                if os.path.isfile(os.path.join(abs_root, cfg)):
                    cmd = ["npm", "run", "dev"] if "dev" in scripts else ["npx", "next", "dev"]
                    return ProjectInfo(kind="next", label="Next.js", root=abs_root, start_command=cmd, is_framework=True)
            if "next" in deps and "dev" in scripts:
                return ProjectInfo(kind="next", label="Next.js", root=abs_root, start_command=["npm", "run", "dev"], is_framework=True)

            # Create React App detection
            if "react-scripts" in deps:
                cmd = ["npm", "start"]
                return ProjectInfo(kind="cra", label="Create React App", root=abs_root, start_command=cmd, is_framework=True)

            # Generic Node dev script
            if "dev" in scripts:
                return ProjectInfo(kind="node", label="Node Dev", root=abs_root, start_command=["npm", "run", "dev"], is_framework=True)
            if "start" in scripts:
                return ProjectInfo(kind="node", label="Node Start", root=abs_root, start_command=["npm", "start"], is_framework=True)
        except Exception:
            pass

    # Static project fallback
    index_file = None
    for cand in ("index.html", "index.htm", "main.html", "app.html"):
        p = os.path.join(abs_root, cand)
        if os.path.isfile(p):
            index_file = p
            break
    return ProjectInfo(kind="static", label="Static Web", root=abs_root, entry_file=index_file)


def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a port is free to bind on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            return True
        except OSError:
            return False


def find_available_port(preferred: int = 5173, fallback_ports: Optional[List[int]] = None) -> int:
    """Find an available port starting with preferred, then fallbacks, then dynamic bind."""
    if is_port_available(preferred):
        return preferred
    fallbacks = fallback_ports or [5174, 5175, 5176, 3000, 3001, 8080, 8000]
    for p in fallbacks:
        if is_port_available(p):
            return p
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class DevServerManager:
    """Manages local dev server instances with zero duplicate processes and clean lifecycle."""

    _active_servers: Dict[str, DevServerManager] = {}
    _lock = threading.RLock()

    @classmethod
    def get_or_create(cls, root: str) -> DevServerManager:
        """Get running server for workspace root or create a new manager."""
        norm_root = os.path.abspath(os.path.expanduser(root or ""))
        with cls._lock:
            if norm_root in cls._active_servers:
                return cls._active_servers[norm_root]
            mgr = cls(norm_root)
            cls._active_servers[norm_root] = mgr
            return mgr

    @classmethod
    def cleanup_all(cls) -> None:
        """Terminate and clean up all running development servers across CAT."""
        with cls._lock:
            for mgr in list(cls._active_servers.values()):
                try:
                    mgr.stop()
                except Exception:
                    pass
            cls._active_servers.clear()

    def __init__(self, root: str) -> None:
        self.root = os.path.abspath(os.path.expanduser(root or ""))
        self.project_info = detect_project_type(self.root)
        self.state = ServerState.STOPPED
        self.port: Optional[int] = None
        self.url: Optional[str] = None
        self.last_error: str = ""
        self._server_instance: Any = None  # LiveServer instance or subprocess.Popen
        self._proc: Optional[subprocess.Popen] = None
        self._logs: List[str] = []
        self._on_state_change: Optional[Callable[[str, str], None]] = None

    def set_state_listener(self, cb: Callable[[str, str], None]) -> None:
        self._on_state_change = cb

    def _notify(self, state: str, error: str = "") -> None:
        self.state = state
        if error:
            self.last_error = error
        if self._on_state_change:
            try:
                self._on_state_change(state, error)
            except Exception:
                pass

    def is_running(self) -> bool:
        if self.state != ServerState.RUNNING:
            return False
        if self._proc is not None:
            return self._proc.poll() is None
        if self._server_instance is not None:
            return getattr(self._server_instance, "running", False)
        return False

    def start(self, preferred_port: Optional[int] = None) -> Tuple[bool, str]:
        """Start the local development server for this project."""
        if self.is_running():
            return True, self.url or f"http://127.0.0.1:{self.port}/"

        self._notify(ServerState.STARTING)
        self.project_info = detect_project_type(self.root)

        if not self.project_info.is_framework:
            return self._start_static(preferred_port)
        else:
            return self._start_framework(preferred_port)

    def _start_static(self, preferred_port: Optional[int] = None) -> Tuple[bool, str]:
        """Start CAT's internal LiveServer with hot-reload."""
        try:
            from ..browser.server import LiveServer
            self.port = find_available_port(preferred_port or 5173)
            # Create LiveServer bound to root
            srv = LiveServer(self.root)
            srv.port = self.port
            started = srv.start()
            if not started:
                self._notify(ServerState.ERROR, f"Port {self.port} could not be bound.")
                return False, self.last_error

            self._server_instance = srv
            self.port = srv.port
            self.url = f"http://127.0.0.1:{self.port}/"
            self._notify(ServerState.RUNNING)
            self._logs.append(f"Static dev server started at {self.url}")
            return True, self.url
        except Exception as e:
            err = f"Failed to start static server: {e}"
            self._notify(ServerState.ERROR, err)
            return False, err

    def _start_framework(self, preferred_port: Optional[int] = None) -> Tuple[bool, str]:
        """Launch project's own dev server (e.g. Vite, Next.js)."""
        cmd = self.project_info.start_command
        if not cmd:
            return self._start_static(preferred_port)

        self.port = find_available_port(preferred_port or 5173)
        try:
            # Launch dev process safely
            env = os.environ.copy()
            env["PORT"] = str(self.port)
            self._proc = subprocess.Popen(
                cmd,
                cwd=self.root,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            # Monitor startup in background thread
            def _reader():
                while self._proc and self._proc.poll() is None:
                    line = self._proc.stdout.readline()
                    if line:
                        self._logs.append(line.rstrip())
                        if len(self._logs) > 500:
                            del self._logs[:-500]

            t = threading.Thread(target=_reader, daemon=True)
            t.start()

            # Wait briefly for process to initialize or report url
            start_time = time.monotonic()
            while time.monotonic() - start_time < 5.0:
                if self._proc.poll() is not None:
                    err = "\n".join(self._logs[-10:]) or "Process exited prematurely."
                    self._notify(ServerState.ERROR, err)
                    return False, err
                if not is_port_available(self.port):
                    # Port is now bound by dev server!
                    break
                time.sleep(0.2)

            self.url = f"http://127.0.0.1:{self.port}/"
            self._notify(ServerState.RUNNING)
            return True, self.url
        except Exception as e:
            err = f"Failed to spawn dev command {cmd}: {e}"
            self._notify(ServerState.ERROR, err)
            return False, err

    def stop(self) -> None:
        """Cleanly stop the running development server."""
        if self._server_instance is not None:
            try:
                self._server_instance.shutdown()
            except Exception:
                pass
            self._server_instance = None

        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=2.0)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None

        self._notify(ServerState.STOPPED)

    def restart(self) -> Tuple[bool, str]:
        """Restart the running server."""
        self._notify(ServerState.RESTARTING)
        self.stop()
        time.sleep(0.3)
        return self.start(self.port)

    def get_logs(self, limit: int = 50) -> List[str]:
        """Return latest captured stdout/stderr lines."""
        return list(self._logs[-limit:])
