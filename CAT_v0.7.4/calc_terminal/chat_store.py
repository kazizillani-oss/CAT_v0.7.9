"""
CAT — Workspace-aware Chat History Store.

Persists chat sessions to ~/.cat/chats/ with strict workspace isolation,
per-conversation AI mode metadata, and backward-compatible migration from
legacy chat records.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

log = logging.getLogger("cat.chat_store")

_CHATS_DIR = os.path.join(os.path.expanduser("~"), ".cat", "chats")
_INDEX_FILE = os.path.join(_CHATS_DIR, "_index.json")
_SCHEMA_VERSION = 2
_LEGACY_WORKSPACE = "__legacy_unassigned__"


def _ensure_dir():
    os.makedirs(_CHATS_DIR, exist_ok=True)


def _index_path() -> str:
    return _INDEX_FILE


def _chat_path(chat_id: str) -> str:
    safe = chat_id.replace("/", "_").replace("\\", "_").replace("..", "_")
    return os.path.join(_CHATS_DIR, f"{safe}.json")


def normalize_workspace_path(path: Optional[str]) -> str:
    """Canonical absolute path for workspace comparison (platform-aware)."""
    if not path or not str(path).strip():
        return ""
    try:
        raw = str(path).strip()
        if "\x00" in raw:
            return ""
        expanded = os.path.expanduser(raw)
        resolved = os.path.abspath(expanded)
        normalized = os.path.normpath(resolved)
        if os.name == "nt":
            normalized = normalized.rstrip("\\")
        else:
            normalized = normalized.rstrip("/")
        return normalized
    except (OSError, ValueError, TypeError):
        return ""


def paths_equal(a: Optional[str], b: Optional[str]) -> bool:
    """Strict workspace ownership comparison — never loose substring match."""
    na = normalize_workspace_path(a)
    nb = normalize_workspace_path(b)
    if not na or not nb:
        return False
    return os.path.normcase(na) == os.path.normcase(nb)


def workspace_key(path: Optional[str]) -> str:
    """Stable grouping key for workspace-organized UI."""
    norm = normalize_workspace_path(path)
    if not norm:
        return _LEGACY_WORKSPACE
    return os.path.normcase(norm)


def workspace_display_name(path: Optional[str]) -> str:
    norm = normalize_workspace_path(path)
    if not norm:
        return "Legacy / Unassigned"
    base = os.path.basename(norm.rstrip(os.sep))
    return base or norm


def _atomic_write_json(path: str, data: Any):
    _ensure_dir()
    tmp = f"{path}.{uuid.uuid4().hex}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    try:
        os.replace(tmp, path)
    except OSError:
        try:
            if os.path.exists(path):
                os.remove(path)
            os.replace(tmp, path)
        except OSError:
            shutil.copyfile(tmp, path)
            try:
                os.remove(tmp)
            except OSError:
                pass


def _load_index() -> List[Dict]:
    _ensure_dir()
    try:
        with open(_index_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return []


def _save_index(entries: List[Dict]):
    _atomic_write_json(_index_path(), entries)


def _migrate_turn(turn: Dict) -> Dict:
    turn = dict(turn)
    if "timestamp" not in turn:
        turn["timestamp"] = time.time()
    return turn


def _migrate_chat(chat: Dict) -> Dict:
    """Upgrade legacy chat records in-place (non-destructive)."""
    chat = dict(chat)
    version = chat.get("schema_version", 1)

    ws = chat.get("workspace_root") or chat.get("project_path") or ""
    ws_norm = normalize_workspace_path(ws)
    chat["workspace_root"] = ws_norm
    chat["project_path"] = ws_norm  # legacy alias

    if not ws_norm:
        chat["legacy_unassigned"] = True
    else:
        chat.setdefault("legacy_unassigned", False)

    chat.setdefault("cwd", ws_norm or os.getcwd())
    chat.setdefault("created_at", chat.get("updated_at", time.time()))
    chat.setdefault("updated_at", chat.get("created_at", time.time()))
    chat.setdefault("last_opened_at", 0.0)
    chat.setdefault("turn_count", len(chat.get("turns", [])))
    chat.setdefault("summary", chat.get("summary", ""))
    chat.setdefault("pinned", bool(chat.get("pinned", False)))
    chat.setdefault("archived", bool(chat.get("archived", False)))
    chat.setdefault("provider", chat.get("provider", "") or "")
    chat.setdefault("model", chat.get("model", "") or "")

    turns = [_migrate_turn(t) for t in chat.get("turns", [])]
    chat["turns"] = turns

    first_mode = ""
    last_mode = ""
    for t in turns:
        m = t.get("mode") or (t.get("mode_snapshot") or {}).get("mode", "")
        if m:
            if not first_mode:
                first_mode = m
            last_mode = m

    chat.setdefault("created_mode", chat.get("created_mode") or first_mode or "notebook")
    chat.setdefault("current_mode", chat.get("current_mode") or last_mode or chat["created_mode"])

    if version < _SCHEMA_VERSION:
        chat["schema_version"] = _SCHEMA_VERSION
        _save_chat(chat)
        log.info("migrated chat %s to schema v%s", chat.get("id"), _SCHEMA_VERSION)

    return chat


def _load_chat_file(chat_id: str) -> Optional[Dict]:
    path = _chat_path(chat_id)
    try:
        with open(path, "r", encoding="utf-8") as f:
            chat = json.load(f)
            if isinstance(chat, dict):
                return _migrate_chat(chat)
    except (FileNotFoundError, json.JSONDecodeError, TypeError):
        pass
    return None


def _save_chat(chat: Dict):
    chat = _migrate_chat(chat)
    _atomic_write_json(_chat_path(chat.get("id", "unknown")), chat)


def _index_entry(chat: Dict) -> Dict:
    chat = _migrate_chat(chat)
    return {k: v for k, v in chat.items() if k != "turns"}


def list_chats() -> List[Dict]:
    return [_migrate_chat(dict(e)) for e in _load_index()]


def get_chat(chat_id: str) -> Optional[Dict]:
    chat = _load_chat_file(chat_id)
    if chat:
        entry = _index_entry(chat)
        index = _load_index()
        found = any(e.get("id") == chat_id for e in index)
        if not found:
            index.insert(0, entry)
            _save_index(index)
    return chat


def create_chat(
    name: Optional[str] = None,
    project_path: Optional[str] = None,
    *,
    workspace_root: Optional[str] = None,
    cwd: Optional[str] = None,
    created_mode: Optional[str] = None,
    current_mode: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict:
    """Create a new empty chat bound to a workspace."""
    chat_id = str(uuid.uuid4())[:12]
    now = time.time()
    ws = normalize_workspace_path(workspace_root or project_path or cwd or os.getcwd())
    mode = created_mode or current_mode or "notebook"
    chat = {
        "schema_version": _SCHEMA_VERSION,
        "id": chat_id,
        "name": name or f"Chat {time.strftime('%m/%d %H:%M')}",
        "created_at": now,
        "updated_at": now,
        "last_opened_at": now,
        "turn_count": 0,
        "workspace_root": ws,
        "project_path": ws,
        "cwd": normalize_workspace_path(cwd) or ws or normalize_workspace_path(os.getcwd()),
        "created_mode": mode,
        "current_mode": current_mode or mode,
        "provider": provider or "",
        "model": model or "",
        "pinned": False,
        "archived": False,
        "legacy_unassigned": not bool(ws),
        "turns": [],
        "summary": "",
    }
    _save_chat(chat)
    index = _load_index()
    index.insert(0, _index_entry(chat))
    _save_index(index)
    log.info("created chat %s workspace=%s mode=%s", chat_id, ws or _LEGACY_WORKSPACE, mode)
    return chat


def save_chat(chat: Dict):
    chat = _migrate_chat(chat)
    _save_chat(chat)
    index = _load_index()
    entry = _index_entry(chat)
    found = False
    for i, e in enumerate(index):
        if e.get("id") == chat.get("id"):
            index[i] = entry
            found = True
            break
    if not found:
        index.insert(0, entry)
    _save_index(index)


def rename_chat(chat_id: str, new_name: str) -> bool:
    chat = get_chat(chat_id)
    if not chat:
        return False
    chat["name"] = new_name.strip() or chat.get("name", "Untitled")
    chat["updated_at"] = time.time()
    save_chat(chat)
    return True


def delete_chat(chat_id: str) -> bool:
    path = _chat_path(chat_id)
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    index = _load_index()
    index = [e for e in index if e.get("id") != chat_id]
    _save_index(index)
    log.info("deleted chat %s", chat_id)
    return True


def update_chat_metadata(chat_id: str, **fields) -> bool:
    chat = get_chat(chat_id)
    if not chat:
        return False
    for key, val in fields.items():
        if key == "workspace_root" or key == "project_path":
            ws = normalize_workspace_path(val)
            chat["workspace_root"] = ws
            chat["project_path"] = ws
            chat["legacy_unassigned"] = not bool(ws)
        elif key in chat or key in (
            "pinned", "archived", "current_mode", "created_mode",
            "provider", "model", "cwd", "last_opened_at", "summary",
        ):
            chat[key] = val
    chat["updated_at"] = time.time()
    save_chat(chat)
    return True


def touch_last_opened(chat_id: str) -> bool:
    return update_chat_metadata(chat_id, last_opened_at=time.time())


def pin_chat(chat_id: str, pinned: bool = True) -> bool:
    return update_chat_metadata(chat_id, pinned=bool(pinned))


def archive_chat(chat_id: str, archived: bool = True) -> bool:
    return update_chat_metadata(chat_id, archived=bool(archived))


def associate_chat_workspace(chat_id: str, workspace_root: str) -> bool:
    ws = normalize_workspace_path(workspace_root)
    if not ws:
        return False
    return update_chat_metadata(
        chat_id,
        workspace_root=ws,
        project_path=ws,
        legacy_unassigned=False,
    )


def duplicate_chat(chat_id: str, new_name: Optional[str] = None) -> Optional[Dict]:
    src = get_chat(chat_id)
    if not src:
        return None
    copy = create_chat(
        name=new_name or f"{src.get('name', 'Chat')} (copy)",
        workspace_root=src.get("workspace_root"),
        cwd=src.get("cwd"),
        created_mode=src.get("created_mode"),
        current_mode=src.get("current_mode"),
        provider=src.get("provider"),
        model=src.get("model"),
    )
    copy["turns"] = [dict(t) for t in src.get("turns", [])]
    copy["turn_count"] = len(copy["turns"])
    copy["summary"] = src.get("summary", "")
    save_chat(copy)
    return copy


def add_turn(
    chat_id: str,
    role: str,
    content: str,
    *,
    mode: Optional[str] = None,
    mode_snapshot: Optional[Dict] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> Optional[Dict]:
    """Append a turn with full mode/provider metadata."""
    chat = get_chat(chat_id)
    if not chat:
        return None
    turn: Dict[str, Any] = {
        "role": role,
        "content": content,
        "timestamp": time.time(),
    }
    if mode:
        turn["mode"] = mode
    if mode_snapshot:
        turn["mode_snapshot"] = dict(mode_snapshot)
        turn.setdefault("mode", mode_snapshot.get("mode", mode))
    elif mode:
        try:
            from . import ai_modes
            turn["mode_snapshot"] = ai_modes.snapshot(mode)
        except Exception:
            pass
    if provider:
        turn["provider"] = provider
    if model:
        turn["model"] = model
    chat.setdefault("turns", []).append(turn)
    chat["turn_count"] = len(chat["turns"])
    chat["updated_at"] = time.time()
    if mode:
        chat["current_mode"] = mode
    if provider:
        turn_prov = provider
        chat["provider"] = provider
    if model:
        chat["model"] = model
    save_chat(chat)
    return turn


def update_turn(chat_id: str, turn_index: int, content: str) -> bool:
    chat = get_chat(chat_id)
    if not chat:
        return False
    turns = chat.get("turns", [])
    if 0 <= turn_index < len(turns):
        turns[turn_index]["content"] = content
        turns[turn_index]["edited"] = True
        chat["updated_at"] = time.time()
        save_chat(chat)
        return True
    return False


def _summary_from_entry(entry: Dict) -> Dict:
    entry = _migrate_chat(dict(entry))
    ws = entry.get("workspace_root") or entry.get("project_path") or ""
    return {
        "id": entry.get("id"),
        "name": entry.get("name", "Untitled"),
        "turn_count": entry.get("turn_count", 0),
        "updated_at": entry.get("updated_at", 0),
        "created_at": entry.get("created_at", 0),
        "last_opened_at": entry.get("last_opened_at", 0),
        "workspace_root": ws,
        "project_path": ws,
        "cwd": entry.get("cwd", ws),
        "created_mode": entry.get("created_mode", "notebook"),
        "current_mode": entry.get("current_mode", entry.get("created_mode", "notebook")),
        "provider": entry.get("provider", ""),
        "model": entry.get("model", ""),
        "pinned": bool(entry.get("pinned", False)),
        "archived": bool(entry.get("archived", False)),
        "legacy_unassigned": bool(entry.get("legacy_unassigned", not bool(ws))),
        "summary": entry.get("summary", ""),
    }


def get_chat_summaries(
    workspace_root: Optional[str] = None,
    *,
    include_archived: bool = False,
    include_legacy: bool = True,
) -> List[Dict]:
    """Metadata-only list; optionally scoped to one workspace."""
    summaries = []
    target = normalize_workspace_path(workspace_root) if workspace_root else ""
    for entry in _load_index():
        s = _summary_from_entry(entry)
        if not include_archived and s.get("archived"):
            continue
        if s.get("legacy_unassigned") and not include_legacy:
            continue
        if target:
            if s.get("legacy_unassigned"):
                continue
            if not paths_equal(s.get("workspace_root"), target):
                continue
        summaries.append(s)
    summaries.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
    return summaries


def filter_chats(
    summaries: Sequence[Dict],
    *,
    filter_name: str = "all",
    mode_filter: Optional[str] = None,
    workspace_root: Optional[str] = None,
) -> List[Dict]:
    """Apply UI filter presets to summary list."""
    items = list(summaries)
    ws = normalize_workspace_path(workspace_root) if workspace_root else ""
    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day).timestamp()
    yesterday_start = (datetime(now.year, now.month, now.day) - timedelta(days=1)).timestamp()
    week_start = (now - timedelta(days=7)).timestamp()

    if filter_name == "current_workspace":
        if ws:
            items = [c for c in items if paths_equal(c.get("workspace_root"), ws) and not c.get("archived")]
        else:
            items = []
    elif filter_name == "pinned":
        items = [c for c in items if c.get("pinned") and not c.get("archived")]
    elif filter_name == "archived":
        items = [c for c in items if c.get("archived")]
    elif filter_name == "today":
        items = [c for c in items if c.get("updated_at", 0) >= today_start and not c.get("archived")]
    elif filter_name == "recent":
        items = [c for c in items if c.get("updated_at", 0) >= week_start and not c.get("archived")]
    else:
        items = [c for c in items if not c.get("archived")]

    if mode_filter:
        mf = mode_filter.lower()
        items = [
            c for c in items
            if (c.get("current_mode") or c.get("created_mode", "")).lower() == mf
        ]
    return items


def group_chats_by_workspace(summaries: Sequence[Dict]) -> List[Dict]:
    """Group chat summaries by workspace for hierarchical UI."""
    buckets: Dict[str, Dict] = {}
    seen_ids: set = set()
    for s in summaries:
        cid = s.get("id")
        if cid in seen_ids:
            continue
        seen_ids.add(cid)
        key = workspace_key(s.get("workspace_root"))
        if key not in buckets:
            path = s.get("workspace_root") or ""
            buckets[key] = {
                "workspace_key": key,
                "workspace_root": path,
                "workspace_name": workspace_display_name(path),
                "chat_count": 0,
                "last_activity": 0.0,
                "pinned": False,
                "chats": [],
            }
        bucket = buckets[key]
        bucket["chats"].append(s)
        bucket["chat_count"] += 1
        bucket["last_activity"] = max(bucket["last_activity"], s.get("updated_at", 0))
        if s.get("pinned"):
            bucket["pinned"] = True

    groups = sorted(buckets.values(), key=lambda g: g["last_activity"], reverse=True)
    for g in groups:
        g["chats"].sort(key=lambda c: c.get("updated_at", 0), reverse=True)
    return groups


def _date_bucket(ts: float) -> str:
    if not ts:
        return "Previous"
    now = datetime.now()
    dt = datetime.fromtimestamp(ts)
    today = datetime(now.year, now.month, now.day)
    chat_day = datetime(dt.year, dt.month, dt.day)
    delta = (today - chat_day).days
    if delta == 0:
        return "Today"
    if delta == 1:
        return "Yesterday"
    if delta < 7:
        return "This Week"
    return "Previous"


def group_chats_by_date(chats: Sequence[Dict]) -> List[Tuple[str, List[Dict]]]:
    order = ["Today", "Yesterday", "This Week", "Previous"]
    buckets: Dict[str, List[Dict]] = {k: [] for k in order}
    seen_ids: set = set()
    for c in chats:
        cid = c.get("id")
        if cid in seen_ids:
            continue
        seen_ids.add(cid)
        buckets[_date_bucket(c.get("updated_at", 0))].append(c)
    return [(label, buckets[label]) for label in order if buckets[label]]


def get_pinned_chats(limit: int = 20, workspace_root: Optional[str] = None) -> List[Dict]:
    if workspace_root:
        pinned = [s for s in get_chat_summaries(workspace_root, include_archived=False) if s.get("pinned")]
    else:
        pinned = [s for s in get_chat_summaries(include_archived=False) if s.get("pinned")]
    pinned.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
    return pinned[:limit]


def get_recent_chats(limit: int = 10, workspace_root: Optional[str] = None) -> List[Dict]:
    if workspace_root:
        items = get_chat_summaries(workspace_root, include_archived=False)
    else:
        items = get_chat_summaries(include_archived=False)
    items = [c for c in items if c.get("last_opened_at") or c.get("updated_at")]
    items.sort(
        key=lambda x: x.get("last_opened_at") or x.get("updated_at", 0),
        reverse=True,
    )
    return items[:limit]


def search_chats(
    query: str,
    *,
    workspace_root: Optional[str] = None,
    scope: str = "current",
    mode_filter: Optional[str] = None,
    provider_filter: Optional[str] = None,
    date_after: Optional[float] = None,
) -> List[Dict]:
    """Search chat metadata and message content."""
    q = (query or "").strip().lower()
    if scope == "current":
        if workspace_root:
            candidates = get_chat_summaries(workspace_root, include_archived=True, include_legacy=False)
        else:
            candidates = []
    else:
        candidates = get_chat_summaries(include_archived=True)

    if mode_filter:
        mf = mode_filter.lower()
        candidates = [
            c for c in candidates
            if (c.get("current_mode") or c.get("created_mode", "")).lower() == mf
        ]
    if provider_filter:
        pf = provider_filter.lower()
        candidates = [c for c in candidates if pf in (c.get("provider") or "").lower()]
    if date_after:
        candidates = [c for c in candidates if c.get("updated_at", 0) >= date_after]

    if not q:
        return candidates

    results: List[Dict] = []
    seen: set = set()
    for entry in candidates:
        cid = entry.get("id", "")
        if cid in seen:
            continue
        name = entry.get("name", "").lower()
        ws_name = workspace_display_name(entry.get("workspace_root")).lower()
        ws_path = (entry.get("workspace_root") or "").lower()
        mode = (entry.get("current_mode") or entry.get("created_mode") or "").lower()
        model = (entry.get("model") or "").lower()
        provider = (entry.get("provider") or "").lower()
        if any(q in field for field in (name, ws_name, ws_path, mode, model, provider, cid.lower())):
            results.append(entry)
            seen.add(cid)
            continue
        chat = get_chat(cid)
        if not chat:
            continue
        for turn in chat.get("turns", []):
            if q in turn.get("content", "").lower():
                results.append(entry)
                seen.add(cid)
                break
    return results


def export_chat_markdown(chat_id: str) -> Optional[str]:
    chat = get_chat(chat_id)
    if not chat:
        return None
    lines = [
        f"# {chat.get('name', 'CAT Conversation')}",
        "",
        f"- **Workspace:** `{chat.get('workspace_root') or 'Unassigned'}`",
        f"- **Mode:** {chat.get('current_mode') or chat.get('created_mode', 'notebook')}",
        f"- **Provider:** {chat.get('provider') or 'unknown'}",
        f"- **Model:** {chat.get('model') or 'unknown'}",
        f"- **Created:** {datetime.fromtimestamp(chat.get('created_at', 0)).isoformat()}",
        f"- **Updated:** {datetime.fromtimestamp(chat.get('updated_at', 0)).isoformat()}",
        "",
        "---",
        "",
    ]
    for turn in chat.get("turns", []):
        role = turn.get("role", "user")
        label = "You" if role == "user" else "CAT Assistant" if role == "assistant" else "System"
        ts = turn.get("timestamp", 0)
        when = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else ""
        mode = turn.get("mode") or (turn.get("mode_snapshot") or {}).get("mode", "")
        header = f"## {label}"
        if when:
            header += f" ({when})"
        if mode:
            header += f" — {mode}"
        lines.extend([header, "", turn.get("content", ""), "", "---", ""])
    return "\n".join(lines)


def validate_workspace_metadata(path: Optional[str]) -> bool:
    """Reject malformed paths that could corrupt grouping."""
    if not path:
        return True
    norm = normalize_workspace_path(path)
    if not norm:
        return False
    if "\x00" in norm:
        return False
    return True
