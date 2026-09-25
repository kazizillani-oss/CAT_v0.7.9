"""
CCT — terminal host detection + native clipboard read.

CCT is a Textual chat IDE: it does not spawn or drive a shell/PTY, so a
"paste" is delivered by the terminal the user launched CCT in. This
module answers two questions the large-paste fix (v0.7.8.45) needs:

  * Which shell is hosting CCT right now?       (detect_host)
  * What does the clipboard actually hold on Windows?  (read_clipboard_text)

The PowerShell case: on Windows console hosts (conhost / Windows
Terminal, regardless of whether PowerShell or cmd is the shell), a very
large bracketed-paste payload can be truncated or dropped while being
written into the console input buffer — before Textual ever sees it.
The paste handler recovers by comparing the delivered event text against
the OS clipboard: when the clipboard is a strict prefix-superset of the
delivered text, the clipboard is the authoritative payload.

Everything here is best-effort; every function returns a safe default on
failure so the app never depends on this module succeeding.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import os
import sys
import time

_CF_UNICODETEXT = 13
_cached_host = None
_cached_emulator = None


def detect_host():
    """Lowercase name of the SHELL CCT is running inside:

        'powershell' | 'cmd' | 'bash' | 'zsh' | 'other'

    Detection is env-var based (no subprocesses, no psutil) and cached —
    the environment cannot change at runtime. `CCT_FORCE_HOST` overrides
    it for tests and exotic setups.
    """
    global _cached_host
    forced = os.environ.get("CCT_FORCE_HOST", "").strip().lower()
    if forced:
        _cached_host = forced
        return _cached_host
    if _cached_host:
        return _cached_host
    host = "other"
    try:
        shell = os.environ.get("SHELL", "")
        if shell:
            base = os.path.basename(shell).lower()
            if "zsh" in base:
                host = "zsh"
            elif "bash" in base or base in ("sh", "dash"):
                host = "bash"
        if host == "other" and os.environ.get("PSModulePath"):
            # Set by Windows PowerShell and pwsh (and only by them), so
            # it is the reliable PowerShell fingerprint on Windows.
            host = "powershell"
        if host == "other":
            comspec = os.environ.get("COMSPEC", "").lower()
            if "powershell" in comspec:
                host = "powershell"
            elif "cmd" in comspec:
                host = "cmd"
        if host == "other" and sys.platform == "win32":
            host = "cmd"
    except Exception:
        host = "other"
    _cached_host = host
    return host


def detect_emulator():
    """Terminal-emulator name for diagnostics ('Windows Terminal',
    'ConEmu', 'vscode', 'Apple Terminal', 'xterm', ...) or 'other'.
    Never raises, cached."""
    global _cached_emulator
    if _cached_emulator:
        return _cached_emulator
    emu = "other"
    try:
        if os.environ.get("WT_SESSION"):
            emu = "Windows Terminal"
        elif os.environ.get("ConEmuPID"):
            emu = "ConEmu"
        elif os.environ.get("TERM_PROGRAM"):
            tp = os.environ["TERM_PROGRAM"].lower()
            emu = "vscode" if "vscode" in tp else os.environ["TERM_PROGRAM"]
        elif os.environ.get("__CF_USER_TEXT_ENCODING"):
            emu = "Apple Terminal"
        elif os.environ.get("TERM"):
            emu = os.environ["TERM"]
    except Exception:
        emu = "other"
    _cached_emulator = emu
    return emu


def is_windows():
    """True when CCT is running on a Windows console host (the only
    place the clipboard-prefix paste recovery is needed)."""
    return sys.platform == "win32"


def read_clipboard_text():
    """Best-effort native clipboard read on Windows (user32
    GetClipboardData, CF_UNICODETEXT via ctypes — no third-party
    dependency, no subprocess). Returns the clipboard text as str, or
    None when there is no text / the clipboard is busy / an error
    occurs / the platform is not Windows."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        # Restype/argtype declarations are mandatory: the default int
        # restype truncates 64-bit HGLOBAL pointers returned by
        # GetClipboardData/GlobalLock/GlobalSize.
        user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
        user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
        user32.GetClipboardData.argtypes = [wintypes.UINT]
        user32.GetClipboardData.restype = ctypes.c_void_p
        kernel32.GlobalSize.argtypes = [ctypes.c_void_p]
        kernel32.GlobalSize.restype = ctypes.c_size_t
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalUnlock.restype = wintypes.BOOL
        text = None
        for _ in range(3):  # brief retries; the clipboard is often held
            if user32.OpenClipboard(None):
                break
            time.sleep(0.015)
        else:
            return None
        try:
            if not user32.IsClipboardFormatAvailable(_CF_UNICODETEXT):
                return None
            handle = user32.GetClipboardData(_CF_UNICODETEXT)
            if not handle:
                return None
            ptr = kernel32.GlobalLock(handle)
            if not ptr:
                return None
            try:
                size = kernel32.GlobalSize(handle)
                if size <= 2:
                    return None
                nchars = size // 2
                arr = (ctypes.c_wchar * (nchars + 1)).from_address(ptr)
                text = "".join(arr[:nchars]).rstrip("\x00")
            finally:
                kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()
        return text
    except Exception:
        return None


