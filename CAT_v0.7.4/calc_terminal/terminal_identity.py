"""
calc_terminal/terminal_identity.py
==================================
Centralized Terminal & Tab Identity management for CAT CLI.

Guarantees that the active terminal tab and window title display:
    🐱 CAT CLI  (or CAT CLI)
across Windows Terminal, Command Prompt (cmd.exe), PowerShell, and POSIX
terminals, preventing generic host shell names ('Command Prompt',
'PowerShell', 'cmd.exe', 'pwsh') from leaking or polluting the tab/window.

Features:
  - Emits UTF-8 OSC 0 and OSC 2 escape sequences safely without Windows cp1252 crashes.
  - Calls Win32 kernel32.SetConsoleTitleW for conhost / ConPTY consistency.
  - Loads and sets the official CAT logo (.ico) via WM_SETICON on the console HWND.
  - Detects and registers the CAT CLI profile in Windows Terminal settings.json.
  - Runs a lightweight TitleGuard daemon thread to recover if external processes
    (e.g. child cmd.exe / npm / git) overwrite the console title.
"""

import atexit
import os
import sys
import threading
import time
from typing import Optional, Tuple

BRAND_NAME = "CAT CLI"
BRAND_EMOJI = "🐱"
DEFAULT_TITLE = f"{BRAND_EMOJI} {BRAND_NAME}"
PLAIN_TITLE = BRAND_NAME
WT_CAT_GUID = "{a3f2b4c1-d8e7-4f9a-8b1c-3d5e7f9a2b4c}"

_current_active_title: str = DEFAULT_TITLE
_title_guard_thread: Optional[threading.Thread] = None
_title_guard_stop_event = threading.Event()
_title_guard_lock = threading.Lock()
_title_saved: bool = False


def _get_local_appdata_dir() -> str:
    local_app = os.environ.get("LOCALAPPDATA")
    if local_app:
        base = os.path.join(local_app, "CCT")
    else:
        base = os.path.expanduser("~/.cct")
    try:
        os.makedirs(base, exist_ok=True)
    except Exception:
        pass
    return base


def get_icon_path() -> Optional[str]:
    """Return the absolute path to the multi-resolution CAT .ico file,
    refreshing the stable Windows Terminal copy from the installed package."""
    local_dir = _get_local_appdata_dir()
    local_ico = os.path.join(local_dir, "cat.ico")
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(pkg_dir, "cat.ico"),
        os.path.join(pkg_dir, "web", "static", "icons", "cat.ico"),
    ]
    for c in candidates:
        if os.path.isfile(c) and os.path.getsize(c) > 0:
            # Keep Windows Terminal's stable profile path synchronized after upgrades.
            try:
                import shutil
                shutil.copy2(c, local_ico)
                return os.path.abspath(local_ico)
            except Exception:
                return os.path.abspath(c)

    # A previously copied icon remains usable if this is a partial install.
    if os.path.isfile(local_ico) and os.path.getsize(local_ico) > 0:
        return os.path.abspath(local_ico)

    # Last-resort generation for partial installs that only contain the PNG.
    png_source = os.path.join(pkg_dir, "cat.png")
    if not os.path.isfile(png_source):
        png_source = os.path.join(pkg_dir, "web", "static", "icons", "icon-512.png")
    if os.path.isfile(png_source):
        try:
            from PIL import Image
            img = Image.open(png_source)
            sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
            img.save(local_ico, sizes=sizes)
            return os.path.abspath(local_ico)
        except Exception:
            pass

    return None


