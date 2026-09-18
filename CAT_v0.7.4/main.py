#!/usr/bin/env python3
"""
Coding Agent Terminal (CAT) — entry point.

Run with:
    python main.py

No third-party packages are required for the fallback terminal. If
`textual` is installed AND stdin is a real interactive terminal, this
launches the primary chat UI (calc_terminal/ui/) by default; otherwise
it falls back to the classic print()/input() REPL — same command set
either way, see calc_terminal/commands_data.py.

This file is a thin shim over calc_terminal.cli so that `python main.py`
and the installed `cct` console script share one code path.
"""

from calc_terminal.cli import main


if __name__ == "__main__":
    raise SystemExit(main())