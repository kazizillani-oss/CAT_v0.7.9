"""
CCT Recent/Pinned/Favorite Projects (spec v0.7 Sidebar section +
v0.7.7 Workspace Management Preview, sections 1/4/5).

A small, dedicated JSON store — same pattern as workspace.py and
config.py rather than growing either of those. Tracks folders opened
via the IDE's "Open Folder" (ui/sidebar.py), so they can be reopened
"without restarting" (spec's own phrase) and shown in the Welcome
Dashboard's "Recent Projects" list.

v0.7.7 additions (all backward-compatible — every pre-existing
function keeps its exact old behavior):
  - per-entry labels (rename), favorites, and per-workspace sidebar
    collapse state;
  - `workspaces()` — one combined list of every known workspace with
    all metadata, for the multi-workspace explorer and the history
    panel;
  - `search()`, `remove()`, `clear_history()`, `last_opened()`.

Deliberately NOT part of config.py's CCTConfig dataclass: that file's
own docstring already says new settings should land there going
forward, but a growing, unbounded list of recent paths is list-shaped
state, not a scalar setting — mixing the two would make CCTConfig's
schema noisy for the (many) callers that only care about the scalar
settings.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import json
import os
import time

STORE_PATH = os.path.join(os.path.expanduser("~"), ".cct_recent_projects.json")
# v0.7.8.1: Recent Workspaces is now the primary workspace-management
# surface, so the history cap grows from 12 to 20.
MAX_RECENT = 20


def _load():
    if not os.path.exists(STORE_PATH):
        return {"recent": [], "pinned": []}
    try:
        with open(STORE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("recent", [])
        data.setdefault("pinned", [])
        return data
    except Exception:
        return {"recent": [], "pinned": []}


def _save(data):
    try:
        with open(STORE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False


def _norm(path):
    return os.path.abspath(os.path.expanduser(str(path)))


def _get_entry(data, path):
    for r in data["recent"]:
        if r.get("path") == path:
            return r
    return None


def record_opened(path):
    """Call whenever a folder is opened as the IDE workspace root.
    Moves `path` to the front of 'recent', de-duplicated, capped at
    MAX_RECENT so this file doesn't grow forever. Existing metadata
    (label/favorite/collapsed) on the entry is preserved across
    reopens."""
    path = _norm(path)
    data = _load()
    old = _get_entry(data, path)
    meta = {}
    if old is not None:
        meta = {k: old[k] for k in ("label", "favorite", "collapsed") if old.get(k) is not None}
    data["recent"] = [r for r in data["recent"] if r.get("path") != path]
    entry = {"path": path, "opened_at": time.time()}
    entry.update(meta)
    data["recent"].insert(0, entry)
    data["recent"] = data["recent"][:MAX_RECENT]
    _save(data)
    return data


def toggle_pin(path):
    path = _norm(path)
    data = _load()
    pinned = data["pinned"]
    if path in pinned:
        pinned.remove(path)
        is_pinned = False
    else:
        pinned.insert(0, path)
        is_pinned = True
    data["pinned"] = pinned
    _save(data)
    return is_pinned


def is_pinned(path):
    path = _norm(path)
    return path in _load()["pinned"]


def remove_recent(path):
    """Removes a single entry from 'recent' (matched by absolute path) —
    the per-project delete option in the Explorer's Recent Projects
    list. Never touches 'pinned' (unpinning is a separate, deliberate
    action), and never touches any file or folder on disk. Returns
    True/False the same way _save() does; safe to call for a path
    that isn't in the list (no-op)."""
    path = _norm(path)
    data = _load()
    data["recent"] = [r for r in data["recent"] if r.get("path") != path]
    return _save(data)


def clear_recent():
    """Removes every entry from 'recent' (only the stored references in
    STORE_PATH) — never touches 'pinned', and never touches any actual
    file or folder on disk. Safe to call even with an empty list
    already; returns True/False the same way _save() does."""
    data = _load()
    data["recent"] = []
    return _save(data)


def forget_protected():
    """v0.7.9.4 fix: purge any recent/pinned entry that lives inside a
    protected system root (C:\\Windows, C:\\Program Files, ...). An
    earlier build could record e.g. C:\\WINDOWS\\System32 as a 'recent
    project' when `cat` was launched from PowerShell's default cwd;
    reopening such a directory is never useful (generated-file creation
    fails with PermissionError there). Runs once at UI startup. Never
    raises."""
    try:
        from . import workspace as _ws
        data = _load()
        before = (len(data["recent"]), len(data["pinned"]))
        data["recent"] = [r for r in data["recent"]
                          if not _ws.path_is_protected(r.get("path", ""))]
        data["pinned"] = [p for p in data["pinned"]
                          if not _ws.path_is_protected(
                              p.get("path", "") if isinstance(p, dict)
                              else str(p))]
        if (len(data["recent"]), len(data["pinned"])) != before:
            _save(data)
    except Exception:
        pass


