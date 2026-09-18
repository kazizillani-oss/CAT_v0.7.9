"""CAT browser/ — PreviewController: the one owner of preview lifecycle.

    ▷ click  ─► start_for_file(index.html)
                 ├─ LiveServer.start()          (127.0.0.1:auto port)
                 ├─ BrowserEngine.start()       (real Chromium)
                 ├─ navigate(entry url)
                 └─ PreviewFileWatcher.start()  (debounced live reload)

    ⏻ click  ─► stop_preview()   server/browser/watcher torn down,
                                 editor session untouched
    CAT exit ─► shutdown()       idempotent, atexit-registered

State model lives here (spec section 22): server_state + preview_state
progress STOPPED → STARTING → RUNNING/ERROR, and every transition is
reported through `on_event(kind, **info)` so the UI can render progress
without any of this code touching widgets.
"""

from __future__ import annotations

import atexit
import os
import threading
from typing import Callable, Optional

from .engine import BrowserEngine, PLAYWRIGHT_AVAILABLE
from .navigation import NavigationHistory
from .preview_entry import find_entry_file, relative_url_for
from .project_detector import (detect_project, dependencies_installed,
                               STATIC)
from .devserver import DevServerProcess
from .server import LiveServer
from .state import PreviewState, ServerState
from .watcher import PreviewFileWatcher, is_web_file


