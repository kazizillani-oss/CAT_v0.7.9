"""
CAT Checkpoint & Rollback System per §14:
- Automated snapshot of targeted files before agent modifications
- Precise git-style unified diff computation
- One-click safe rollback restoring previous workspace states
"""

from __future__ import annotations

import difflib
import json
import os
import shutil
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class FileSnapshot:
    path: str
    content: str
    existed: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "content": self.content,
            "existed": self.existed,
        }


@dataclass
class Checkpoint:
    id: str
    description: str
    timestamp: float = field(default_factory=time.time)
    snapshots: Dict[str, FileSnapshot] = field(default_factory=dict)
    applied: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "timestamp": self.timestamp,
            "files": list(self.snapshots.keys()),
            "applied": self.applied,
        }


class CheckpointManager:
    """Manages workspace snapshots, diffs, and rollbacks."""

    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = storage_dir or os.path.join(os.path.expanduser("~"), ".cct_checkpoints")
        self.checkpoints: Dict[str, Checkpoint] = {}
        os.makedirs(self.storage_dir, exist_ok=True)

    def create_checkpoint(self, description: str, files: List[str]) -> Checkpoint:
        """Capture pre-modification state of specified files."""
        cid = f"chk_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        snapshots = {}
        for f in files:
            norm = os.path.abspath(os.path.expanduser(f))
            if os.path.exists(norm) and os.path.isfile(norm):
                try:
                    with open(norm, "r", encoding="utf-8", errors="ignore") as fp:
                        content = fp.read()
                    snapshots[norm] = FileSnapshot(path=norm, content=content, existed=True)
                except Exception:
                    pass
            else:
                snapshots[norm] = FileSnapshot(path=norm, content="", existed=False)

        chk = Checkpoint(id=cid, description=description, snapshots=snapshots)
        self.checkpoints[cid] = chk
        self._persist_checkpoint(chk)
        return chk

    def get_diff(self, checkpoint_id: str) -> Dict[str, str]:
        """Compute unified diff for each file in checkpoint against current workspace."""
        chk = self.checkpoints.get(checkpoint_id)
        if not chk:
            return {}

        diffs = {}
        for path, snap in chk.snapshots.items():
            orig_lines = snap.content.splitlines(keepends=True) if snap.existed else []
            curr_lines = []
            if os.path.exists(path) and os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        curr_lines = f.readlines()
                except Exception:
                    pass

            diff = list(
                difflib.unified_diff(
                    orig_lines,
                    curr_lines,
                    fromfile=f"a/{os.path.basename(path)} (checkpoint)",
                    tofile=f"b/{os.path.basename(path)} (current)",
                )
            )
            if diff:
                diffs[path] = "".join(diff)

        return diffs

    def rollback(self, checkpoint_id: str) -> Tuple[bool, List[str]]:
        """Restore workspace files to their exact checkpoint state."""
        chk = self.checkpoints.get(checkpoint_id)
        if not chk:
            return False, ["Checkpoint not found"]

        restored_files = []
        errors = []
        for path, snap in chk.snapshots.items():
            try:
                if snap.existed:
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(snap.content)
                    restored_files.append(path)
                else:
                    # File was newly created after checkpoint, so remove it
                    if os.path.exists(path):
                        os.remove(path)
                        restored_files.append(f"Deleted {path}")
            except Exception as ex:
                errors.append(f"Failed to restore {path}: {ex}")

        chk.applied = False
        return len(errors) == 0, restored_files

    def list_checkpoints(self) -> List[Checkpoint]:
        return sorted(self.checkpoints.values(), key=lambda c: c.timestamp, reverse=True)

    def _persist_checkpoint(self, chk: Checkpoint):
        try:
            path = os.path.join(self.storage_dir, f"{chk.id}.json")
            data = {
                "id": chk.id,
                "description": chk.description,
                "timestamp": chk.timestamp,
                "applied": chk.applied,
                "snapshots": {p: s.to_dict() for p, s in chk.snapshots.items()},
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass


checkpoint_manager = CheckpointManager()
