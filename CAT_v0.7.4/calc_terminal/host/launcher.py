"""
CAT Browser Launcher - creates CAT's own browser window.

Entry point for CAT's embedded browser subsystem.
Creates a QWebEngineView-based browser window (same process).

Usage:
  from calc_terminal.host.launcher import launch_cat_host, can_launch_host
"""

from __future__ import annotations

import os
import sys
import pathlib

def _has_module(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def can_launch_host() -> bool:
    return _has_module("PySide6") or _has_module("PyQt6")


def get_host_status() -> dict:
    engines = []
    if _has_module("PySide6"):
        engines.append("PySide6 (Qt WebEngine)")
    if _has_module("PyQt6"):
        engines.append("PyQt6 (Qt WebEngine)")
    return {
        "available": bool(engines),
        "engines": engines,
        "preferred": engines[0] if engines else None,
        "reason": "ready" if engines else "no browser engine - install: pip install PySide6",
        "webview2_runtime": _webview2_runtime_version(),
    }


def _webview2_runtime_version() -> str:
    if sys.platform != "win32":
        return ""
    try:
        import winreg
        for path in [
            r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
            r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
        ]:
            try:
                k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
                pv, _ = winreg.QueryValueEx(k, "pv")
                winreg.CloseKey(k)
                return str(pv)
            except FileNotFoundError:
                continue
    except Exception:
        pass
    return ""


_PENDING_VERIFICATION_PATH = pathlib.Path.home() / ".cat_pending_verification.json"

def _store_pending_verification(url: str):
    try:
        import json, time
        payload = json.dumps({"url": url, "ts": time.time()})
        tmp_p = pathlib.Path.home() / ".cat_pending_verification.tmp"
        tmp_p.write_text(payload, encoding="utf-8")
        tmp_p.replace(_PENDING_VERIFICATION_PATH)
    except Exception:
        try:
            _PENDING_VERIFICATION_PATH.write_text(
                json.dumps({"url": url, "ts": time.time()}), encoding="utf-8"
            )
        except Exception:
            pass


def _ensure_qt_app():
    """Create or get existing QApplication. Returns (app, created_new)."""
    # Fix Qt WebEngine cache permission errors
    import tempfile
    _cache_path = os.path.join(tempfile.gettempdir(), "cat_qt_cache")
    os.makedirs(_cache_path, exist_ok=True)
    os.environ["QTWEBENGINE_CACHE_PATH"] = _cache_path
    # Performance: keep GPU enabled for smooth rendering, eliminate window occlusion flicker,
    # bound memory to 4 processes for low-end 4GB-8GB PCs, and enable smooth 60fps scrolling
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS",
                          "--disable-dev-shm-usage --enable-gpu-rasterization "
                          "--ignore-gpu-blocklist --enable-zero-copy "
                          "--disable-background-networking --disable-default-apps "
                          "--disable-features=CalculateNativeWinOcclusion "
                          "--renderer-process-limit=4 --smooth-scrolling "
                          "--disable-gpu-watchdog --num-raster-threads=2")
    os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

    try:
        from PySide6.QtCore import QCoreApplication, Qt
        from PySide6.QtWidgets import QApplication
    except ImportError:
        from PyQt6.QtCore import QCoreApplication, Qt  # type: ignore
        from PyQt6.QtWidgets import QApplication  # type: ignore

    # AA_ShareOpenGLContexts MUST be set before QApplication is instantiated to prevent surface tearing/flickering
    try:
        if hasattr(Qt.ApplicationAttribute, "AA_ShareOpenGLContexts"):
            QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    except Exception:
        pass

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        return app, True
    return app, False


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes, ctypes.wintypes
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if h:
                code = ctypes.wintypes.DWORD()
                ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
                ctypes.windll.kernel32.CloseHandle(h)
                return code.value == 259
            return False
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def launch_cat_host(
    start_browser_url: str | None = None,
    start_mode: str = "terminal",
    repl=None,
    block: bool = True,
) -> int:
    """Launch CAT's own browser window.

    block=True:  creates app + window + runs event loop (BLOCKS until closed).
    block=False: navigates existing window to URL (no new app, returns fast).
    """
    if start_browser_url in ("fatty", "--fatty", "cat web"):
        start_browser_url = "http://localhost:8765/"
        start_mode = "browser"

    if start_browser_url and "8765" in start_browser_url:
        try:
            from ..web.server import ensure_fatty_server
            ensure_fatty_server(timeout=5.0, auto_start=True)
        except Exception:
            pass

    if not block:
        url = start_browser_url or "about:home"
        _store_pending_verification(url)
        # 1. Check if running in current process
        try:
            try:
                from PySide6.QtWidgets import QApplication as _QApp
            except ImportError:
                from PyQt6.QtWidgets import QApplication as _QApp  # type: ignore
            app = _QApp.instance()
            if app is not None:
                for w in app.topLevelWidgets():
                    try:
                        if w.__class__.__name__ == "CATDesktopWindow" and hasattr(w, "browser"):
                            w.navigate(url)
                            if hasattr(w, "_bring_to_front"):
                                w._bring_to_front()
                            else:
                                w.show()
                                w.raise_()
                                w.activateWindow()
                            return 0
                    except Exception:
                        continue
        except Exception:
            pass

        # 2. Check if an external CAT Browser process is actively running (heartbeat within 3.5s)
        try:
            import time, json
            hb_path = pathlib.Path.home() / ".cat_browser_heartbeat"
            if hb_path.exists():
                is_running = False
                hwnd = 0
                try:
                    raw = hb_path.read_text(encoding="utf-8").strip()
                    if raw:
                        if raw.startswith("{"):
                            data = json.loads(raw)
                            hb_ts = float(data.get("ts", 0))
                            pid = int(data.get("pid", 0))
                            hwnd = int(data.get("hwnd", 0))
                        else:
                            hb_ts = float(raw)
                            pid = 0
                        if (time.time() - hb_ts) < 3.5:
                            if pid > 0:
                                is_running = _is_pid_alive(pid)
                            else:
                                is_running = True
                except Exception:
                    is_running = False

                if is_running:
                    # Active window will pick up _store_pending_verification within 250ms
                    # On Windows, immediately restore & bring it to foreground over maximized terminal!
                    if sys.platform == "win32":
                        try:
                            import ctypes
                            if hwnd <= 0 and pid > 0:
                                def _enum_cb(h, extra):
                                    lp = ctypes.c_ulong()
                                    ctypes.windll.user32.GetWindowThreadProcessId(h, ctypes.byref(lp))
                                    if lp.value == pid and ctypes.windll.user32.IsWindowVisible(h):
                                        extra.append(h)
                                        return False
                                    return True
                                WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.py_object)
                                found = []
                                ctypes.windll.user32.EnumWindows(WNDENUMPROC(_enum_cb), found)
                                if found:
                                    hwnd = found[0]

                            if hwnd > 0:
                                user32 = ctypes.windll.user32
                                kernel32 = ctypes.windll.kernel32
                                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                                fg_hwnd = user32.GetForegroundWindow()
                                fg_thread = user32.GetWindowThreadProcessId(fg_hwnd, None) if fg_hwnd else 0
                                cur_thread = kernel32.GetCurrentThreadId()
                                attached = False
                                if fg_thread and fg_thread != cur_thread:
                                    attached = bool(user32.AttachThreadInput(cur_thread, fg_thread, True))
                                swp_flags = 0x0001 | 0x0002 | 0x0040  # SWP_NOSIZE | SWP_NOMOVE | SWP_SHOWWINDOW
                                user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, swp_flags)  # HWND_TOPMOST
                                user32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, swp_flags)  # HWND_NOTOPMOST
                                user32.BringWindowToTop(hwnd)
                                user32.SetForegroundWindow(hwnd)
                                if attached:
                                    user32.AttachThreadInput(cur_thread, fg_thread, False)
                        except Exception:
                            pass
                    return 0
                else:
                    # Stale heartbeat file from dead/crashed process -> clean it up
                    hb_path.unlink(missing_ok=True)
        except Exception:
            pass

        # 3. No active CAT Browser window found -> spawn in background
        has_qt = _has_module("PySide6") or _has_module("PyQt6")
        if has_qt:
            import subprocess
            exe = sys.executable
            if sys.platform == "win32":
                pw = exe.replace("python.exe", "pythonw.exe")
                if os.path.exists(pw):
                    exe = pw
            # Source-checkout support only: a pip-installed CAT already has
            # `calc_terminal` importable, so never force PYTHONPATH/cwd to a
            # repo path that does not exist on the user's machine.
            candidate_root = pathlib.Path(__file__).resolve().parent.parent.parent
            is_source_checkout = (candidate_root / "calc_terminal").is_dir() and (
                candidate_root / "main.py"
            ).exists()
            env = os.environ.copy()
            popen_kwargs: dict = {}
            if is_source_checkout:
                ws_root = str(candidate_root)
                ppath = env.get("PYTHONPATH", "")
                env["PYTHONPATH"] = ws_root + (os.pathsep + ppath if ppath else "")
                popen_kwargs["cwd"] = ws_root
            cmd = [exe, "-m", "calc_terminal.host.launcher", "--url", url, "--mode", "browser"]
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
            try:
                subprocess.Popen(
                    cmd,
                    env=env,
                    creationflags=creationflags,
                    close_fds=(sys.platform != "win32"),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    **popen_kwargs,
                )
                return 0
            except Exception as e:
                print(f"[CAT Browser] failed to spawn background browser: {e}", file=sys.stderr)
        return 0

    has_qt = _has_module("PySide6") or _has_module("PyQt6")
    if has_qt:
        return _launch_with_qt(start_browser_url, start_mode, repl)

    print("\n[CAT Browser] No browser engine found.", file=sys.stderr)
    print("Install PySide6 for real HTML/CSS/JS rendering:", file=sys.stderr)
    print("  pip install PySide6", file=sys.stderr)
    return 2