def set_process_app_user_model_id(app_id: str = "kazizillani.cat.cli.v08") -> bool:
    """Explicitly set Windows AppUserModelID so the Windows taskbar displays our custom icon
    rather than Python's default interpreter icon."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(str(app_id))
        return True
    except Exception:
        return False


def get_browser_icon_path() -> Optional[str]:
    """Return the absolute path to the current multi-resolution CAT Browser icon."""
    local_dir = _get_local_appdata_dir()
    local_ico = os.path.join(local_dir, "cat_browser.ico")
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(pkg_dir, "cat_browser.ico"),
        os.path.join(pkg_dir, "web", "static", "icons", "cat_browser.ico"),
    ]
    for c in candidates:
        if os.path.isfile(c) and os.path.getsize(c) > 0:
            try:
                import shutil
                shutil.copy2(c, local_ico)
                return os.path.abspath(local_ico)
            except Exception:
                return os.path.abspath(c)
    if os.path.isfile(local_ico) and os.path.getsize(local_ico) > 0:
        return os.path.abspath(local_ico)
    return None


def apply_console_icon(ico_path: Optional[str] = None) -> bool:
    """Set the Windows console window and taskbar icon via Win32 WM_SETICON and AppUserModelID."""
    if sys.platform != "win32":
        return False
    set_process_app_user_model_id("kazizillani.cat.cli.v08")
    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        user32 = ctypes.WinDLL("user32", use_last_error=True)

        kernel32.GetConsoleWindow.restype = wintypes.HWND
        user32.LoadImageW.argtypes = (
            wintypes.HANDLE, wintypes.LPCWSTR, wintypes.UINT,
            ctypes.c_int, ctypes.c_int, wintypes.UINT,
        )
        user32.LoadImageW.restype = wintypes.HANDLE
        user32.SendMessageW.argtypes = (
            wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t,
        )
        user32.SendMessageW.restype = ctypes.c_ssize_t

        hwnd = kernel32.GetConsoleWindow()
        if not hwnd:
            return False

        if not ico_path:
            ico_path = get_icon_path()
        if not ico_path or not os.path.isfile(ico_path):
            return False

        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1

        # The multi-size ICO supplies crisp 16px and 32px console/window icons;
        # Shell and Windows Terminal can select larger embedded sizes as needed.
        hicon_small = user32.LoadImageW(None, ico_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
        hicon_big = user32.LoadImageW(None, ico_path, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)

        success = False
        if hicon_small:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
            success = True
        if hicon_big:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)
            success = True
        return success
    except Exception:
        return False


def apply_browser_taskbar_icon(hwnd: int, ico_path: Optional[str] = None) -> bool:
    """Set the Windows taskbar and window icon for CAT Browser via Win32 WM_SETICON,
    class icons, and SetCurrentProcessExplicitAppUserModelID."""
    if sys.platform != "win32" or hwnd <= 0:
        return False
    set_process_app_user_model_id("kazizillani.cat.browser.v08")
    if not ico_path:
        ico_path = get_browser_icon_path()
    if not ico_path or not os.path.isfile(ico_path):
        return False
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.LoadImageW.argtypes = (
            wintypes.HANDLE, wintypes.LPCWSTR, wintypes.UINT,
            ctypes.c_int, ctypes.c_int, wintypes.UINT,
        )
        user32.LoadImageW.restype = wintypes.HANDLE
        user32.SendMessageW.argtypes = (
            wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t,
        )
        user32.SendMessageW.restype = ctypes.c_ssize_t

        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1

        sm_cx_sm = user32.GetSystemMetrics(49) or 16
        sm_cy_sm = user32.GetSystemMetrics(50) or 16
        sm_cx_lg = user32.GetSystemMetrics(11) or 32
        sm_cy_lg = user32.GetSystemMetrics(12) or 32

        hicon_small = user32.LoadImageW(None, str(ico_path), IMAGE_ICON, sm_cx_sm, sm_cy_sm, LR_LOADFROMFILE)
        hicon_big = user32.LoadImageW(None, str(ico_path), IMAGE_ICON, sm_cx_lg, sm_cy_lg, LR_LOADFROMFILE)
        hicon_256 = user32.LoadImageW(None, str(ico_path), IMAGE_ICON, 256, 256, LR_LOADFROMFILE)

        success = False
        if hicon_small:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
            success = True
        target_big = hicon_big or hicon_256
        if target_big:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, target_big)
            success = True

        GCLP_HICON = -14
        GCLP_HICONSM = -34
        set_class = getattr(user32, "SetClassLongPtrW", getattr(user32, "SetClassLongW", None))
        if set_class:
            set_class.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t)
            set_class.restype = ctypes.c_ssize_t
            if target_big:
                try:
                    set_class(hwnd, GCLP_HICON, target_big)
                except Exception:
                    pass
            if hicon_small:
                try:
                    set_class(hwnd, GCLP_HICONSM, hicon_small)
                except Exception:
                    pass
        return success
    except Exception:
        return False


def _safe_write_osc(text: str) -> bool:
    """Write OSC title escape sequences using raw UTF-8 bytes to prevent
    Windows default cp1252 UnicodeEncodeError crashes."""
    try:
        if os.environ.get("TERM", "") == "dumb":
            return False

        is_tty = False
        try:
            is_tty = bool(getattr(sys.stdout, "isatty", lambda: False)())
        except Exception:
            is_tty = False

        if not is_tty:
            return False

        # Clean control characters
        clean = "".join(ch for ch in str(text) if ch.isprintable() and ch not in "\x07\x1b")[:100]

        # Push title once on xterm if supported
        global _title_saved
        push_seq = b"\x1b[22t" if not _title_saved else b""
        if not _title_saved:
            _title_saved = True

        # OSC 0 (window & icon) and OSC 2 (window title)
        osc_seq = f"\x1b]0;{clean}\x07\x1b]2;{clean}\x07".encode("utf-8")

        payload = push_seq + osc_seq
        # Prefer writing directly to buffer for UTF-8 reliability
        buf = getattr(sys.stdout, "buffer", None)
        if buf is not None:
            buf.write(payload)
            buf.flush()
        else:
            try:
                sys.stdout.write(f"\x1b]0;{clean}\x07")
                sys.stdout.flush()
            except UnicodeEncodeError:
                fallback = clean.encode("ascii", errors="ignore").decode("ascii").strip()
                sys.stdout.write(f"\x1b]0;{fallback}\x07")
                sys.stdout.flush()
        return True
    except Exception:
        return False


def set_terminal_title(title: Optional[str] = None, with_icon: bool = True) -> bool:
    """Set the terminal tab and window title to '🐱 CAT CLI' (or custom title).
    Centralized function that handles:
      1. OSC 0 and OSC 2 terminal sequences (UTF-8 safe)
      2. Win32 SetConsoleTitleW
      3. Win32 console WM_SETICON (on Windows)
    """
    global _current_active_title

    if title is None or not str(title).strip():
        chosen = DEFAULT_TITLE if with_icon else PLAIN_TITLE
    else:
        t = str(title).strip()
        # If the user passed a sub-title like 'Starting' or 'Ready', brand it nicely
        if t.lower() in ("starting", "ready", "running", "exiting"):
            chosen = f"{DEFAULT_TITLE} — {t.capitalize()}"
        elif not (t.startswith(BRAND_EMOJI) or BRAND_NAME in t):
            chosen = f"{DEFAULT_TITLE} — {t}"
        else:
            chosen = t

    _current_active_title = chosen

    # 1. OSC sequences (for Windows Terminal, modern conhost, Mintty, VS Code, iTerm, etc.)
    osc_ok = _safe_write_osc(chosen)

    # 2. Win32 SetConsoleTitleW (for classic conhost, cmd.exe, PowerShell, and ConPTY)
    win32_ok = False
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleTitleW(chosen)
            win32_ok = True
            apply_console_icon()
        except Exception:
            pass

    return osc_ok or win32_ok


def restore_terminal_title() -> bool:
    """Restore previous terminal title on exit (xterm title stack pop)."""
    global _title_saved
    if not _title_saved:
        return False
    try:
        buf = getattr(sys.stdout, "buffer", None)
        if buf is not None:
            buf.write(b"\x1b[23t")
            buf.flush()
        else:
            sys.stdout.write("\x1b[23t")
            sys.stdout.flush()
        _title_saved = False
        return True
    except Exception:
        _title_saved = False
        return False


def get_current_console_title() -> Optional[str]:
    """Retrieve the current console title via Win32 GetConsoleTitleW."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(1024)
        length = ctypes.windll.kernel32.GetConsoleTitleW(buf, 1024)
        if length > 0:
            return buf.value
    except Exception:
        pass
    return None


