"""
CCT - native Windows file picker for Browse in Attach to Message.

Reliability order (v0.8.1 root-cause fix for "Browse does nothing"):

  1. tkinter askopenfilenames with root.attributes("-topmost", True).
     The -topmost attribute GUARANTEES the dialog appears above the
     fullscreen terminal even when the terminal owns the foreground
     (Windows Terminal / conhost). This is the primary method because
     the old ctypes-first path could open GetOpenFileNameW BEHIND the
     terminal window (hwndOwner=0 in Windows Terminal returns no usable
     owner), where it silently waited for input the user could not see —
     exactly the reported "button bounces, nothing happens" symptom.

  2. ctypes GetOpenFileNameW (comdlg32) as a fallback when tkinter is
     unavailable. hwndOwner=0 works reliably from worker threads;
     lpstrInitialDir sets the start directory (never lpstrFile, which
     causes CDERR_DIALOGFAILURE).

Both methods: files only (no folder selection), multi-select enabled,
"All Files (*.*)" plus common category filters — deliberately broad.
"""
if __name__ == "__main__":
    print("This is a library file.")
    import sys; sys.exit(1)

import os
import sys

try:
    import ctypes
    from ctypes import wintypes
    _CTYPES_OK = True
except Exception:
    _CTYPES_OK = False

_OFN_FILEMUSTEXIST = 0x00001000
_OFN_PATHMUSTEXIST = 0x00000800
_OFN_HIDEREADONLY = 0x00000004
_OFN_EXPLORER = 0x00080000
_OFN_ALLOWMULTISELECT = 0x00000200
_FLAGS = (_OFN_FILEMUSTEXIST | _OFN_PATHMUSTEXIST
          | _OFN_HIDEREADONLY | _OFN_EXPLORER | _OFN_ALLOWMULTISELECT)
_BUFSIZE = 32768

FILTER = (
    "All Files (*.*)\0*.*\0"
    "Code Files (*.py;*.js;*.ts;*.tsx;*.jsx;*.java;*.c;*.h;*.cpp;*.rs;*.go)\0"
    "*.py;*.js;*.ts;*.tsx;*.jsx;*.java;*.c;*.h;*.cpp;*.rs;*.go\0"
    "Data Files (*.json;*.yaml;*.yml;*.toml;*.xml;*.csv)\0"
    "*.json;*.yaml;*.yml;*.toml;*.xml;*.csv\0"
    "Documents (*.txt;*.md;*.log;*.html;*.css;*.scss;*.pdf;*.doc;*.docx)\0"
    "*.txt;*.md;*.log;*.html;*.css;*.scss;*.pdf;*.doc;*.docx\0"
    "Images (*.png;*.jpg;*.jpeg;*.webp;*.gif;*.svg;*.bmp;*.ico)\0"
    "*.png;*.jpg;*.jpeg;*.webp;*.gif;*.svg;*.bmp;*.ico\0"
    "Archives (*.zip;*.tar;*.gz;*.bz2;*.rar;*.7z)\0"
    "*.zip;*.tar;*.gz;*.bz2;*.rar;*.7z\0"
)

TK_FILETYPES = [
    ("All Files", "*.*"),
    ("Code Files", "*.py *.js *.ts *.tsx *.jsx *.java *.c *.h *.cpp *.rs *.go"),
    ("Data Files", "*.json *.yaml *.yml *.toml *.xml *.csv"),
    ("Documents", "*.txt *.md *.log *.html *.css *.scss *.pdf *.doc *.docx"),
    ("Images", "*.png *.jpg *.jpeg *.webp *.gif *.svg *.bmp *.ico"),
    ("Archives", "*.zip *.tar *.gz *.bz2 *.rar *.7z"),
]


def is_native_supported():
    return sys.platform == "win32"


def parse_multi_buffer(raw):
    if isinstance(raw, bytes):
        raw = raw.decode("utf-16-le", errors="ignore")
    parts = [p for p in raw.split("\x00") if p]
    if not parts:
        return []
    if len(parts) == 1:
        return parts if os.path.isabs(parts[0]) else []
    directory = parts[0]
    out = []
    for name in parts[1:]:
        candidate = os.path.join(directory, name)
        if os.path.isabs(candidate):
            out.append(candidate)
    return out