def recent():
    return [r["path"] for r in _load()["recent"]]


def pinned():
    return list(_load()["pinned"])


# ================================================== v0.7.7 workspace mgmt ==
# (Workspace Management Preview, sections 4/5 — everything below is
# additive; nothing above changed behavior.)


def label_for(path):
    """The workspace's display label: a user-set custom label, else the
    folder's base name."""
    path = _norm(path)
    entry = _get_entry(_load(), path)
    if entry and entry.get("label"):
        return entry["label"]
    return os.path.basename(path.rstrip(os.sep)) or path


def rename(path, label):
    """Sets a custom display label for a workspace. Empty/None clears
    it back to the folder-name default. Returns the effective label."""
    path = _norm(path)
    label = (label or "").strip()
    data = _load()
    entry = _get_entry(data, path)
    if entry is None:
        data["recent"].insert(0, {"path": path, "opened_at": time.time(),
                                  "label": label or None})
    else:
        if label:
            entry["label"] = label
        else:
            entry.pop("label", None)
    _save(data)
    return label or os.path.basename(path.rstrip(os.sep)) or path


def toggle_favorite(path):
    """Stars/unstars a workspace. Returns the new favorite state."""
    path = _norm(path)
    data = _load()
    entry = _get_entry(data, path)
    if entry is None:
        data["recent"].insert(0, {"path": path, "opened_at": time.time(),
                                  "favorite": True})
        _save(data)
        return True
    favorite = not bool(entry.get("favorite"))
    entry["favorite"] = favorite
    _save(data)
    return favorite


def is_favorite(path):
    path = _norm(path)
    entry = _get_entry(_load(), path)
    return bool(entry and entry.get("favorite"))


def favorites():
    data = _load()
    return [r["path"] for r in data["recent"] if r.get("favorite")]


def set_collapsed(path, collapsed):
    """Stores the explorer collapse state for one workspace (the
    multi-workspace explorer collapses a workspace's tree without
    removing it)."""
    path = _norm(path)
    data = _load()
    entry = _get_entry(data, path)
    if entry is None:
        data["recent"].insert(0, {"path": path, "opened_at": time.time(),
                                  "collapsed": bool(collapsed)})
    else:
        entry["collapsed"] = bool(collapsed)
    _save(data)


def is_collapsed(path):
    path = _norm(path)
    entry = _get_entry(_load(), path)
    return bool(entry and entry.get("collapsed"))


def workspaces():
    """One combined list of every known workspace — recent + pinned
    union, each entry {"path", "label", "pinned", "favorite",
    "collapsed", "opened_at"}. Pinned entries missing from recent are
    included with their base-name label. Ordered: pinned first, then
    most-recently-opened."""
    data = _load()
    by_path = {}
    for r in data["recent"]:
        by_path[r["path"]] = {
            "path": r["path"],
            "label": r.get("label") or os.path.basename(r["path"].rstrip(os.sep)) or r["path"],
            "favorite": bool(r.get("favorite")),
            "collapsed": bool(r.get("collapsed")),
            "opened_at": r.get("opened_at", 0),
            "pinned": False,
        }
    for p in data["pinned"]:
        p = _norm(p)
        if p in by_path:
            by_path[p]["pinned"] = True
        else:
            by_path[p] = {
                "path": p,
                "label": os.path.basename(p.rstrip(os.sep)) or p,
                "favorite": False,
                "collapsed": False,
                "opened_at": 0,
                "pinned": True,
            }
    ordered = sorted(by_path.values(),
                     key=lambda w: (not w["pinned"], -w.get("opened_at", 0)))
    return ordered


def last_opened():
    """The most recently opened workspace path, or None."""
    r = _load()["recent"]
    return r[0]["path"] if r else None


def search(query):
    """Case-insensitive search across every known workspace's path and
    label. Empty query returns everything (workspaces())."""
    q = (query or "").strip().lower()
    if not q:
        return workspaces()
    return [w for w in workspaces()
            if q in w["path"].lower() or q in w["label"].lower()]


def remove(path):
    """Full removal from the history: recent, pinned, and favorite
    references (pinned list holds bare paths). Never touches files on
    disk. Returns True if anything was removed."""
    path = _norm(path)
    data = _load()
    before = (len(data["recent"]), len(data["pinned"]))
    data["recent"] = [r for r in data["recent"] if r.get("path") != path]
    data["pinned"] = [p for p in data["pinned"] if p != path]
    changed = (len(data["recent"]), len(data["pinned"])) != before
    _save(data)
    return changed


def clear_history():
    """Removes every stored workspace reference (recent + pinned +
    favorites) — only the JSON store, never files on disk. Returns
    True when the store had anything to clear."""
    data = _load()
    had = bool(data["recent"] or data["pinned"])
    data["recent"] = []
    data["pinned"] = []
    _save(data)
    return had