def _is_polluted_title(current: Optional[str]) -> bool:
    """Check if the title currently contains a generic shell or subprocess name."""
    if not current:
        return True
    s = current.strip().lower()
    # If it contains CAT CLI, it's good
    if "cat cli" in s or "coding agent terminal" in s:
        return False
    # Polluted shell names
    polluters = [
        "command prompt",
        "powershell",
        "cmd.exe",
        "pwsh",
        "windows powershell",
        "npm",
        "node",
        "git",
        "python",
    ]
    return any(p in s for p in polluters)


def _title_guard_worker(interval: float = 1.0):
    """Background worker that continuously asserts the CAT CLI title
    if an external subprocess or shell clobbers it."""
    while not _title_guard_stop_event.is_set():
        try:
            if sys.platform == "win32":
                curr = get_current_console_title()
                if _is_polluted_title(curr):
                    set_terminal_title(_current_active_title)
        except Exception:
            pass
        _title_guard_stop_event.wait(interval)


def start_title_guard(interval: float = 1.0):
    """Start the background thread that guards against title pollution."""
    global _title_guard_thread
    with _title_guard_lock:
        if _title_guard_thread is not None and _title_guard_thread.is_alive():
            return
        _title_guard_stop_event.clear()
        _title_guard_thread = threading.Thread(
            target=_title_guard_worker,
            args=(interval,),
            name="CAT-TitleGuard",
            daemon=True,
        )
        _title_guard_thread.start()


