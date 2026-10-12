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
from .diagnostics import install_diagnostics, install_qt_message_handler, log_exception

install_diagnostics()

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


def get_optimal_chromium_flags() -> str:
    """Keep Chromium's normal GPU, process isolation, and raster heuristics."""
    # Forced renderer/raster limits made unrelated tabs share a renderer and
    # let one renderer fault take down several sites. Chromium already adapts
    # these choices to the active GPU, RAM, and platform; keep its defaults.
    # In particular, do not disable GPU acceleration or its crash protections.
    flags = ["--no-default-browser-check"]
    if sys.platform.startswith("linux"):
        flags.append("--disable-dev-shm-usage")
    if os.environ.get("CAT_BROWSER_GPU_COMPOSITING", "").lower() == "compat":
        # Used only after the supervised GPU-composited browser process faults.
        # Chromium keeps other GPU APIs available while using software compositing.
        flags.append("--disable-gpu-compositing")
    return " ".join(flags)


def _ensure_qt_app():
    """Create or get existing QApplication. Returns (app, created_new)."""
    # Fix Qt WebEngine cache permission errors
    import tempfile
    _cache_path = os.path.join(tempfile.gettempdir(), "cat_qt_cache")
    os.makedirs(_cache_path, exist_ok=True)
    os.environ["QTWEBENGINE_CACHE_PATH"] = _cache_path
    
    # Adaptive anti-flicker & performance flags
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = get_optimal_chromium_flags()
    if sys.platform.startswith("linux") and hasattr(os, "geteuid") and os.geteuid() == 0:
        os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

    try:
        from PySide6.QtCore import QCoreApplication, Qt
        from PySide6.QtWidgets import QApplication
    except ImportError:
        from PyQt6.QtCore import QCoreApplication, Qt  # type: ignore
        from PyQt6.QtWidgets import QApplication  # type: ignore

    # AA_ShareOpenGLContexts prevents surface tearing and flicker
    try:
        if hasattr(Qt.ApplicationAttribute, "AA_ShareOpenGLContexts"):
            QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
        # On Windows, Direct3D 11 via ANGLE is rock-solid and eliminates OpenGL ICD driver flickering.
        # Only use desktop OpenGL if on Linux or explicitly requested.
        if sys.platform != "win32" and hasattr(Qt.ApplicationAttribute, "AA_UseDesktopOpenGL"):
            QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_UseDesktopOpenGL, True)
    except Exception:
        pass

    # On Windows, register explicit AppUserModelID BEFORE any window / QApplication is created
    # so Windows Shell groups and shows CAT Browser with its own identity instead of Python.exe
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("kazizillani.cat.browser.v08")
        except Exception:
            pass

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
        # Apply official CAT Browser icon to application instance early
        try:
            from ..terminal_identity import get_browser_icon_path
            ico = get_browser_icon_path()
            if ico and os.path.isfile(ico):
                try:
                    from PySide6.QtGui import QIcon
                except ImportError:
                    from PyQt6.QtGui import QIcon  # type: ignore
                app.setWindowIcon(QIcon(ico))
        except Exception:
            pass
        install_qt_message_handler()
        return app, True
    install_qt_message_handler()
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
    elif start_browser_url in ("terminal", "--terminal", "cli", "--cli", "console", "cat terminal", "about:cat-cli"):
        start_browser_url = "about:home"
        start_mode = "browser"
    elif start_browser_url in ("viewer", "--viewer", "about:viewer"):
        start_browser_url = "http://localhost:8765/viewer.html"
        start_mode = "browser"
    elif start_browser_url in ("fomoji", "--fomoji", "login", "auth"):
        start_browser_url = "http://localhost:3000/home.html"
        start_mode = "browser"

    if start_browser_url:
        try:
            p = pathlib.Path(start_browser_url).expanduser()
            if p.exists() and p.is_file():
                start_browser_url = p.resolve().as_uri()
                start_mode = "browser"
        except Exception:
            pass

    if start_browser_url and "8765" in start_browser_url:
        try:
            from ..web.server import ensure_fatty_server
            ensure_fatty_server(timeout=5.0, auto_start=True)
        except Exception:
            pass

    if start_browser_url and ("3000" in start_browser_url or "fomoji" in start_browser_url):
        try:
            from ..fomoji_manager import check_server_reachable, initialize_fomoji_subsystem
            if not check_server_reachable(timeout=0.8):
                initialize_fomoji_subsystem(interactive=False)
        except Exception:
            pass

    url = start_browser_url or "about:home"
    if start_browser_url or start_mode == "browser" or not block:
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
                        if hasattr(w, "navigate"):
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
                                is_running = False
                except Exception:
                    is_running = False

                if is_running:
                    # Active window will pick up _store_pending_verification within 250ms
                    # On Windows, strictly verify that a visible window exists before returning 0!
                    if sys.platform == "win32":
                        try:
                            import ctypes
                            user32 = ctypes.windll.user32
                            if hwnd > 0 and (not user32.IsWindow(hwnd) or not user32.IsWindowVisible(hwnd)):
                                hwnd = 0
                            if hwnd <= 0 and pid > 0:
                                def _enum_cb(h, extra):
                                    lp = ctypes.c_ulong()
                                    user32.GetWindowThreadProcessId(h, ctypes.byref(lp))
                                    if lp.value == pid and user32.IsWindowVisible(h):
                                        extra.append(h)
                                        return False
                                    return True
                                WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.py_object)
                                found = []
                                user32.EnumWindows.argtypes = [WNDENUMPROC, ctypes.py_object]
                                user32.EnumWindows.restype = ctypes.c_bool
                                user32.EnumWindows(WNDENUMPROC(_enum_cb), found)
                                if found:
                                    hwnd = found[0]

                            if hwnd > 0 and user32.IsWindow(hwnd) and user32.IsWindowVisible(hwnd):
                                kernel32 = ctypes.windll.kernel32
                                if user32.IsIconic(hwnd):
                                    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                                fg_hwnd = user32.GetForegroundWindow()
                                if fg_hwnd != hwnd:
                                    fg_thread = user32.GetWindowThreadProcessId(fg_hwnd, None) if fg_hwnd else 0
                                    cur_thread = kernel32.GetCurrentThreadId()
                                    attached = False
                                    if fg_thread and fg_thread != cur_thread:
                                        attached = bool(user32.AttachThreadInput(cur_thread, fg_thread, True))
                                    if hasattr(user32, "SwitchToThisWindow"):
                                        user32.SwitchToThisWindow(hwnd, True)
                                    user32.BringWindowToTop(hwnd)
                                    user32.SetForegroundWindow(hwnd)
                                    if attached:
                                        user32.AttachThreadInput(cur_thread, fg_thread, False)
                                return 0
                            else:
                                # No visible window found — dead/ghost background process, spawn fresh window!
                                is_running = False
                                hb_path.unlink(missing_ok=True)
                        except Exception:
                            is_running = False
                            hb_path.unlink(missing_ok=True)
                    else:
                        return 0
                else:
                    # Stale heartbeat file from dead/crashed process -> clean it up
                    hb_path.unlink(missing_ok=True)
        except Exception:
            pass

    if not block:
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
            cmd = [exe, "-m", "calc_terminal.host.supervisor", "--url", url]
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
        if os.environ.get("CAT_BROWSER_SUPERVISED_CHILD") != "1":
            from .supervisor import run_supervisor
            return run_supervisor(url)
        return _launch_with_qt(start_browser_url, start_mode, repl)

    print("\n[CAT Browser] No browser engine found.", file=sys.stderr)
    print("Install PySide6 for real HTML/CSS/JS rendering:", file=sys.stderr)
    print("  pip install PySide6", file=sys.stderr)
    return 2