def _pick_files_tkinter(initial_dir, title):
    """PRIMARY: tkinter dialog forced top-most, so it is always visible.
    Returns list of paths ([] = user cancelled), None = tkinter unusable."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            filepaths = filedialog.askopenfilenames(
                title=title,
                initialdir=initial_dir,
                filetypes=TK_FILETYPES,
            )
            if filepaths:
                return list(filepaths)
            return []  # user cancelled
        finally:
            try:
                root.destroy()
            except Exception:
                pass
    except Exception as e:
        print("[NativePicker] tkinter picker failed: %s" % e, file=sys.stderr)
        return None


class _OPENFILENAMEW(ctypes.Structure):
    _fields_ = [
        ("lStructSize", wintypes.DWORD),
        ("hwndOwner", wintypes.HWND),
        ("hInstance", wintypes.HINSTANCE),
        ("lpstrFilter", wintypes.LPCWSTR),
        ("lpstrCustomFilter", wintypes.LPWSTR),
        ("nMaxCustFilter", wintypes.DWORD),
        ("nFilterIndex", wintypes.DWORD),
        ("lpstrFile", wintypes.LPWSTR),
        ("nMaxFile", wintypes.DWORD),
        ("lpstrFileTitle", wintypes.LPWSTR),
        ("nMaxFileTitle", wintypes.DWORD),
        ("lpstrInitialDir", wintypes.LPCWSTR),
        ("lpstrTitle", wintypes.LPCWSTR),
        ("Flags", wintypes.DWORD),
        ("nFileOffset", wintypes.WORD),
        ("nFileExtension", wintypes.WORD),
        ("lpstrDefExt", wintypes.LPCWSTR),
        ("lCustData", ctypes.c_void_p),
        ("lpfnHook", ctypes.c_void_p),
        ("lpTemplateName", wintypes.LPCWSTR),
    ]
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        _fields_ += [("pvReserved", ctypes.c_void_p),
                     ("dwReserved", wintypes.DWORD)]
    _fields_ += [("FlagsEx", wintypes.DWORD)]


def _pick_files_ctypes(initial_dir, title):
    """FALLBACK: ctypes GetOpenFileNameW. Returns list of paths or None."""
    # CRITICAL: lpstrFile buffer must start EMPTY.
    # Setting buf.value to a directory path causes CDERR_DIALOGFAILURE (12290).
    # Initial directory is set via lpstrInitialDir instead.
    buf = ctypes.create_unicode_buffer(_BUFSIZE)

    filter_str = FILTER + "\x00"
    ofn = _OPENFILENAMEW()
    ofn.lStructSize = ctypes.sizeof(_OPENFILENAMEW)
    # hwndOwner=0: works reliably from worker threads.
    # GetConsoleWindow() returns 0 in Windows Terminal/Textual.
    # GetForegroundWindow() causes error 12290 (CDERR_DIALOGFAILURE).
    ofn.hwndOwner = 0
    ofn.lpstrFilter = filter_str
    ofn.nFilterIndex = 1
    ofn.lpstrFile = ctypes.cast(buf, wintypes.LPWSTR)
    ofn.nMaxFile = _BUFSIZE
    ofn.lpstrTitle = title
    ofn.Flags = _FLAGS

    # Set initial directory via lpstrInitialDir, NOT via buf.value
    if initial_dir:
        if not os.path.isdir(initial_dir):
            initial_dir = os.path.dirname(initial_dir) or None
        if initial_dir:
            ofn.lpstrInitialDir = initial_dir

    comdlg32 = ctypes.windll.comdlg32
    fn = comdlg32.GetOpenFileNameW
    fn.argtypes = [ctypes.POINTER(_OPENFILENAMEW)]
    fn.restype = wintypes.BOOL

    result = fn(ctypes.byref(ofn))
    if result:
        return parse_multi_buffer(buf.raw)
    err = comdlg32.CommDlgExtendedError()
    if err:
        print("[NativePicker] CommDlgExtendedError=%d" % err, file=sys.stderr)
    return None


def pick_files(initial_dir=None, title="Select file(s) to attach"):
    """Show a file picker. Tries the always-visible tkinter dialog first,
    falls back to ctypes GetOpenFileNameW.
    Returns list of paths (empty = cancelled), None = all methods failed."""
    if not is_native_supported():
        return None

    # Method 1: tkinter (topmost — cannot open behind the terminal)
    result = _pick_files_tkinter(initial_dir, title)
    if result is not None:
        return result

    # Method 2: ctypes GetOpenFileNameW
    if not _CTYPES_OK:
        return None
    print("[NativePicker] Trying ctypes fallback...", file=sys.stderr)
    try:
        result = _pick_files_ctypes(initial_dir, title)
        if result is not None:
            return result
    except Exception as e:
        print("[NativePicker] ctypes exception: %s" % e, file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)

    return None