def clipboard_payload_override(delivered):
    """Windows paste-recovery decision (v0.7.8.45, PowerShell case).

    Returns (payload, source) for the paste handler:

      (delivered, 'terminal')                  — keep what the terminal
                                                 delivered (everything
                                                 else)
      (clipboard, 'clipboard')                 — the Windows console
                                                 host truncated the
                                                 bracketed-paste payload
                                                 (clipboard is a strict
                                                 prefix-superset of the
                                                 delivered text), so the
                                                 clipboard is the
                                                 authoritative copy

    `source` is the human-readable name used in debug logs.
    """
    if not is_windows():
        return delivered, "terminal"
    if not delivered:
        # Host dropped the whole payload; the clipboard is the only
        # copy left.
        clip = read_clipboard_text()
        if clip:
            return clip, "clipboard (terminal dropped the payload)"
        return delivered, "terminal"
    clip = read_clipboard_text()
    if clip and len(clip) > len(delivered) and clip.startswith(delivered):
        return clip, "clipboard (terminal payload truncated)"
    return delivered, "terminal"


# -----------------------------------------------------------------------------
# Terminal Sanitation & Mouse/Focus Tracking Teardown
# -----------------------------------------------------------------------------

TERMINAL_RESET_SEQUENCES = (
    "\x1b[?1000l"  # Disable VT200 mouse reporting
    "\x1b[?1002l"  # Disable button-event mouse tracking
    "\x1b[?1003l"  # Disable any-event / all-event mouse tracking
    "\x1b[?1004l"  # Disable FocusIn / FocusOut reporting ([I / [O)
    "\x1b[?1006l"  # Disable SGR extended mouse mode (<...M / <...m)
    "\x1b[?1015l"  # Disable urxvt extended mouse mode
    "\x1b[?2004l"  # Disable bracketed paste mode
    "\x1b[<u"      # Disable Kitty keyboard protocol
    "\x1b[?1049l"  # Switch from alternate screen back to normal buffer
    "\x1b[?25h"    # Ensure cursor is visible
    "\x1b[0m"      # Reset all text attributes and colors
)

_terminal_guard_installed = False


