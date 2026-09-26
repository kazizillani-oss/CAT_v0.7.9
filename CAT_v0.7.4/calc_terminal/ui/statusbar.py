"""
CCT UI — statusbar.py (spec v0.7 project structure list + "Status Bar"
section: Workspace / Current Model / GPU / Memory / CPU / API / Ollama
/ Simulation / Version / Time, one compact bottom line).

footer.py's `StatusLine` already implements exactly this rendering
contract (a zero-arg `get_fields()` callable returning
`[(label, value, tone), ...]`, joined into one dot-separated line, no
boxes) — see CCTApp._status_fields in ui/app.py. Per the v0.7 brief
("Do NOT rewrite working modules"), this file does not reimplement
that renderer a second time; it subclasses it under the spec's
expected filename and adds the field-gathering logic (memory/CPU via
the standard library only, Ollama reachability, simulation state,
version, wall-clock time) that CCTApp's `_status_fields` didn't cover
yet, so `ui/app.py` can hand this one callable instead of hand-rolling
those fields itself.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import os
import platform
import shutil
import threading
import time

from .. import permissions as perm
from .footer import StatusLine as _BaseStatusLine, TEXTUAL_AVAILABLE as _FOOTER_OK

TEXTUAL_AVAILABLE = _FOOTER_OK


def _memory_usage_mb():
    """Best-effort resident memory for *this* process, standard-library
    only (no psutil dependency). Returns None if the platform doesn't
    expose it (e.g. some minimal containers) rather than guessing."""
    try:
        import resource
        kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # ru_maxrss is KB on Linux, bytes on macOS.
        return kb / 1024 if platform.system() != "Darwin" else kb / (1024 * 1024)
    except Exception:
        return None


def _cpu_load_pct():
    """A cheap, dependency-free CPU signal: 1-minute load average
    divided by core count, as a percentage. Returns None on platforms
    without os.getloadavg() (e.g. Windows) — the caller shows 'n/a'
    rather than a fabricated number."""
    try:
        load1, _, _ = os.getloadavg()
        cores = os.cpu_count() or 1
        return min(100.0, 100.0 * load1 / cores)
    except (OSError, AttributeError):
        return None


def _ollama_reachable():
    """One short-timeout probe of the local Ollama server. Cached by
    the caller's refresh cadence (StatusLine already only redraws on
    its own interval), not on every field access."""
    try:
        import requests
        r = requests.get("http://localhost:11434/api/tags", timeout=0.3)
        return r.status_code == 200
    except Exception:
        return False


class StatusFields:
    """Gathers the spec's status-bar fields. Kept as a plain class (not
    a widget) so it's unit-testable without Textual, matching how
    thinking.py stays dependency-free — StatusBar below only renders
    what this computes."""

    def __init__(self, app_state_getter, version="0.8.ab"):
        """`app_state_getter` is a zero-arg callable returning a dict
        with keys this module doesn't otherwise know: 'model_label',
        'workspace', 'notebook_count', 'simulation', 'ollama_checked_at'.
        CCTApp supplies it; this class never reaches into CCTApp itself."""
        self._get_state = app_state_getter
        self._version = version
        self._ollama_ok = None
        self._ollama_last_check = 0.0
        self._ollama_lock = threading.Lock()
        self._ollama_probing = False

    def _ollama_status(self):
        """Last-known Ollama reachability — NEVER blocks the UI thread.
        A stale reading kicks one daemon-thread probe (guarded so
        probes can't stack); the fresh value lands on the next repaint.
        Until the first probe lands, None renders as '…' (unknown),
        never a fabricated up/down."""
        now = time.time()
        if now - self._ollama_last_check > 30:
            self._ollama_last_check = now
            self._kick_ollama_probe()
        return self._ollama_ok

    def _kick_ollama_probe(self):
        try:
            with self._ollama_lock:
                if self._ollama_probing:
                    return
                self._ollama_probing = True
        except Exception:
            return
        thread = threading.Thread(
            target=self._probe_ollama_bg, daemon=True)
        thread.start()

    def _probe_ollama_bg(self):
        try:
            ok = _ollama_reachable()
        except Exception:
            ok = False
        try:
            with self._ollama_lock:
                self._ollama_ok = ok
                self._ollama_probing = False
        except Exception:
            self._ollama_ok = ok
            self._ollama_probing = False

    def fields(self):
        state = self._get_state() or {}
        gpu_ok = bool(shutil.which("nvidia-smi"))
        net_ok = perm.manager.allowed("internet")
        mem_mb = _memory_usage_mb()
        cpu_pct = _cpu_load_pct()
        ollama_ok = self._ollama_status()

        out = [
            ("Workspace", state.get("workspace") or "none", ""),
            ("Model", state.get("model_label") or "none",
             "ready" if state.get("model_label") not in (None, "no model") else "warn"),
            ("GPU", "ready" if gpu_ok else "cpu-only", "ready" if gpu_ok else ""),
            ("Mem", f"{mem_mb:.0f}MB" if mem_mb is not None else "n/a", ""),
            ("CPU", f"{cpu_pct:.0f}%" if cpu_pct is not None else "n/a", ""),
            ("API", "allowed" if net_ok else "blocked", "ready" if net_ok else "err"),
            ("Ollama", "up" if ollama_ok else ("…" if ollama_ok is None else "down"),
             "ready" if ollama_ok else ""),
        ]
        sim = state.get("simulation")
        if sim:
            out.append(("Sim", sim, "ready"))
        out.append(("", f"v{self._version}", ""))
        out.append(("", time.strftime("%H:%M"), ""))
        return out


if TEXTUAL_AVAILABLE:

    class StatusBar(_BaseStatusLine):
        """Drop-in replacement for footer.StatusLine — identical
        rendering (inherited unchanged), richer field source. CCTApp
        constructs this with a StatusFields instance's `.fields` bound
        method instead of its own ad hoc `_status_fields`."""

        def __init__(self, status_fields: StatusFields, id="cct-statusline"):
            super().__init__(status_fields.fields, id=id)

else:
    StatusBar = None
