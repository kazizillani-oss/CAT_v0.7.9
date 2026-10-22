"""
Vercel Serverless Function entry point for FATTY CAT Web Server & Cloud IDE.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Resolve repository paths so calc_terminal is importable
_current_dir = Path(__file__).resolve().parent
_repo_root = _current_dir.parent
_cat_dir = _repo_root / "CAT_v0.7.4"

# Ensure CAT package directory and repo root are in sys.path
for p in (str(_cat_dir), str(_repo_root)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Serverless environment flags
os.environ.setdefault("VERCEL", "1")
os.environ.setdefault("CAT_ENV", "production")
os.environ.setdefault("PYTHONUNBUFFERED", "1")

# Import the FastAPI application from calc_terminal.web.server
try:
    from calc_terminal.web.server import app
except Exception as exc:
    import traceback
    tb = traceback.format_exc()
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse

    app = FastAPI(title="FATTY CAT (Diagnostics Mode)")

    @app.get("/{full_path:path}")
    async def diagnostics(full_path: str = ""):
        return HTMLResponse(
            f"<html><body style='background:#0d1117;color:#f85149;font-family:monospace;padding:24px;'>"
            f"<h2>🐾 Fatty CAT Vercel Cold-Start Diagnostic</h2>"
            f"<p>An error occurred while importing <code>calc_terminal.web.server</code>:</p>"
            f"<pre style='background:#161b22;padding:16px;border-radius:8px;color:#c9d1d9;overflow:auto;'>"
            f"{exc}\n\n{tb}"
            f"</pre></body></html>",
            status_code=500
        )
