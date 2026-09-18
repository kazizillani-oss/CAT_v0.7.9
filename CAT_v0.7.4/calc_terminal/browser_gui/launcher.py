"""
DEPRECATED — Legacy separate-window browser launcher. NOT the normal Browser Mode.

Normal Browser Mode uses calc_terminal.host.desktop.EmbeddedBrowserPane
(QWebEngineView = real Chromium) instead, which is owned by CAT and runs
in the same process.

This module is kept for backward compatibility only. Do NOT use it as
the primary browser entry point.
"""

from __future__ import annotations

import os
import sys
import subprocess
import pathlib

def _has_module(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False

def _launch_with_pyside(start_url: str) -> int:
    try:
        from .qt_browser import launch_qt_browser
        return launch_qt_browser(start_url)
    except Exception as e:
        print(f"[CAT Browser] PySide6 launch failed: {e}", file=sys.stderr)
        return 1

def _launch_with_pyqt(start_url: str) -> int:
    try:
        # Qt browser is written for PySide6, but PyQt6 API is almost identical
        # We try to reuse same file with an alias
        import importlib
        # Force import as PySide6 name if only PyQt6 installed — our qt_browser
        # already handles both via try/except inside
        from .qt_browser import launch_qt_browser
        return launch_qt_browser(start_url)
    except Exception as e:
        print(f"[CAT Browser] PyQt launch failed: {e}", file=sys.stderr)
        return 1

def _launch_with_webview(start_url: str) -> int:
    try:
        from .webview_browser import launch_webview_browser
        return launch_webview_browser(start_url)
    except Exception as e:
        print(f"[CAT Browser] pywebview launch failed: {e}", file=sys.stderr)
        return 1

def _launch_with_playwright(start_url: str) -> int:
    try:
        from .playwright_browser import launch_playwright_browser
        return launch_playwright_browser(start_url)
    except Exception as e:
        print(f"[CAT Browser] Playwright launch failed: {e}", file=sys.stderr)
        return 1

def launch_browser_gui(start_url: str = "about:home", block: bool = True) -> int:
    """
    LEGACY separate-window launcher — DEPRECATED for normal Browser Mode.

    Per the architecture fix, normal Browser Mode must NOT open a separate OS
    window (webbrowser.open / Chrome / Edge / this launcher's old path).
    It must create/show CAT's EMBEDDED browser view (QWebEngineView child of
    CAT Host, inside the same CAT window that holds the terminal).

    This function now ONLY delegates to the Host embedded path. If no
    embedded engine is available, it ERRORS with install instructions
    instead of launching a separate Chrome/Edge window (which would violate
    the single-process requirement).

    Normal code must call:  from calc_terminal.host.launcher import launch_cat_host
    """
    # Prefer Host embedded (correct architecture) when available
    try:
        from ..host.launcher import can_launch_host, launch_cat_host, get_host_status  # type: ignore
        if can_launch_host():
            # Delegate to Host — Browser INSIDE CAT (embedded QWebEngineView)
            return launch_cat_host(start_browser_url=start_url, start_mode="browser", block=block)
        else:
            st = get_host_status()
            print(f"[CAT Browser] ERROR: No EMBEDDED engine — cannot show Browser INSIDE CAT.", file=sys.stderr)
            print(f"[CAT Browser] {st['reason']}", file=sys.stderr)
            print("[CAT Browser] Install: pip install PySide6  (QWebEngineView child inside CAT Host)", file=sys.stderr)
            print("[CAT Browser] Not launching separate Chrome/Edge (violates architecture).", file=sys.stderr)
            print(f"[CAT Browser] URL that would have rendered inside CAT: {start_url}", file=sys.stderr)
            return 2
    except SystemExit:
        raise
    except Exception as e:
        print(f"[CAT Browser] Host delegate failed ({e}) — not launching external.", file=sys.stderr)
        return 1
    # Legacy separate-window fallback REMOVED — Browser Mode must be embedded.
    # The old _launch_with_* paths are kept below only for diagnostics but are
    # NOT used for normal Browser Mode. Do not re-enable them without fixing
    # the architecture violation.
    # Check for a custom browser backend override
    backend = os.environ.get("CAT_BROWSER_BACKEND", "").lower().strip()

    # If block=False, spawn a new process so CAT terminal stays usable
    if not block:
        # Spawn detached process: python -m calc_terminal.browser_gui --url <url>
        try:
            cmd = [sys.executable, "-m", "calc_terminal.browser_gui", "--url", start_url]
            kwargs = {}
            if os.name == "nt":
                # DETACHED_PROCESS
                import subprocess as sp
                kwargs["creationflags"] = sp.DETACHED_PROCESS | sp.CREATE_NEW_PROCESS_GROUP  # type: ignore
            else:
                kwargs["start_new_session"] = True
            subprocess.Popen(cmd, **kwargs, cwd=os.getcwd())
            return 0
        except Exception as e:
            print(f"[CAT Browser] Failed to spawn browser process: {e}", file=sys.stderr)
            return 1

    # Block path — try backends in order (or forced)
    if backend in ("pyside", "pyside6"):
        return _launch_with_pyside(start_url)
    if backend in ("pyqt", "pyqt6"):
        return _launch_with_pyqt(start_url)
    if backend in ("playwright", "pw"):
        return _launch_with_playwright(start_url)
    if backend in ("webview", "pywebview"):
        return _launch_with_webview(start_url)

    # Auto-detect — Playwright is already required for CAT Preview, so it will be available
    # and gives a real Chromium window without extra Qt install
    if _has_module("PySide6"):
        rc = _launch_with_pyside(start_url)
        if rc == 0:
            return rc
    if _has_module("PyQt6"):
        rc = _launch_with_pyqt(start_url)
        if rc == 0:
            return rc
    # Playwright visible window is always available if CAT Preview works — use it as primary fallback
    # (real HTML/CSS/JS, no text extraction)
    if _has_module("playwright"):
        rc = _launch_with_playwright(start_url)
        if rc == 0:
            return rc
    if _has_module("webview"):
        rc = _launch_with_webview(start_url)
        if rc == 0:
            return rc

    # No GUI backend installed
    print("\n[CAT Browser] No graphical browser backend found.", file=sys.stderr)
    print("Install one of (Playwright already covers Preview, but for standalone window):", file=sys.stderr)
    print("  pip install playwright && playwright install chromium  # already for CAT Preview", file=sys.stderr)
    print("  pip install PySide6   # full browser with tabs/toolbar", file=sys.stderr)
    print("  pip install pywebview # lightweight WebView2", file=sys.stderr)
    print("\nAfter installing, run again:", file=sys.stderr)
    print(f"  cat browse {start_url}" if start_url != "about:home" else "  cat browse", file=sys.stderr)
    return 2

def main():
    import argparse
    p = argparse.ArgumentParser(description="CAT Browser — graphical WebView2/Chromium window")
    p.add_argument("--url", default="about:home", help="URL to open")
    p.add_argument("--no-block", action="store_true", help="Don't block, spawn detached")
    args = p.parse_args()
    sys.exit(launch_browser_gui(args.url, block=not args.no_block))

if __name__ == "__main__":
    main()
