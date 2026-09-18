"""CAT browser/ — debounced workspace watch for WEB files.

Reuses fs_watcher.WorkspaceWatcher's proven watchdog/poller machinery,
narrowed to what a website preview cares about:

    .html .htm .css .js .mjs .json .svg   (+ image/font assets)

and re-debounced to PREVIEW_DEBOUNCE (150 ms, spec section 13) so a
burst of AI writes coalesces into ONE preview update:

    AI writes index.html ─┐
    AI writes style.css  ─┼─► quiet 150ms ─► callback({paths}) ─► reload
    AI writes app.js     ─┘

The callback always fires on a background thread (same contract as
fs_watcher) and receives absolute paths.
"""

import os
import threading

from ..fs_watcher import WorkspaceWatcher
from .server import WEB_EXTENSIONS

PREVIEW_DEBOUNCE = 0.15     # spec: wait 100–200 ms after the last change
ASSET_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".avif",
    ".woff", ".woff2", ".ttf", ".otf", ".svg",
}


def is_web_file(path: str) -> bool:
    _, ext = os.path.splitext(str(path).lower())
    return ext in WEB_EXTENSIONS or ext in ASSET_EXTENSIONS


class PreviewFileWatcher(WorkspaceWatcher):
    """WorkspaceWatcher tuned for live preview:

    * DEBOUNCE = 150 ms (the Explorer's copy stays at 350 ms);
    * only web-relevant paths reach the callback;
    * `on_activity` fires per accepted change batch so the UI can show
      '● Writing style.css' style build activity without polling.
    """

    DEBOUNCE = PREVIEW_DEBOUNCE

    def __init__(self, callback, on_activity=None):
        self._user_callback = callback
        self._activity = on_activity
        super().__init__(self._filtered_flush)

    def _filtered_flush(self, batch):
        web = {p for p in batch if is_web_file(p)}
        if not web:
            return
        try:
            if self._activity is not None:
                for p in sorted(web)[:12]:
                    self._activity(p)
        except Exception:
            pass
        try:
            self._user_callback(web)
        except Exception:
            pass


class Debouncer:
    """Generic trailing-edge debounce usable by tests and the controller:
    schedule(fn) resets a 150 ms timer; fn runs once after quiet."""

    def __init__(self, delay=PREVIEW_DEBOUNCE):
        self.delay = delay
        self._timer = None
        self._lock = threading.Lock()

    def schedule(self, fn):
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            timer = threading.Timer(self.delay, self._run, args=(fn,))
            timer.daemon = True
            self._timer = timer
            timer.start()

    def _run(self, fn):
        with self._lock:
            self._timer = None
        try:
            fn()
        except Exception:
            pass

    def cancel(self):
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