def _launch_with_qt(start_browser_url, start_mode, repl) -> int:
    """Create the browser window AND run the event loop. BLOCKS until closed."""
    try:
        os.environ.setdefault(
            "QTWEBENGINE_CHROMIUM_FLAGS",
            "--disable-dev-shm-usage --enable-gpu-rasterization "
            "--ignore-gpu-blocklist --enable-zero-copy "
            "--disable-background-networking --disable-default-apps"
        )
        app, created = _ensure_qt_app()

        from .desktop import CATDesktopWindow
        initial_url = start_browser_url if (start_mode == "browser" or start_browser_url) else None
        w = CATDesktopWindow(repl=repl, start_browser_url=initial_url)
        w.show()
        try:
            if hasattr(w, "_bring_to_front"):
                w._bring_to_front()
            else:
                w.raise_()
                w.activateWindow()
        except Exception:
            pass

        if created:
            return app.exec()  # type: ignore
        return 0
    except Exception as e:
        import traceback
        print(f"[CAT Browser] launch failed: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1


def create_browser_window(start_browser_url=None, start_mode="browser", repl=None):
    """Create the browser window WITHOUT starting the event loop.

    Returns (app, window, created_new).
    Caller MUST call app.exec() after setting up other Qt objects.
    """
    os.environ.setdefault(
        "QTWEBENGINE_CHROMIUM_FLAGS",
        "--disable-dev-shm-usage --enable-gpu-rasterization "
        "--ignore-gpu-blocklist --enable-zero-copy "
        "--disable-background-networking --disable-default-apps"
    )
    app, created = _ensure_qt_app()

    from .desktop import CATDesktopWindow
    initial_url = start_browser_url if (start_mode == "browser" or start_browser_url) else None
    w = CATDesktopWindow(repl=repl, start_browser_url=initial_url)
    w.show()
    try:
        w.raise_()
        w.activateWindow()
    except Exception:
        pass
    return app, w, created


def main():
    import argparse
    p = argparse.ArgumentParser(description="CAT Browser - embedded Chromium")
    p.add_argument("url_pos", nargs="?", default=None, help="URL to open (positional)")
    p.add_argument("--url", default=None, help="URL to open")
    p.add_argument("--mode", choices=["terminal", "browser"], default="browser")
    p.add_argument("--no-block", action="store_true")
    p.add_argument("--status", action="store_true")
    p.add_argument("--fatty", action="store_true", help="Open Fatty CAT Web interface")
    args = p.parse_args()

    if args.status:
        import json
        print(json.dumps(get_host_status(), indent=2))
        return 0

    start_url = args.url or args.url_pos
    if args.fatty:
        start_url = "http://localhost:8765/"
        args.mode = "browser"
    elif start_url and "localhost" in start_url and args.mode == "terminal":
        args.mode = "browser"

    sys.exit(launch_cat_host(
        start_browser_url=start_url,
        start_mode=args.mode,
        block=not args.no_block,
    ))


if __name__ == "__main__":
    main()
