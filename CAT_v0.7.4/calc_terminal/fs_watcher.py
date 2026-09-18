"""
CAT v0.7.9.0 — fs_watcher.py: real-time filesystem watching for the
live File Explorer.

Architecture (the whole point of this module):

    REAL FILESYSTEM
          |
      watcher (watchdog Observer, or a stdlib snapshot-poll fallback)
          |
    debounced filesystem events  ->  callback(set_of_changed_paths)
          |
    Workspace state manager (ui/app.py bridges to the UI thread)
          |
    Explorer tree refresh

The callback is ALWAYS invoked on a background thread — it must never
touch widgets. ui/app.py's `_on_fs_events` marshals the paths back to
the UI thread with call_from_thread and posts a WorkspaceFilesChanged
Message, exactly like every other worker-to-UI crossing in this app.

Design notes:

* watchdog's Observer is used when importable (real OS push events on
  Windows — ReadDirectoryChangesW — plus inotify/FSEvents elsewhere).
  When it isn't installed, a low-overhead stdlib poller takes over: it
  walks only the active workspace root every POLL_INTERVAL seconds,
  compares name/mtime snapshots, and reports only actual differences.
  That fallback is throttled by construction (one walk per interval,
  nothing between ticks) — never a busy loop.
* Events are debounced: bursts of related changes (a save writing a
  temp file then renaming it over the target; `git checkout` touching
  hundreds of files) coalesce into one callback ~DEBOUNCE seconds after
  the last raw event, so the Explorer reloads once, not N times.
* One watcher instance per app. `start(root)` stops whatever root was
  being watched before (new workspace => stop old watcher => start new
  watcher), so the Explorer can never observe a stale folder.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import os
import threading

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler as _WdHandler
    WATCHDOG_AVAILABLE = True
except Exception:
    WATCHDOG_AVAILABLE = False
    Observer = None

    class _WdHandler:  # stand-in so the class body below still parses
        pass


class WorkspaceWatcher:
    """Watches one workspace root and reports debounced change sets.

    Parameters
    ----------
    callback : callable(set[str])
        Invoked with the set of changed absolute paths. Always called
        from a background thread (the Observer's emitter thread or the
        fallback poller thread). Exceptions raised inside it must be
        its own responsibility.
    """

    DEBOUNCE = 0.35          # seconds of quiet before flushing a burst
    POLL_INTERVAL = 2.0      # fallback poll cadence (no watchdog)

    def __init__(self, callback):
        self._callback = callback
        self._root = None
        self._lock = threading.Lock()
        self._pending = set()
        self._debounce_timer = None
        self._observer = None
        self._poll_thread = None
        self._poll_stop = threading.Event()
        self._snapshot = {}

    # ------------------------------------------------------------ start --
    def start(self, root):
        """(Re)points the watcher at `root`. Stops the previous watch
        first, so switching workspaces never leaves an old Observer (or
        old poller) running against a folder that is no longer open."""
        root = os.path.abspath(os.path.expanduser(root))
        if not os.path.isdir(root):
            return False
        self.stop()
        with self._lock:
            self._root = root
            self._pending.clear()
        if WATCHDOG_AVAILABLE:
            return self._start_observer(root)
        return self._start_poller(root)

    def _start_observer(self, root):
        try:
            observer = Observer(timeout=0.5)
            observer.daemon = True
            handler = _Handler(self)
            # watch() on the root itself; recursive covers subfolders.
            # Windows/ReadDirectoryChangesW delivers create/delete/
            # rename/modify for everything below root.
            observer.schedule(handler, root, recursive=True)
            observer.start()
            self._observer = observer
            return True
        except Exception:
            # Watchdog exists but the platform refused the watch (rare
            # — e.g. a drive gone mid-call): fall back to polling.
            self._observer = None
            return self._start_poller(root)

    def _start_poller(self, root):
        self._poll_stop.clear()
        try:
            self._snapshot = self._scan(root)
        except Exception:
            self._snapshot = {}
        thread = threading.Thread(
            target=self._poll_loop, args=(root,),
            name="cat-fs-poll", daemon=True)
        thread.start()
        self._poll_thread = thread
        return True

    # ------------------------------------------------------------- stop --
    def stop(self):
        """Fully tears down whichever mechanism is running. Safe to call
        twice / when never started."""
        with self._lock:
            self._root = None
            self._cancel_debounce_locked()
        observer = self._observer
        self._observer = None
        if observer is not None:
            try:
                observer.stop()
                observer.join(timeout=2.0)
            except Exception:
                pass
        self._poll_stop.set()
        thread = self._poll_thread
        self._poll_thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        with self._lock:
            self._pending.clear()
        self._snapshot = {}

    @property
    def root(self):
        return self._root

    @property
    def active(self):
        return self._observer is not None or self._poll_thread is not None

    @property
    def event_based(self):
        """True when backed by real OS events (watchdog); False when the
        throttled poll fallback is in charge."""
        return self._observer is not None

    # ------------------------------------------------- event collection --
    def report(self, path):
        """Thread-safe event intake. Called by the watchdog handler for
        every raw filesystem event (and usable directly for explicit
        internal TOOL_FILE_* notifications). Bursts are coalesced and
        flushed once the stream goes quiet for DEBOUNCE seconds."""
        if path:
            with self._lock:
                if self._root is None:
                    return
                self._pending.add(os.path.abspath(path))
                self._cancel_debounce_locked()
                timer = threading.Timer(self.DEBOUNCE, self._flush)
                timer.daemon = True
                timer.start()
                self._debounce_timer = timer

    def _cancel_debounce_locked(self):
        timer = self._debounce_timer
        self._debounce_timer = None
        if timer is not None:
            timer.cancel()

    def _flush(self):
        with self._lock:
            batch = self._pending
            self._pending = set()
        if batch and self._callback is not None:
            try:
                self._callback(batch)
            except Exception:
                pass

    # ---------------------------------------------------- poll fallback --
    def _scan(self, root):
        """One shallow-everything snapshot: {path: mtime}. Directories
        get st_mtime too (Windows keeps dir mtimes fresh on content
        churn), so folder create/delete shows up as a diff without any
        special handling. Symlinks are never followed."""
        snap = {}
        stack = [root]
        while stack:
            current = stack.pop()
            try:
                snap[current] = os.stat(current).st_mtime
                with os.scandir(current) as entries:
                    for entry in entries:
                        try:
                            if entry.is_symlink():
                                continue
                            if entry.is_dir(follow_symlinks=False):
                                stack.append(entry.path)
                            else:
                                snap[entry.path] = entry.stat().st_mtime
                        except OSError:
                            continue
            except (OSError, PermissionError):
                continue
        return snap

    def _poll_loop(self, root):
        while not self._poll_stop.wait(self.POLL_INTERVAL):
            if self._root != root:
                return
            try:
                fresh = self._scan(root)
            except Exception:
                continue
            old = self._snapshot
            changed = {p for p in fresh.keys() ^ old.keys()}
            for p in fresh.keys() & old.keys():
                if fresh[p] != old[p]:
                    changed.add(p)
            if changed:
                self._snapshot = fresh
                for p in list(changed)[:64]:   # cap the burst size
                    self.report(p)
            else:
                # Keep mtimes fresh even when nothing changed, so the
                # next comparison stays cheap.
                self._snapshot = fresh


class _Handler(_WdHandler):
    """Watchdog adapter: forwards every interesting event kind into the
    watcher's debounced intake."""

    def __init__(self, watcher):
        super().__init__()
        self._watcher = watcher

    def on_created(self, event):
        self._emit(event.dest_path or event.src_path)

    def on_deleted(self, event):
        self._emit(event.src_path)

    def on_modified(self, event):
        self._emit(event.src_path)

    def on_moved(self, event):
        self._emit(event.src_path)
        self._emit(event.dest_path)

    def _emit(self, path):
        if path:
            self._watcher.report(path)
