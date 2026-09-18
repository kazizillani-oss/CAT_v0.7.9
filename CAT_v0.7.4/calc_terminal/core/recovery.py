"""
CAT Crash Resilience & Auto-Recovery per §15:
- Continuous persistence of running agent state, task DAG, and scratchpad
- Crash recovery detection on startup with resume or clean-rollback options
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RecoverySnapshot:
    session_id: str
    task_id: str
    mode: str
    timestamp: float = field(default_factory=time.time)
    task_graph_state: Dict[str, Any] = field(default_factory=dict)
    scratchpad: str = ""
    active_checkpoint_id: Optional[str] = None
    completed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "task_id": self.task_id,
            "mode": self.mode,
            "timestamp": self.timestamp,
            "task_graph_state": self.task_graph_state,
            "scratchpad": self.scratchpad,
            "active_checkpoint_id": self.active_checkpoint_id,
            "completed": self.completed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RecoverySnapshot:
        return cls(
            session_id=data.get("session_id", ""),
            task_id=data.get("task_id", ""),
            mode=data.get("mode", "agent"),
            timestamp=data.get("timestamp", time.time()),
            task_graph_state=data.get("task_graph_state", {}),
            scratchpad=data.get("scratchpad", ""),
            active_checkpoint_id=data.get("active_checkpoint_id"),
            completed=data.get("completed", False),
        )


class RecoveryEngine:
    """Manages crash detection, state persistence, and session resumption."""

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or os.path.join(os.path.expanduser("~"), ".cct_recovery_state.json")
        self._active_snapshot: Optional[RecoverySnapshot] = None
        self._load()

    def _load(self):
        if not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._active_snapshot = RecoverySnapshot.from_dict(data)
        except Exception:
            pass

    def record_heartbeat(
        self,
        session_id: str,
        task_id: str,
        mode: str,
        task_graph_state: Optional[Dict[str, Any]] = None,
        scratchpad: str = "",
        checkpoint_id: Optional[str] = None,
    ) -> RecoverySnapshot:
        """Persist state of in-flight execution."""
        snap = RecoverySnapshot(
            session_id=session_id,
            task_id=task_id,
            mode=mode,
            task_graph_state=task_graph_state or {},
            scratchpad=scratchpad,
            active_checkpoint_id=checkpoint_id,
            completed=False,
        )
        self._active_snapshot = snap
        self.save()
        return snap

    def mark_completed(self, session_id: str):
        """Mark session completed cleanly so recovery is not triggered."""
        if not self._active_snapshot:
            self._load()
        if self._active_snapshot and self._active_snapshot.session_id == session_id:
            self._active_snapshot.completed = True
            self.save()

    def get_pending_recovery(self) -> Optional[RecoverySnapshot]:
        """Check if an uncompleted session was interrupted/crashed."""
        if not self._active_snapshot:
            self._load()
        if self._active_snapshot and not self._active_snapshot.completed and self._active_snapshot.session_id:
            return self._active_snapshot
        return None

    def clear_recovery(self):
        """Clear recovery record."""
        self._active_snapshot = None
        if os.path.exists(self.storage_path):
            try:
                os.remove(self.storage_path)
            except Exception:
                pass

    def save(self):
        if not self._active_snapshot:
            return
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self._active_snapshot.to_dict(), f, indent=2)
        except Exception:
            pass


recovery_engine = RecoveryEngine()
