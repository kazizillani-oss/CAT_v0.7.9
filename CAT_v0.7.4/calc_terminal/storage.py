"""
CAT CLI — Centralized User Storage, Backup & Native `.cat` File Format System.

Provides persistent, platform-aware user storage for:
- Agents (custom & imported)
- Missions & Tasks (checkpoints, execution history)
- Chats & Workspace sessions
- Agent Memory & Context
- Integrations & MCP Configurations
- Storage metrics, safe backups & non-destructive migrations
"""

from __future__ import annotations

import copy
import datetime
import json
import logging
import os
import re
import shutil
import sys
import time
import zipfile
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("cat.storage")

CAT_FORMAT_VERSION = 1
SUPPORTED_CAT_TYPES = {
    "agent", "mission", "chat", "project", "workspace", "integration",
    "benchmark", "model", "experiment", "dataset", "report"
}

# Sensitive token / secret detectors for .cat export & storage sanitation
SECRET_PATTERNS = [
    re.compile(r'(?i)(api[_-]?key|apikey|secret|token|password|passwd|auth)\s*[:=]\s*["\']?([A-Za-z0-9_\-\.]{12,})["\']?'),
    re.compile(r'(?i)bearer\s+([A-Za-z0-9_\-\.]{20,})'),
    re.compile(r'sk-[A-Za-z0-9_-]{20,}'),
    re.compile(r'ghp_[A-Za-z0-9]{36}'),
    re.compile(r'xai-[A-Za-z0-9_-]{20,}'),
]
REDACTED_SECRET = "[REDACTED_SECRET]"


# -----------------------------------------------------------------------------
# Storage Directory Resolution
# -----------------------------------------------------------------------------

def get_storage_dir() -> str:
    """The canonical CAT application-data directory for this platform.

    Precedence:
      1. CAT_STORAGE_DIR or CCT_DATA_DIR environment variable
      2. Windows: %LOCALAPPDATA%\\CAT (or fallback %USERPROFILE%\\.cat)
      3. macOS: ~/Library/Application Support/CAT
      4. Linux: $XDG_DATA_HOME/cat or ~/.cat
    """
    override = os.environ.get("CAT_STORAGE_DIR", "").strip() or os.environ.get("CCT_DATA_DIR", "").strip()
    if override:
        path = os.path.abspath(override)
        _ensure_subdirs(path)
        return path

    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if base and os.path.isdir(base):
            path = os.path.join(base, "CAT")
        else:
            path = os.path.join(os.path.expanduser("~"), ".cat")
    elif sys.platform == "darwin":
        path = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "CAT")
    else:
        xdg = os.environ.get("XDG_DATA_HOME", "").strip()
        if xdg:
            path = os.path.join(xdg, "cat")
        else:
            path = os.path.join(os.path.expanduser("~"), ".cat")

    _ensure_subdirs(path)
    return path


def _ensure_subdirs(base: str) -> None:
    subdirs = [
        "agents",
        "missions",
        "chats",
        "memory",
        "integrations",
        "mcp",
        "cache",
        "workspaces",
        "backups",
        "settings",
        "benchmarks",
        "models",
        "experiments",
        "datasets",
        "reports",
        "artifacts",
    ]
    try:
        os.makedirs(base, exist_ok=True)
        for sub in subdirs:
            os.makedirs(os.path.join(base, sub), exist_ok=True)
    except Exception as e:
        logger.warning(f"Could not initialize all CAT storage subdirectories: {e}")


def get_subpath(*parts: str) -> str:
    """Returns absolute path inside the CAT storage directory."""
    return os.path.join(get_storage_dir(), *parts)


# -----------------------------------------------------------------------------
# Secret Sanitization
# -----------------------------------------------------------------------------

def sanitize_secrets(data: Any) -> Any:
    """Recursively traverses strings, lists, and dicts to redact secrets."""
    if isinstance(data, str):
        sanitized = data
        for pat in SECRET_PATTERNS:
            sanitized = pat.sub(REDACTED_SECRET, sanitized)
        return sanitized
    elif isinstance(data, dict):
        out = {}
        for k, v in data.items():
            k_lower = str(k).lower()
            if any(s in k_lower for s in ("key", "secret", "token", "password", "auth_bearer")):
                out[k] = REDACTED_SECRET
            else:
                out[k] = sanitize_secrets(v)
        return out
    elif isinstance(data, list):
        return [sanitize_secrets(item) for item in data]
    return data


