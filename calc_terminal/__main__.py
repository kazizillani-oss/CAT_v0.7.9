"""
CAT v0.7.9.0 — `python -m calc_terminal` support.

Delegates to the same console entry point the installed `cat` command
uses (calc_terminal.cli:main), so a source checkout can always be
launched with `python -m calc_terminal [path] [--version]` even before
a pip install registers the console scripts.
"""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
