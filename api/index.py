"""
Vercel Serverless Function entry point for FATTY CAT Web Server & Cloud IDE.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# 1. Patch asyncio primitives for Python 3.10+ / 3.12 compatibility with Vercel's ASGI wrapper
try:
    import asyncio
    for _cls_name in ("Queue", "LifoQueue", "PriorityQueue", "Lock", "Event", "Semaphore", "BoundedSemaphore", "Condition"):
        _cls = getattr(asyncio, _cls_name, None)
        if _cls is not None:
            _orig_init = _cls.__init__
            def _make_patched(_orig):
                def _patched(self, *args, **kwargs):
                    kwargs.pop("loop", None)
                    return _orig(self, *args, **kwargs)
                return _patched
            _cls.__init__ = _make_patched(_orig_init)
except Exception:
    pass

# 2. Serverless environment configuration
_tmp = tempfile.gettempdir()
_cat_home = os.path.join(_tmp, "cat_home")
_cat_ws = os.path.join(_tmp, "cat_workspace")
for _p in (_cat_home, _cat_ws, os.path.join(_cat_home, ".config", "cct")):
    try:
        os.makedirs(_p, exist_ok=True)
    except Exception:
        pass

os.environ.setdefault("VERCEL", "1")
os.environ.setdefault("CAT_ENV", "production")
os.environ.setdefault("PYTHONUNBUFFERED", "1")
os.environ.setdefault("CCT_DATA_DIR", os.path.join(_cat_home, ".config", "cct"))
os.environ.setdefault("XDG_CONFIG_HOME", os.path.join(_cat_home, ".config"))

# 3. Resolve repository paths so calc_terminal is importable as a top-level package
_current_dir = Path(__file__).resolve().parent
_repo_root = _current_dir.parent
_cat_dir = _repo_root / "CAT_v0.7.4"

for p in (str(_repo_root), str(_cat_dir)):
    if p not in sys.path:
        sys.path.insert(0, p)

# 4. Import the FastAPI application
try:
    from calc_terminal.web.server import app

    # Add optional serverless diagnostic endpoint
    @app.get("/api/diag")
    async def serverless_diagnostics():
        import platform
        return {
            "status": "healthy",
            "service": "FATTY CAT Cloud IDE",
            "version": "0.7.9.0",
            "python": sys.version,
            "platform": platform.platform(),
            "serverless": True,
            "cwd": os.getcwd(),
            "sys_path": sys.path[:5],
            "writable_workspace": _cat_ws,
        }

except Exception as exc:
    import traceback
    tb = traceback.format_exc()
    print("FATAL ERROR: Failed to import calc_terminal.web.server:", file=sys.stderr)
    print(tb, file=sys.stderr)

    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse

    app = FastAPI(title="FATTY CAT (Diagnostics Mode)", lifespan=None)

    @app.get("/")
    @app.get("/health")
    @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"])
    async def diagnostics_fallback(full_path: str = ""):
        return HTMLResponse(
            f"<!DOCTYPE html><html><head><title>🐾 Fatty CAT Cold-Start Diagnostic</title></head>"
            f"<body style='background:#0d1117;color:#f85149;font-family:monospace;padding:28px;line-height:1.6;'>"
            f"<h2>🐾 Fatty CAT Vercel Cold-Start Diagnostic</h2>"
            f"<p style='color:#e6edf3;'>An error occurred while importing <code>calc_terminal.web.server</code>:</p>"
            f"<pre style='background:#161b22;padding:16px;border-radius:8px;color:#c9d1d9;overflow:auto;border:1px solid #30363d;'>"
            f"{exc}\n\n{tb}"
            f"</pre>"
            f"<p style='color:#8b949e;'>sys.path: {sys.path}</p>"
            f"</body></html>",
            status_code=200
        )