# -----------------------------------------------------------------------------
# Native `.cat` File Format (Schema v1)
# -----------------------------------------------------------------------------

def create_cat_envelope(
    obj_type: str,
    obj_id: str,
    data: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
    version: int = CAT_FORMAT_VERSION,
) -> Dict[str, Any]:
    """Wraps an object into the canonical CAT envelope schema."""
    clean_data = sanitize_secrets(copy.deepcopy(data))
    now = time.time()
    meta = {
        "id": obj_id,
        "name": (metadata or {}).get("name") or obj_id,
        "author": (metadata or {}).get("author") or "user",
        "created_at": (metadata or {}).get("created_at") or now,
        "updated_at": now,
        "compatibility": f">=0.8.0",
    }
    if metadata:
        for k, v in metadata.items():
            if k not in meta:
                meta[k] = v

    return {
        "format": "cat",
        "version": version,
        "type": obj_type,
        "id": obj_id,
        "metadata": meta,
        "data": clean_data,
    }


def validate_cat_envelope(envelope: Any) -> Tuple[bool, str, List[str]]:
    """Validates a `.cat` dictionary against format rules.

    Returns:
        (is_valid, error_reason, list_of_security_warnings)
    """
    if not isinstance(envelope, dict):
        return False, "Not a valid JSON/dictionary structure", []

    if envelope.get("format") != "cat":
        return False, f"Missing or invalid format header: expected 'cat', got '{envelope.get('format')}'", []

    ver = envelope.get("version")
    if not isinstance(ver, int) or ver <= 0:
        return False, f"Invalid schema version: {ver}", []

    if ver > CAT_FORMAT_VERSION:
        return False, f"Unsupported newer CAT schema version: {ver} (Current supported version: {CAT_FORMAT_VERSION})", []

    obj_type = envelope.get("type")
    if obj_type not in SUPPORTED_CAT_TYPES:
        return False, f"Unsupported object type '{obj_type}'. Supported: {', '.join(sorted(SUPPORTED_CAT_TYPES))}", []

    obj_id = envelope.get("id")
    if not obj_id or not isinstance(obj_id, str):
        return False, "Missing or empty object 'id'", []

    data = envelope.get("data")
    if not isinstance(data, dict):
        return False, "Missing or non-dictionary 'data' payload", []

    warnings: List[str] = []

    # Security audits on payload
    if obj_type == "agent":
        tools = data.get("tools") or []
        if isinstance(tools, list):
            if any(t in ("run_terminal", "shell_commands", "execute_python") for t in tools):
                warnings.append("Terminal / code execution tools requested")
            if any(t in ("write_file", "delete_file", "archive_delete_entries") for t in tools):
                warnings.append("Mutating filesystem tools requested")
            if any("mcp" in str(t).lower() for t in tools):
                warnings.append("MCP tool access requested")
        perms = data.get("permissions")
        if isinstance(perms, dict):
            if perms.get("level") == "full":
                warnings.append("Agent requests 'full' access permission level")

    elif obj_type == "mission":
        tasks = data.get("tasks") or []
        if any(isinstance(t, dict) and t.get("action") == "terminal" for t in tasks):
            warnings.append("Mission contains terminal execution tasks")

    return True, "", warnings


def export_cat_file(
    obj_type: str,
    obj_id: str,
    data: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
    out_path: Optional[str] = None,
) -> str:
    """Exports an object to a `.cat` file.

    If out_path is omitted, saves to the default storage directory for its type.
    Returns the absolute path to the written file.
    """
    envelope = create_cat_envelope(obj_type, obj_id, data, metadata)
    valid, err, _ = validate_cat_envelope(envelope)
    if not valid:
        raise ValueError(f"Cannot export invalid CAT object: {err}")

    if not out_path:
        safe_id = re.sub(r"[^\w\-.]", "_", obj_id)
        if obj_type == "agent":
            out_path = get_subpath("agents", f"{safe_id}.cat")
        elif obj_type == "mission":
            out_path = get_subpath("missions", f"{safe_id}.cat")
        elif obj_type == "chat":
            out_path = get_subpath("chats", f"{safe_id}.cat")
        else:
            out_path = get_subpath(f"{safe_id}.{obj_type}.cat")

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(envelope, f, indent=2, ensure_ascii=False)

    return os.path.abspath(out_path)


