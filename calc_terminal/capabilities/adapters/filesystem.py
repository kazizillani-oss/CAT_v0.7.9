"""
Filesystem Capability Adapters:
- filesystem.read
- filesystem.write
- filesystem.delete
- filesystem.list
"""

from __future__ import annotations

import os
import difflib
from typing import Any, Dict, Optional, Tuple

from ..schema import (
    AvailabilityStatus,
    Capability,
    CapabilityCategory,
    CapabilitySpec,
    ExecutionResult,
)


def _check_fs_health() -> Tuple[AvailabilityStatus, str]:
    return AvailabilityStatus.AVAILABLE, "Local filesystem accessible"


def _read_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    path = args.get("path", "")
    if not path:
        return ExecutionResult(success=False, error="path argument is required")
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(path):
        return ExecutionResult(success=False, error=f"File not found: {path}")
    if os.path.isdir(path):
        return ExecutionResult(success=False, error=f"Path is a directory, not a file: {path}")

    offset = int(args.get("offset", 0))
    limit = int(args.get("limit", 2000))

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        total_lines = len(lines)
        sliced = lines[offset : offset + limit]
        content = "".join(sliced)

        return ExecutionResult(
            success=True,
            output=content,
            metadata={"path": path, "total_lines": total_lines, "offset": offset, "lines_returned": len(sliced)},
        )
    except Exception as e:
        return ExecutionResult(success=False, error=f"Read error: {e}")


def _write_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    path = args.get("path", "")
    content = args.get("content", "")
    if not path:
        return ExecutionResult(success=False, error="path argument is required")
    path = os.path.abspath(os.path.expanduser(path))

    old_content = ""
    is_new = not os.path.exists(path)
    if not is_new:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                old_content = f.read()
        except Exception:
            pass

    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        diff = "".join(
            difflib.unified_diff(
                old_content.splitlines(keepends=True),
                content.splitlines(keepends=True),
                fromfile=f"a/{os.path.basename(path)}",
                tofile=f"b/{os.path.basename(path)}",
            )
        )

        return ExecutionResult(
            success=True,
            output=f"Successfully wrote {len(content)} characters to {path}",
            metadata={"path": path, "is_new": is_new, "diff": diff, "bytes_written": len(content.encode("utf-8"))},
        )
    except Exception as e:
        return ExecutionResult(success=False, error=f"Write error: {e}")


def _delete_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    path = args.get("path", "")
    if not path:
        return ExecutionResult(success=False, error="path argument is required")
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(path):
        return ExecutionResult(success=False, error=f"Path not found: {path}")

    try:
        if os.path.isdir(path):
            import shutil
            shutil.rmtree(path)
        else:
            os.remove(path)
        return ExecutionResult(success=True, output=f"Successfully deleted {path}", metadata={"path": path})
    except Exception as e:
        return ExecutionResult(success=False, error=f"Delete error: {e}")


def _list_handler(args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    path = args.get("path", ".")
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(path):
        return ExecutionResult(success=False, error=f"Directory not found: {path}")
    if not os.path.isdir(path):
        return ExecutionResult(success=False, error=f"Path is not a directory: {path}")

    max_entries = int(args.get("max_entries", 200))
    entries = []
    try:
        for root, dirs, files in os.walk(path):
            # Skip hidden and venv directories
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", "node_modules", "__pycache__")]
            for d in sorted(dirs):
                entries.append({"name": d, "type": "directory", "path": os.path.join(root, d)})
                if len(entries) >= max_entries:
                    break
            for f in sorted(files):
                entries.append({"name": f, "type": "file", "path": os.path.join(root, f)})
                if len(entries) >= max_entries:
                    break
            if len(entries) >= max_entries:
                break
        return ExecutionResult(success=True, output=entries, metadata={"path": path, "count": len(entries)})
    except Exception as e:
        return ExecutionResult(success=False, error=f"List directory error: {e}")


def register_filesystem_capabilities(bus):
    bus.register(Capability(
        spec=CapabilitySpec(
            name="filesystem.read",
            version="1.0.0",
            category=CapabilityCategory.FILESYSTEM,
            description="Read file content safely from disk.",
            input_schema={"path": "string", "offset": "integer?", "limit": "integer?"},
            output_schema={"content": "string"},
            permissions=["read_workspace"],
            documentation="Reads a UTF-8 text file from the local workspace.",
        ),
        handler=_read_handler,
        health_checker=_check_fs_health,
    ))

    bus.register(Capability(
        spec=CapabilitySpec(
            name="filesystem.write",
            version="1.0.0",
            category=CapabilityCategory.FILESYSTEM,
            description="Write or overwrite file content on disk.",
            input_schema={"path": "string", "content": "string"},
            output_schema={"status": "string"},
            permissions=["modify_files"],
            documentation="Writes content to a file, creating parent directories if needed.",
        ),
        handler=_write_handler,
        health_checker=_check_fs_health,
    ))

    bus.register(Capability(
        spec=CapabilitySpec(
            name="filesystem.delete",
            version="1.0.0",
            category=CapabilityCategory.FILESYSTEM,
            description="Delete a file or directory with permission check.",
            input_schema={"path": "string"},
            output_schema={"status": "string"},
            permissions=["delete_files"],
            documentation="Deletes a file or directory. Requires explicit user approval.",
        ),
        handler=_delete_handler,
        health_checker=_check_fs_health,
    ))

    bus.register(Capability(
        spec=CapabilitySpec(
            name="filesystem.list",
            version="1.0.0",
            category=CapabilityCategory.FILESYSTEM,
            description="List directory structure.",
            input_schema={"path": "string?", "max_entries": "integer?"},
            output_schema={"entries": "list"},
            permissions=["read_workspace"],
            documentation="Walks and returns directory contents.",
        ),
        handler=_list_handler,
        health_checker=_check_fs_health,
    ))
