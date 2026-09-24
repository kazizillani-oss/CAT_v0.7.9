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

import argparse
from calc_terminal.git_sync import sync_and_publish


def main():
    parser = argparse.ArgumentParser(
        description="Stage, validate commit, and sync/publish CAT CLI changes to GitHub."
    )
    parser.add_argument(
        "message",
        nargs="*",
        default=None,
        help="Optional commit message. If omitted or empty, an automatic descriptive message is generated.",
    )
    parser.add_argument(
        "--remote",
        default="origin",
        help="Git remote name (default: origin).",
    )
    parser.add_argument(
        "--branch",
        default=None,
        help="Target branch (default: current branch or main).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be committed without creating or pushing commits.",
    )
    args = parser.parse_args()

    commit_msg = " ".join(args.message).strip() if args.message else None
    rc = sync_and_publish(
        repo_path=str(repo_root),
        message=commit_msg,
        remote=args.remote,
        branch=args.branch,
        dry_run=args.dry_run,
    )
    sys.exit(rc)


if __name__ == "__main__":
    main()
