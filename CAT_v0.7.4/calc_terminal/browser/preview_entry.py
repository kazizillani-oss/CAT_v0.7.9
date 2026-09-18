"""CAT browser/ — entry-point detection + workspace-relative URLs.

Given an open file (or nothing), decide WHAT to preview and WHERE the
web root is:

    index.html anywhere in the tree  → its folder becomes the web root
    docs/site/index.html             → web root = docs/site
    no html at all                   → (None, root) → honest error

Keeps the controller free of path heuristics and is unit-testable.
"""

import os
from typing import Optional, Tuple

ENTRY_NAMES = ("index.html", "index.htm", "default.html")


def _is_html(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in (".html", ".htm")


def find_entry_file(open_path: Optional[str],
                    workspace_root: str) -> Tuple[Optional[str], str]:
    """Return (entry_html_path, web_root).

    Order:
      1. the open file itself, when it's HTML;
      2. an index.html next to the open file, walking UP to the root;
      3. workspace_root/index.html;
      4. shallowest index.html anywhere under the root (bounded walk).
    """
    root = os.path.abspath(workspace_root)
    if open_path and _is_html(open_path) and os.path.isfile(open_path):
        # prefer a sibling index if the open file sits inside a folder
        # that has one (e.g. user opened src/about.html but src/index.html
        # exists → still treat src/ as the site)
        folder = os.path.dirname(open_path)
        for name in ENTRY_NAMES:
            candidate = os.path.join(folder, name)
            if os.path.isfile(candidate):
                return candidate, folder
        return open_path, folder
    if open_path and os.path.isdir(open_path):
        for name in ENTRY_NAMES:
            candidate = os.path.join(open_path, name)
            if os.path.isfile(candidate):
                return candidate, open_path
    # direct root entries
    for name in ENTRY_NAMES:
        candidate = os.path.join(root, name)
        if os.path.isfile(candidate):
            return candidate, root
    # bounded search (depth ≤ 3) for the shallowest entry page
    best = None
    best_depth = 99
    base_depth = root.rstrip(os.sep).count(os.sep)
    for dirpath, dirnames, filenames in os.walk(root):
        depth = dirpath.rstrip(os.sep).count(os.sep) - base_depth
        if depth > 3:
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames
                       if d not in ("node_modules", ".git", "__pycache__",
                                    ".venv", "venv")]
        for name in ENTRY_NAMES:
            if name in filenames:
                if depth < best_depth:
                    best = os.path.join(dirpath, name)
                    best_depth = depth
                break
    if best is not None:
        return best, os.path.dirname(best)
    return None, root


def relative_url_for(path: str, web_root: str) -> Optional[str]:
    """Filesystem path → URL path relative to the served root."""
    path = os.path.abspath(path)
    web_root = os.path.abspath(web_root).rstrip(os.sep) + os.sep
    try:
        rel = os.path.relpath(path, web_root)
    except ValueError:
        return None
    if rel.startswith(".."):
        return None
    return rel.replace(os.sep, "/")


def url_for_file(path: str, server_url: str,
                 web_root: str) -> Optional[str]:
    rel = relative_url_for(path, web_root)
    if rel is None:
        return None
    return server_url.rstrip("/") + "/" + rel
