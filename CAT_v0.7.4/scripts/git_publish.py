#!/usr/bin/env python3
"""Standalone script to execute the verified CAT Git publishing and GitHub update workflow."""

import os
import sys
from pathlib import Path

# Add package root to sys.path
here = Path(__file__).resolve().parent
repo_root = here.parent.parent
pkg_root = here.parent
sys.path.insert(0, str(pkg_root))

from calc_terminal.git_sync import sync_and_publish


def main():
    message = " ".join(sys.argv[1:]).strip() if len(sys.argv) > 1 else None
    rc = sync_and_publish(repo_path=str(repo_root), message=message)
    sys.exit(rc)


if __name__ == "__main__":
    main()