def write_cat_file(
    filepath: str,
    obj_type: str,
    payload: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
    obj_id: Optional[str] = None,
) -> str:
    """Convenience helper writing a validated .cat file directly to a destination path."""
    if not obj_id:
        obj_id = (metadata or {}).get("id") or (metadata or {}).get("model_id") or (metadata or {}).get("benchmark_id") or (metadata or {}).get("dataset_id") or (metadata or {}).get("experiment_id") or os.path.splitext(os.path.basename(filepath))[0]
    return export_cat_file(obj_type=obj_type, obj_id=obj_id, data=payload, metadata=metadata, out_path=filepath)


def read_cat_file(filepath: str) -> Tuple[bool, Optional[Dict[str, Any]], str, List[str]]:
    """Reads and validates a `.cat` file.

    Returns:
        (is_valid, parsed_envelope_or_None, error_msg, warnings_list)
    """
    if not os.path.isfile(filepath):
        return False, None, f"File not found: {filepath}", []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as e:
        return False, None, f"JSON parse error: {e}", []

    valid, err, warnings = validate_cat_envelope(raw)
    if not valid:
        return False, raw if isinstance(raw, dict) else None, err, warnings

    return True, raw, "", warnings


def migrate_cat_file(filepath: str) -> Tuple[bool, str]:
    """Inspects a `.cat` file and migrates older schemas to the latest version.

    Creates a timestamped backup before touching the file.
    """
    if not os.path.isfile(filepath):
        return False, f"File does not exist: {filepath}"

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return False, f"Cannot parse file: {e}"

    if not isinstance(data, dict):
        return False, "Not a valid dictionary"

    cur_ver = data.get("version", 0)
    if cur_ver == CAT_FORMAT_VERSION:
        return True, f"File already at latest schema version ({CAT_FORMAT_VERSION})"

    if cur_ver < 1:
        # Pre-v1 legacy migration
        backup_path = f"{filepath}.bak.{int(time.time())}"
        shutil.copy2(filepath, backup_path)

        data["format"] = "cat"
        data["version"] = 1
        if "type" not in data:
            data["type"] = "agent" if "system_instructions" in data or "primary_mode" in data else "project"
        if "id" not in data:
            data["id"] = data.get("name", "migrated-object").lower().replace(" ", "-")
        if "metadata" not in data:
            data["metadata"] = {
                "name": data.get("name", data["id"]),
                "migrated_from_version": cur_ver,
                "updated_at": time.time(),
            }
        if "data" not in data:
            # Everything other than top-level envelope keys moves into data
            payload = {k: v for k, v in data.items() if k not in ("format", "version", "type", "id", "metadata")}
            data["data"] = payload

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return True, f"Migrated from version {cur_ver} to {CAT_FORMAT_VERSION} (Backup: {os.path.basename(backup_path)})"

    return False, f"Unsupported version {cur_ver}"


# -----------------------------------------------------------------------------
# Storage Inspection & Metrics
# -----------------------------------------------------------------------------

def _dir_metrics(dirpath: str) -> Tuple[int, int]:
    """Returns (count_of_files, total_size_in_bytes) for a directory."""
    if not os.path.isdir(dirpath):
        return 0, 0
    count = 0
    size = 0
    for root, _, files in os.walk(dirpath):
        for f in files:
            count += 1
            try:
                size += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return count, size


