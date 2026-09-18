"""CAT Live Preview — Live Reload Manager (calc_terminal/preview/live_reload.py).

Debounced change aggregation and hot-reload dispatcher for local web projects.
Avoids restarting dev servers on ordinary keystrokes / edits.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Callable, List, Optional, Set


class LiveReloadManager:
    """Aggregates file modification events and emits debounced reload requests."""

    def __init__(self, debounce_sec: float = 0.25, on_reload: Optional[Callable[[List[str], bool], None]] = None) -> None:
        self.debounce_sec = debounce_sec
        self.on_reload = on_reload  # (changed_files, is_css_only) -> None
        self._pending_files: Set[str] = set()
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
        self._last_reload_time: float = 0.0

    def notify_file_changed(self, file_path: str) -> None:
        """Register that a file in the workspace was saved or edited."""
        abs_path = os.path.abspath(file_path)
        with self._lock:
            self._pending_files.add(abs_path)
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self.debounce_sec, self._flush)
            self._timer.daemon = True
            self._timer.start()

    def _flush(self) -> None:
        """Process pending changes and invoke reload callback."""
        with self._lock:
            if not self._pending_files:
                return
            files = list(self._pending_files)
            self._pending_files.clear()
            self._timer = None

        # Ignore if reloaded too frequently (avoid reload loops)
        now = time.monotonic()
        if now - self._last_reload_time < 0.1:
            return
        self._last_reload_time = now

        # Determine if CSS only
        is_css_only = all(f.lower().endswith(".css") for f in files)
        if self.on_reload:
            try:
                self.on_reload(files, is_css_only)
            except Exception:
                pass

    def cancel(self) -> None:
        """Cancel any pending debounce timer."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            self._pending_files.clear()
