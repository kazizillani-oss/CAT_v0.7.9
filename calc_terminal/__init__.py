import os
import sys
import tempfile

def _ensure_writable_runtime_env() -> bool:
    """Ensure HOME and CAT data/storage directories point to writable paths.
    On Vercel Serverless / AWS Lambda / read-only containers, /var/task and
    $HOME (/home/sbx_user1051) are read-only while /tmp is writable.
    """
    is_serverless = bool(
        os.environ.get("VERCEL")
        or os.environ.get("VERCEL_ENV")
        or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
        or os.environ.get("NOW_REGION")
        or os.environ.get("CAT_SERVERLESS")
    )
    home = os.path.expanduser("~")
    home_writable = False
    if not is_serverless and home and os.path.isdir(home) and os.access(home, os.W_OK):
        try:
            test_dir = os.path.join(home, ".cat")
            os.makedirs(test_dir, exist_ok=True)
            home_writable = os.access(test_dir, os.W_OK)
        except OSError:
            home_writable = False

    if is_serverless or not home_writable:
        tmp_base = os.path.join(tempfile.gettempdir(), "cat_home")
        try:
            os.makedirs(tmp_base, exist_ok=True)
            os.makedirs(os.path.join(tmp_base, ".config", "cct"), exist_ok=True)
            os.makedirs(os.path.join(tmp_base, ".cat"), exist_ok=True)
            os.makedirs(os.path.join(tmp_base, ".cct", "cache", "providers"), exist_ok=True)
            os.makedirs(os.path.join(tmp_base, ".cct", "cache", "models"), exist_ok=True)
        except OSError:
            pass
        os.environ["HOME"] = tmp_base
        os.environ["USERPROFILE"] = tmp_base
        os.environ.setdefault("XDG_CONFIG_HOME", os.path.join(tmp_base, ".config"))
        os.environ.setdefault("XDG_DATA_HOME", os.path.join(tmp_base, ".local", "share"))
        if not os.environ.get("CCT_DATA_DIR"):
            os.environ["CCT_DATA_DIR"] = os.path.join(tmp_base, ".config", "cct")
        if not os.environ.get("CAT_STORAGE_DIR"):
            os.environ["CAT_STORAGE_DIR"] = os.path.join(tmp_base, ".cat")
        return True
    return False

IS_SERVERLESS_ENV = _ensure_writable_runtime_env()

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

# Only install terminal ANSI escape guard on interactive TTY sessions
if not IS_SERVERLESS_ENV and not os.environ.get("CAT_WEB_SERVER"):
    try:
        if hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
            from .terminal_host import install_terminal_guard
            install_terminal_guard()
    except Exception:
        pass

__version__ = "0.8.0b1"


def _sync_version():
    """Keep __version__ in sync with calc_terminal.app.VERSION so package
    metadata and application version information never drift apart."""
    try:
        from .app import VERSION
        return VERSION
    except Exception:
        return __version__


__version__ = _sync_version()
