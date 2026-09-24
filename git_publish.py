#!/usr/bin/env python3
"""Standalone script to execute the verified CAT Git publishing and GitHub update workflow.

Usage:
    python git_publish.py [optional commit message]
"""

import os
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
pkg_dir = here / "CAT_v0.7.4"
sys.path.insert(0, str(pkg_dir))

from calc_terminal.git_sync import sync_and_publish


def main():
    message = " ".join(sys.argv[1:]).strip() if len(sys.argv) > 1 else None
    rc = sync_and_publish(repo_path=str(here), message=message)
    sys.exit(rc)


if __name__ == "__main__":
    main()
