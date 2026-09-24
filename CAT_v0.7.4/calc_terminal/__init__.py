import sys
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stdin, "reconfigure"):
            sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

__version__ = "0.8.b"


def _sync_version():
    """Keep __version__ in sync with calc_terminal.app.VERSION so package
    metadata and application version information never drift apart."""
    try:
        from .app import VERSION
        return VERSION
    except Exception:
        return __version__


__version__ = _sync_version()