def sanitize_terminal() -> None:
    """Immediately and unconditionally reset the terminal to a clean state:
    - Turns off all mouse tracking modes (1000, 1002, 1003, 1006, 1015)
    - Turns off focus reporting (1004, which causes [I and [O to leak into shell)
    - Turns off bracketed paste mode (2004)
    - Turns off Kitty keyboard protocol
    - Restores normal screen buffer from alternate screen (1049)
    - Ensures cursor is visible (25h)
    - Resets text styling and colors (0m)
    - On Windows: disables ENABLE_VIRTUAL_TERMINAL_INPUT and flushes the console input buffer
      so lingering mouse packets don't bleed into PowerShell / cmd prompts.
    """
    # 1. Output via standard Python streams
    for stream in (getattr(sys, "__stdout__", None), getattr(sys, "stdout", None),
                   getattr(sys, "__stderr__", None), getattr(sys, "stderr", None)):
        if stream is not None:
            try:
                stream.write(TERMINAL_RESET_SEQUENCES)
                stream.flush()
            except Exception:
                pass

    # 2. On Windows: Direct Win32 CONOUT$ and CONIN$ manipulation
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32

            # Direct CONOUT$ write with VT processing enabled
            conout = "CONOUT" + chr(36)
            h_out = kernel32.CreateFileW(
                conout, 0x40000000 | 0x80000000, 0x00000001 | 0x00000002, None, 3, 0, None
            )
            if h_out != -1 and h_out != 0:
                try:
                    mode = ctypes.c_ulong()
                    if kernel32.GetConsoleMode(h_out, ctypes.byref(mode)):
                        kernel32.SetConsoleMode(h_out, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
                    written = ctypes.c_ulong()
                    raw_bytes = TERMINAL_RESET_SEQUENCES.encode("utf-8")
                    kernel32.WriteFile(h_out, raw_bytes, len(raw_bytes), ctypes.byref(written), None)
                finally:
                    kernel32.CloseHandle(h_out)

            # CONIN$ mode restoration and input buffer flush
            conin = "CONIN" + chr(36)
            h_in = kernel32.CreateFileW(
                conin, 0x40000000 | 0x80000000, 0x00000001 | 0x00000002, None, 3, 0, None
            )
            if h_in != -1 and h_in != 0:
                try:
                    in_mode = ctypes.c_ulong()
                    if kernel32.GetConsoleMode(h_in, ctypes.byref(in_mode)):
                        # Clear ENABLE_VIRTUAL_TERMINAL_INPUT (0x0200) and ENABLE_MOUSE_INPUT (0x0010)
                        # Set standard line/echo/processed flags: 0x0001 | 0x0002 | 0x0004 | 0x0080
                        clean_mode = (in_mode.value & ~0x0210) | 0x0087
                        kernel32.SetConsoleMode(h_in, clean_mode)
                    # Discard any mouse or focus sequences already sitting in the input queue
                    kernel32.FlushConsoleInputBuffer(h_in)
                finally:
                    kernel32.CloseHandle(h_in)

            # Also attempt on standard input handle
            std_in = kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE
            if std_in != -1 and std_in != 0:
                try:
                    in_mode = ctypes.c_ulong()
                    if kernel32.GetConsoleMode(std_in, ctypes.byref(in_mode)):
                        clean_mode = (in_mode.value & ~0x0210) | 0x0087
                        kernel32.SetConsoleMode(std_in, clean_mode)
                    kernel32.FlushConsoleInputBuffer(std_in)
                except Exception:
                    pass
        except Exception:
            pass


def install_terminal_guard() -> None:
    """Install global exit and signal guards ensuring the terminal is always sanitized
    even on unexpected exit, crash, Ctrl+C, or kill signal."""
    global _terminal_guard_installed
    if _terminal_guard_installed:
        return
    _terminal_guard_installed = True

    import atexit
    import signal

    atexit.register(sanitize_terminal)

    def _sig_handler(signum, frame):
        sanitize_terminal()
        if signum == getattr(signal, "SIGINT", None):
            raise KeyboardInterrupt()
        sys.exit(128 + signum)

    try:
        if hasattr(signal, "SIGINT"):
            signal.signal(signal.SIGINT, _sig_handler)
    except (ValueError, OSError):
        pass

    try:
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _sig_handler)
    except (ValueError, OSError):
        pass

    try:
        if hasattr(signal, "SIGBREAK"):
            signal.signal(signal.SIGBREAK, _sig_handler)
    except (ValueError, OSError, AttributeError):
        pass

    # Exception hook to sanitize terminal before unhandled exception traceback is written
    orig_excepthook = getattr(sys, "excepthook", None)

    def _sanitizing_excepthook(exc_type, exc_value, exc_tb):
        try:
            sanitize_terminal()
        except Exception:
            pass
        if orig_excepthook and orig_excepthook is not _sanitizing_excepthook:
            orig_excepthook(exc_type, exc_value, exc_tb)

    sys.excepthook = _sanitizing_excepthook