def get_storage_status() -> Dict[str, Any]:
    """Provides a breakdown of CAT user file storage usage."""
    base = get_storage_dir()

    subs = {
        "agents": get_subpath("agents"),
        "missions": get_subpath("missions"),
        "chats": get_subpath("chats"),
        "memory": get_subpath("memory"),
        "integrations": get_subpath("integrations"),
        "mcp": get_subpath("mcp"),
        "cache": get_subpath("cache"),
        "backups": get_subpath("backups"),
        "settings": get_subpath("settings"),
        "benchmarks": get_subpath("benchmarks"),
        "models": get_subpath("models"),
        "experiments": get_subpath("experiments"),
        "datasets": get_subpath("datasets"),
        "reports": get_subpath("reports"),
        "artifacts": get_subpath("artifacts"),
    }

    # Also include legacy ~/.cat/chats if different from get_subpath("chats")
    legacy_chats = os.path.join(os.path.expanduser("~"), ".cat", "chats")
    legacy_chats_count, legacy_chats_size = 0, 0
    if os.path.isdir(legacy_chats) and os.path.abspath(legacy_chats) != os.path.abspath(subs["chats"]):
        legacy_chats_count, legacy_chats_size = _dir_metrics(legacy_chats)

    breakdown = {}
    total_files = 0
    total_bytes = 0

    for name, p in subs.items():
        c, s = _dir_metrics(p)
        if name == "chats":
            c += legacy_chats_count
            s += legacy_chats_size
        breakdown[name] = {
            "count": c,
            "bytes": s,
            "readable_size": format_bytes(s),
            "path": p,
        }
        total_files += c
        total_bytes += s

    return {
        "base_path": base,
        "total_files": total_files,
        "total_bytes": total_bytes,
        "readable_total": format_bytes(total_bytes),
        "breakdown": breakdown,
    }


def format_bytes(num_bytes: int) -> str:
    """Human-readable byte size."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    elif num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{num_bytes / (1024 * 1024 * 1024):.2f} GB"


# -----------------------------------------------------------------------------
# Safe Backup & Restore
# -----------------------------------------------------------------------------

def create_backup(target_path: Optional[str] = None) -> str:
    """Creates a local, safe backup archive of CAT user state.

    Excludes cache, temporary logs, and sanitizes secrets.
    Returns path to created backup archive (.zip).
    """
    base = get_storage_dir()
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    if not target_path:
        target_path = get_subpath("backups", f"cat_backup_{stamp}.zip")

    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)

    included_folders = [
        "agents", "missions", "chats", "memory", "integrations", "mcp", "settings",
        "benchmarks", "models", "experiments", "datasets", "reports"
    ]

    with zipfile.ZipFile(target_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for folder in included_folders:
            fpath = get_subpath(folder)
            if not os.path.isdir(fpath):
                continue
            for root, _, files in os.walk(fpath):
                for file in files:
                    if file.endswith((".pyc", ".tmp", ".log")):
                        continue
                    full_p = os.path.join(root, file)
                    rel_p = os.path.relpath(full_p, base)
                    zf.write(full_p, rel_p)

        # Write manifest
        manifest = {
            "format": "cat_backup",
            "version": 1,
            "created_at": time.time(),
            "timestamp": stamp,
            "source_storage_dir": base,
            "os": sys.platform,
        }
        zf.writestr("cat_backup_manifest.json", json.dumps(manifest, indent=2))

    return os.path.abspath(target_path)


def restore_backup(backup_path: str, overwrite: bool = False) -> Tuple[bool, str]:
    """Restores state from a CAT backup archive."""
    if not os.path.isfile(backup_path):
        return False, f"Backup file not found: {backup_path}"

    base = get_storage_dir()
    try:
        with zipfile.ZipFile(backup_path, "r") as zf:
            namelist = zf.namelist()
            if "cat_backup_manifest.json" not in namelist:
                return False, "Invalid CAT backup file: missing manifest"

            for member in namelist:
                if member == "cat_backup_manifest.json":
                    continue
                # Path traversal protection
                norm = os.path.normpath(member)
                if norm.startswith("..") or os.path.isabs(norm):
                    continue

                dest = os.path.join(base, norm)
                if os.path.exists(dest) and not overwrite:
                    continue
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with zf.open(member) as src, open(dest, "wb") as dst:
                    shutil.copyfileobj(src, dst)

        return True, f"Successfully restored backup into {base}"
    except Exception as e:
        return False, f"Failed to restore backup: {e}"


def clear_cache() -> int:
    """Removes files in cache/ directory. Returns number of removed files."""
    cache_dir = get_subpath("cache")
    removed = 0
    if os.path.isdir(cache_dir):
        for root, dirs, files in os.walk(cache_dir, topdown=False):
            for f in files:
                try:
                    os.remove(os.path.join(root, f))
                    removed += 1
                except OSError:
                    pass
            for d in dirs:
                try:
                    os.rmdir(os.path.join(root, d))
                except OSError:
                    pass
    return removed
