"""
CAT v0.7.9.0 — fs_cache.py: safe, self-invalidating filesystem metadata
cache (requirement #12 — SMART CACHING).

Caches the expensive-to-rebuild, cheap-to-key results CAT asks for over
and over inside one agent run:

* directory listings   (keyed by path; invalidated by that directory's
                        mtime AND by explicit mutation notifications)
* workspace index      (keyed by root + a cheap signature of the tree)

Correctness rules:
* NEVER return stale data after a known mutation: every write/rename/
  delete tool call in agent.py notifies invalidate_path(), and each cache
  hit re-checks the directory's own mtime first — an external change made
  outside CAT is picked up automatically.
* TTL is short (2 s) on purpose: it collapses repeated scans WITHIN one
  agent step burst without ever serving yesterday's view of the world.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import os
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

DEFAULT_TTL = 2.0          # seconds
MAX_ENTRIES = 256

_lock = threading.Lock()
_store: Dict[str, Tuple[float, Any]] = {}      # key -> (expires_at, value)
_signatures: Dict[str, Tuple] = {}             # key -> validity signature


def _dir_signature(path: str) -> Tuple:
    """Cheap validity probe: directory mtime (+ its own existence). An
    external add/remove/update inside the dir changes st_mtime, so the
    cached listing goes stale immediately."""
    try:
        st = os.stat(path)
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return ("missing",)


def get_cached(key: str):
    with _lock:
        entry = _store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at < time.time():
            _store.pop(key, None)
            _signatures.pop(key, None)
            return None
        return value


def put_cached(key: str, value, ttl: float = DEFAULT_TTL,
               signature: Optional[Tuple] = None) -> None:
    with _lock:
        if len(_store) >= MAX_ENTRIES:
            # Drop the soonest-expiring entries first.
            for k in sorted(_store, key=lambda k: _store[k][0])[:32]:
                _store.pop(k, None)
                _signatures.pop(k, None)
        _store[key] = (time.time() + max(0.05, ttl), value)
        if signature is not None:
            _signatures[key] = signature


def valid_signature(key: str, signature: Tuple) -> bool:
    with _lock:
        return _signatures.get(key) == signature


def invalidate_path(path: str) -> None:
    """Called by every mutating tool (write/create/delete/rename) so no
    cached listing can ever outlive a known change. Invalidates the path
    itself and all cached ancestors (a new file changes the parent's
    listing too)."""
    path = os.path.normpath(os.path.abspath(str(path)))
    with _lock:
        for key in [k for k in _store if k.startswith("dirls:")]:
            try:
                cached_path = key[len("dirls:"):]
                norm = os.path.normpath(os.path.abspath(cached_path))
            except Exception:
                continue
            if norm == path or path.startswith(norm + os.sep) \
                    or norm.startswith(path + os.sep):
                _store.pop(key, None)
                _signatures.pop(key, None)


def clear() -> None:
    with _lock:
        _store.clear()
        _signatures.clear()


def cached_dir_listing(path: str, builder: Callable[[], Any],
                       ttl: float = DEFAULT_TTL):
    """TTL+mtime-guarded directory listing. `builder` does the real scan;
    it only runs when there is no fresh, still-valid cached copy."""
    try:
        real = os.path.abspath(path)
    except Exception:
        return builder()
    key = "dirls:" + real
    sig = _dir_signature(real)
    cached = get_cached(key)
    if cached is not None and valid_signature(key, sig):
        return cached
    value = builder()
    put_cached(key, value, ttl=ttl, signature=sig)
    return value
