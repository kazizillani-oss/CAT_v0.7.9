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