def _launch_with_qt(start_browser_url, start_mode, repl) -> int:
    """Create the browser window AND run the event loop. BLOCKS until closed."""
    try:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = get_optimal_chromium_flags()
        app, created = _ensure_qt_app()

        initial_url = start_browser_url if (start_mode == "browser" or start_browser_url) else None
        try:
            from .desktop import CATDesktopWindow
            w = CATDesktopWindow(repl=repl, start_browser_url=initial_url)
        except Exception:
            log_exception("desktop_window_creation_failed", fallback="standalone_qt_browser")
            # Fallback to standalone Qt browser window if Desktop wrapper has an issue
            from ..browser_gui.qt_browser import CATBrowserWindow
            w = CATBrowserWindow(start_url=initial_url)

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
        log_exception("browser_launch_failed")
        import traceback
        print(f"[CAT Browser] launch failed: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1


def create_browser_window(start_browser_url=None, start_mode="browser", repl=None):
    """Create the browser window WITHOUT starting the event loop.

    Returns (app, window, created_new).
    Caller MUST call app.exec() after setting up other Qt objects.
    """
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = get_optimal_chromium_flags()
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
    p.add_argument("url_pos", nargs="?", default=None, help="URL or file to open (positional)")
    p.add_argument("--url", default=None, help="URL or file to open")
    p.add_argument("--mode", choices=["terminal", "browser"], default="browser")
    p.add_argument("--no-block", action="store_true")
    p.add_argument("--status", action="store_true")
    p.add_argument("--fatty", action="store_true", help="Open Fatty CAT Web interface")
    p.add_argument("--terminal", action="store_true", help="Open CAT CLI Web Terminal")
    p.add_argument("--fomoji", action="store_true", help="Open Fomoji Portal")
    p.add_argument("--viewer", action="store_true", help="Open Document & Media Viewer")
    args, unknown = p.parse_known_args()

    if args.status:
        import json
        print(json.dumps(get_host_status(), indent=2))
        return 0

    start_url = args.url or args.url_pos
    if args.terminal:
        start_url = "about:home"
        args.mode = "browser"
    elif args.fomoji:
        start_url = "http://localhost:3000/home.html"
        args.mode = "browser"
    elif args.viewer:
        start_url = "http://localhost:8765/viewer.html"
        args.mode = "browser"
    elif args.fatty:
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
