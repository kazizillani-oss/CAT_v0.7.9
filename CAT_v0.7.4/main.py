#!/usr/bin/env python3
"""
Coding Agent Terminal (CAT) — entry point.

Run with:
    python main.py

When imported by an ASGI server or Vercel Python runtime, exposes `app`
(the Fatty CAT FastAPI web application) via module __getattr__.
"""

from calc_terminal.cli import main


def __getattr__(name: str):
    if name == "app":
        from calc_terminal.web.server import app as _fastapi_app
        return _fastapi_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if __name__ == "__main__":
    raise SystemExit(main())