class PreviewController:
    """Owns Server + Engine + Watcher + Navigation for one workspace."""

    def __init__(self, root: str, engine: Optional[BrowserEngine] = None,
                 on_event: Optional[Callable] = None,
                 devserver_factory=None):
        self.root = os.path.abspath(os.path.expanduser(root))
        self.on_event = on_event or (lambda *a, **k: None)
        self.server = LiveServer(self.root)
        self.engine = engine or BrowserEngine()
        self.history = NavigationHistory()
        self.watcher: Optional[PreviewFileWatcher] = None
        # v0.7.10 spec section 19-20: framework workspaces (Vite/Next/
        # CRA) reuse THEIR OWN dev server; this factory builds that
        # process handle (injectable for tests).
        self._devserver_factory = devserver_factory or DevServerProcess
        self.devserver = None
        self.detection = detect_project(self.root)
        self.server_state = ServerState.STOPPED
        self.preview_state = PreviewState.STOPPED
        self.last_error = ""
        self.entry_url = ""
        self._lock = threading.RLock()
        self._hot_css_enabled = True
        self._pending_ai_paths = set()
        self._ai_debouncer = None
        _register_instance(self)

    # ------------------------------------------------------------ events --
    def _emit(self, kind: str, **info):
        try:
            self.on_event(kind, **info)
        except Exception:
            pass

    def _set_server_state(self, state: ServerState, error=""):
        self.server_state = state
        if error:
            self.last_error = error
        self._emit("server", state=state, error=error)

    def _set_preview_state(self, state: PreviewState, error=""):
        self.preview_state = state
        if error:
            self.last_error = error
        self._emit("preview", state=state, error=error)

    # ------------------------------------------------------------- props --
    @property
    def running(self) -> bool:
        if self.preview_state is not PreviewState.RUNNING:
            return False
        if self.devserver is not None:
            # External (framework) mode: the project's own server is
            # the source of truth, CAT's static one stays idle.
            return self.devserver.running or bool(self.history.current)
        return self.server.running

    @property
    def base_url(self) -> str:
        """The URL everything is served from right now."""
        if self.devserver is not None and self.devserver.url:
            return self.devserver.url
        return self.server.url

    @property
    def url(self) -> str:
        return self.history.current or ""

    # ------------------------------------------------------------- start --
    def _start_static_server(self) -> bool:
        """CAT's own 127.0.0.1 static LiveServer (the default path)."""
        self._emit("activity", text="● Starting local server…")
        self._set_server_state(ServerState.STARTING)
        if not self.server.running:
            if not self.server.start():
                self._set_server_state(
                    ServerState.ERROR,
                    "Failed to start development server "
                    "(port bind refused). CAT will retry next time.")
                self._set_preview_state(PreviewState.ERROR,
                                        "Server failed to start.")
                return False
        if not self.server.wait_ready():
            self._set_server_state(ServerState.ERROR,
                                   "Server did not answer.")
            self._set_preview_state(PreviewState.ERROR,
                                    "Server did not answer.")
            return False
        self._set_server_state(ServerState.RUNNING)
        return True

    def _start_framework_devserver(self, detection) -> bool:
        """Spec section 19-20: the project already HAS a dev server
        (Vite/Next/CRA) — start IT and reuse it; never stack a second
        server on top of a running one."""
        self._emit("activity", text=f"● {detection.label} detected — "
                                    f"starting its dev server…")
        self._set_server_state(ServerState.STARTING)
        ds = self._devserver_factory(
            detection.root, detection.command,
            on_activity=lambda t: self._emit("activity", text=t))
        if not ds.start():
            tail = getattr(ds, "last_output", "")
            self._set_server_state(
                ServerState.ERROR,
                f"{detection.label} dev server failed to start."
                + (f"\n{tail}" if tail else ""))
            self._set_preview_state(PreviewState.ERROR,
                                    "Dev server failed to start.")
            return False
        self.devserver = ds
        self._set_server_state(ServerState.RUNNING)
        return True

    def start_for_file(self, path: str) -> bool:
        """▷ — entry point from an open editor tab (or any html file).
        Detects the project type FIRST (spec section 20): framework
        projects get their own dev server + HMR; everything else is
        served by CAT's static LiveServer."""
        path = os.path.abspath(os.path.expanduser(path))
        entry, web_root = find_entry_file(path, self.root)

        # Re-detect per start: the workspace may have gained/lost its
        # package.json since this controller was created.
        self.detection = detect_project(self.root)
        detection = self.detection
        use_external = (detection.is_framework
                        and dependencies_installed(detection))
        if not entry and not use_external:
            self._set_preview_state(
                PreviewState.ERROR,
                "No HTML entry point found in this workspace.")
            self._emit("error", reason="no-entry")
            return False

        with self._lock:
            if use_external:
                # A Vite index.html at the project root is NOT a plain
                # static page — only the real dev server can render it.
                if not self._start_framework_devserver(detection):
                    return False
                url = self.devserver.url
            else:
                if not self._start_static_server():
                    return False
                rel = relative_url_for(entry, web_root) if entry else ""
                url = self.base_url.rstrip("/") + "/" + rel.lstrip("/")

            self.entry_url = url
            self.watcher = self._ensure_watcher()
            self._emit("activity", text="● Starting browser engine…")
            self._set_preview_state(PreviewState.STARTING)
            try:
                self.engine.start()
                snap = self.navigate(url, push=True)
                if snap is not None and snap.ok:
                    self._emit("activity", text="✓ Preview synchronized")
            except Exception as e:
                # Headless engine failed or Playwright missing — local server is still running
                # and fully functional for real-time viewing in CAT Browser app
                self._emit("activity", text=f"● Live server ready for CAT Browser: {url}")

            self._set_preview_state(PreviewState.RUNNING)
            return True

    def navigate_current_workspace(self) -> bool:
        """Preview the workspace root itself (no specific file)."""
        entry, _web_root = find_entry_file(None, self.root)
        if not entry:
            self._set_preview_state(PreviewState.ERROR,
                                    "No HTML entry point in this workspace.")
            return False
        return self.start_for_file(entry)

    # ---------------------------------------------------------- navigate --
    def navigate(self, url: str, push: bool = True):
        """Load a URL in the running preview; records history."""
        if not self.engine.available:
            self._set_preview_state(PreviewState.ERROR, "Browser not running.")
            return None
        self._emit("activity", text=f"● Loading {url}")
        try:
            snap = self.engine.navigate(url)
        except Exception as e:
            self._set_preview_state(PreviewState.ERROR, str(e))
            return None
        if push and url != self.history.current:
            self.history.push(url)
        else:
            self.history.replace_current(url)
        if snap.ok:
            self._set_preview_state(PreviewState.RUNNING)
        else:
            # A single broken page must not kill the whole stack.
            self._set_preview_state(PreviewState.ERROR, snap.error)
        self._emit("snapshot", snapshot=snap)
        return snap

    def reload(self):
        if not self.running and not self.engine.available:
            return None
        self._emit("activity", text="● Reloading preview…")
        try:
            snap = self.engine.reload()
        except Exception as e:
            self._set_preview_state(PreviewState.ERROR, str(e))
            return None
        if snap.ok:
            self._set_preview_state(PreviewState.RUNNING)
            self._emit("activity", text="✓ Preview synchronized")
        else:
            self._set_preview_state(PreviewState.ERROR, snap.error)
        self._emit("snapshot", snapshot=snap)
        return snap

    def back(self):
        target = self.history.back()
        if target is None:
            return None
        return self.navigate(target, push=False)

    def forward(self):
        target = self.history.forward()
        if target is None:
            return None
        return self.navigate(target, push=False)

    def open_path(self, path: str):
        """Navigate the RUNNING preview to a workspace file (URL bar /
        explorer integration). No-op when stopped."""
        if not self.running:
            return None
        rel = relative_url_for(os.path.abspath(path), self.root)
        if rel is None:
            return None
        return self.navigate(self.base_url.rstrip("/") + "/" + rel)

    # ------------------------------------------------------------ hot path --
    def on_files_changed(self, changed_paths) -> None:
        """Watcher/AI-write hook. Debounced upstream; decides between
        CSS-only hot update and full reload. Never raises.

        Framework mode (Vite/Next): their OWN HMR pipeline reacts to
        file changes — reloading again from CAT would double-fire — so
        we surface the activity lines (spec section 18) and leave the
        updating to the project's dev server."""
        try:
            paths = [p for p in (changed_paths or []) if is_web_file(p)]
            if not paths:
                return
            if self.devserver is not None and self.devserver.running:
                for p in sorted(paths)[:6]:
                    self._emit("activity",
                               text=f"● Writing {os.path.basename(p)}")
                self._emit("activity", text="✓ Framework HMR applied")
                return
            css_only = all(p.lower().endswith(".css") for p in paths)
            if css_only and self._hot_css_enabled:
                hrefs = [os.path.relpath(p, self.root).replace(os.sep, "/")
                         for p in paths]
                reached = self.server.notify_hot_css(hrefs)
                done = False
                if reached == 0 and getattr(self.engine, "available", False):
                    done = bool(self.engine.hot_css(hrefs))
                else:
                    done = True
                if done:
                    self._emit("activity",
                               text=f"✓ CSS updated ({len(paths)} file(s))")
                    return
            for p in sorted(paths)[:6]:
                self._emit("activity",
                           text=f"● Writing {os.path.basename(p)}")
            self.server.notify_reload()
            if getattr(self.engine, "available", False):
                self.reload()
        except Exception as e:
            self._emit("error", reason="hot-reload", detail=str(e))

    def notify_ai_wrote(self, path: str):
        """Explicit fast-path notification from CAT's own write tools —
        bypasses waiting for the OS watcher but STILL debounced (spec
        section 13): a burst of AI writes coalesces into ONE preview
        update ~150 ms after the last one lands."""
        try:
            if not is_web_file(path) or not self.engine.available:
                return
            with self._lock:
                self._pending_ai_paths.add(os.path.abspath(path))
                if self._ai_debouncer is None:
                    from .watcher import Debouncer
                    self._ai_debouncer = Debouncer()

            def flush():
                with self._lock:
                    batch = set(self._pending_ai_paths)
                    self._pending_ai_paths.clear()
                if batch:
                    self.on_files_changed(batch)

            self._ai_debouncer.schedule(flush)
        except Exception as e:
            self._emit("error", reason="ai-write", detail=str(e))

    # ----------------------------------------------------------- watcher --
    def _ensure_watcher(self) -> Optional[PreviewFileWatcher]:
        if self.watcher is not None and self.watcher.active \
                and self.watcher.root == self.root:
            return self.watcher
        try:
            watcher = PreviewFileWatcher(
                lambda batch: self.on_files_changed(batch),
                on_activity=lambda p: self._emit(
                    "activity",
                    text=f"● Writing {os.path.basename(p)}"))
            watcher.start(self.root)
            self.watcher = watcher
            return watcher
        except Exception:
            self.watcher = None
            return None

    # -------------------------------------------------------------- stop --
    def stop_preview(self):
        """⏻ — tear the preview down; the workspace/editor are untouched.
        Idempotent."""
        with self._lock:
            watcher, self.watcher = self.watcher, None
            if watcher is not None:
                try:
                    watcher.stop()
                except Exception:
                    pass
            try:
                self.engine.close()
            except Exception:
                pass
            try:
                self.server.stop()
            except Exception:
                pass
            devserver, self.devserver = self.devserver, None
            if devserver is not None:
                # Kill the framework's npm/node process TREE (§21: no
                # orphans survive CAT, crashes included — atexit calls
                # this same path).
                try:
                    devserver.stop()
                except Exception:
                    pass
            self.history.clear()
            self._set_preview_state(PreviewState.STOPPED)
            self._set_server_state(ServerState.STOPPED)

    def restart_engine(self):
        """Recover from a wedged browser without touching the server."""
        try:
            self.engine.close()
        except Exception:
            pass
        try:
            self.engine.start()
        except Exception as e:
            self._set_preview_state(PreviewState.ERROR, str(e))


# ---------------------------------------------------------------------------
# process-wide lifecycle: every controller ever created is stopped at exit
# so no orphan Chromium/server can survive CAT.
_CONTROLLERS = []
_atexit_installed = False


def _register_instance(ctrl: PreviewController):
    global _atexit_installed
    _CONTROLLERS.append(ctrl)
    del _CONTROLLERS[:-8:]           # keep the list bounded
    if not _atexit_installed:
        atexit.register(_shutdown_all)
        _atexit_installed = True


def _shutdown_all():
    for ctrl in list(_CONTROLLERS):
        try:
            ctrl.stop_preview()
        except Exception:
            pass


def playwright_available() -> bool:
    return PLAYWRIGHT_AVAILABLE