def stop_title_guard():
    """Stop the title guard thread."""
    with _title_guard_lock:
        _title_guard_stop_event.set()


# Ensure title guard stops cleanly on exit
atexit.register(stop_title_guard)


def find_windows_terminal_settings() -> Optional[str]:
    """Locate the active Windows Terminal settings.json file."""
    if sys.platform != "win32":
        return None

    local_app = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        # Windows Terminal (Stable)
        os.path.join(local_app, "Packages", "Microsoft.WindowsTerminal_8wekyb3d8bbwe", "LocalState", "settings.json"),
        # Windows Terminal (Preview)
        os.path.join(local_app, "Packages", "Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe", "LocalState", "settings.json"),
        # Unpackaged / Scoop / Winget portable
        os.path.join(local_app, "Microsoft", "Windows Terminal", "settings.json"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def configure_windows_terminal_profile() -> Tuple[bool, str]:
    """Register or update the dedicated 'CAT CLI' profile in Windows Terminal settings.json.
    Sets:
      - name: "CAT CLI"
      - commandline: "cat"
      - icon: path to cat.ico
      - tabTitle: "CAT CLI"
      - suppressApplicationTitle: false
      - largePasteWarning: false
      - multiLinePasteWarning: false
    """
    settings_file = find_windows_terminal_settings()
    if not settings_file:
        return False, "Windows Terminal settings.json not found."

    ico_path = get_icon_path()
    if not ico_path:
        return False, "CAT icon (.ico) not available."

    try:
        import json
        with open(settings_file, "r", encoding="utf-8-sig") as f:
            data = json.load(f)

        # Globally disable large paste (>5 KiB) warning and multiline paste warning
        # so large sentences, long texts, and code snippets paste immediately without interruption.
        data["largePasteWarning"] = False
        data["multiLinePasteWarning"] = False

        profiles = data.setdefault("profiles", {})
        defaults = profiles.setdefault("defaults", {})
        defaults["largePasteWarning"] = False
        defaults["multiLinePasteWarning"] = False

        plist = profiles.setdefault("list", [])

        # Find existing profile
        target_profile = None
        for p in plist:
            if p.get("guid") == WT_CAT_GUID or p.get("name") == BRAND_NAME:
                target_profile = p
                break

        if target_profile is None:
            target_profile = {
                "guid": WT_CAT_GUID,
                "name": BRAND_NAME,
                "commandline": "cat",
                "icon": ico_path,
                "tabTitle": BRAND_NAME,
                "suppressApplicationTitle": False,
                "largePasteWarning": False,
                "multiLinePasteWarning": False,
            }
            plist.append(target_profile)
            action_desc = "Created new 'CAT CLI' profile"
        else:
            target_profile["name"] = BRAND_NAME
            target_profile["icon"] = ico_path
            target_profile["tabTitle"] = BRAND_NAME
            target_profile["largePasteWarning"] = False
            target_profile["multiLinePasteWarning"] = False
            action_desc = "Updated existing 'CAT CLI' profile"

        # Atomic write back
        tmp_file = settings_file + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        os.replace(tmp_file, settings_file)
        return True, f"{action_desc} in Windows Terminal ({settings_file})."
    except Exception as e:
        return False, f"Failed to configure Windows Terminal profile: {e}"


def init_terminal_identity():
    """High-level initialization called on CAT CLI startup."""
    # 1. Set the initial title immediately
    set_terminal_title()

    # 2. Configure Windows Terminal profile if running on Windows
    if sys.platform == "win32":
        try:
            configure_windows_terminal_profile()
        except Exception:
            pass

    # 3. Start title guard to protect against subprocess/shell pollution
    start_title_guard()
