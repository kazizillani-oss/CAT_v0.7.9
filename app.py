"""
Fatty CAT Cloud IDE & Web Server root ASGI application entrypoint.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent
_cat_dir = _repo_root / "CAT_v0.7.4"

for p in (str(_cat_dir), str(_repo_root), os.getcwd(), os.path.join(os.getcwd(), "CAT_v0.7.4")):
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault("VERCEL", "1")
os.environ.setdefault("CAT_ENV", "production")

from calc_terminal.web.server import app
