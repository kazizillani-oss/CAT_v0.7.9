"""
CAT Recovery & Rollback Engine (v1.0.0)

Unified Enterprise Recovery Engine:
- Continuous session heartbeat & crash interruption detection (integrating §15 recovery)
- Multi-file atomic change tracking & unified diff generation (integrating §14 checkpointing)
- Pre-change, pre-agent, pre-refactor, and pre-update automatic snapshots
- Transactional execution with test validation before commit
- Selective file restore, operation-level rollback, and undo/redo stacks
- Distinguishes recoverable (files, config) from irreversible operations (git push, remote APIs)
"""

from __future__ import annotations

import os
import time
import json
import uuid
import difflib
import shutil
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Tuple, Callable

from .checkpoint import CheckpointManager, Checkpoint, FileSnapshot, checkpoint_manager


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
        return asdict(self)

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


@dataclass
class ChangeRecord:
    timestamp: float
    operation_type: str  # "modify", "create", "delete", "rename", "config", "dep", "extension", "agent_patch"
    target: str
    details: str = ""
    checkpoint_id: Optional[str] = None
    recoverable: bool = True


@dataclass
class RecoveryTransaction:
    id: str
    name: str
    started_at: float
    affected_files: List[str]
    checkpoint_id: str
    status: str = "active"  # "active", "committed", "aborted", "failed"


class RecoveryEngine:
    """Unified recovery, rollback, crash-resilience, and transaction engine for CAT."""

    _instance = None

    def __init__(self, checkpoint_mgr: Optional[CheckpointManager] = None, storage_dir: Optional[str] = None):
        self.checkpoint_mgr = checkpoint_mgr or checkpoint_manager
        self.audit_log: List[ChangeRecord] = []
        self.undo_stack: List[str] = []  # checkpoint IDs
        self.redo_stack: List[str] = []  # checkpoint IDs
        self.active_transaction: Optional[RecoveryTransaction] = None
        self.storage_dir = storage_dir or os.path.join(os.path.expanduser("~"), ".cat_recovery")
        os.makedirs(self.storage_dir, exist_ok=True)
        self.audit_file = os.path.join(self.storage_dir, "audit_log.json")
        self.crash_file = os.path.join(self.storage_dir, "crash_recovery_state.json")
        self._active_crash_snapshot: Optional[RecoverySnapshot] = None
        self._load_audit_log()
        self._load_crash_state()

    @classmethod
    def get(cls) -> "RecoveryEngine":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_audit_log(self):
        if os.path.exists(self.audit_file):
            try:
                with open(self.audit_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data[-200:]:
                        self.audit_log.append(ChangeRecord(**item))
            except Exception:
                pass

    def _save_audit_log(self):
        try:
            with open(self.audit_file, "w", encoding="utf-8") as f:
                json.dump([asdict(c) for c in self.audit_log[-200:]], f, indent=2)
        except Exception:
            pass

    def _load_crash_state(self):
        # Check both modern and legacy paths
        paths = [self.crash_file, os.path.join(os.path.expanduser("~"), ".cct_recovery_state.json")]
        for p in paths:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        self._active_crash_snapshot = RecoverySnapshot.from_dict(json.load(f))
                    break
                except Exception:
                    pass

    # =====================================================================
    # Heartbeat & Interruption Recovery (§15)
    # =====================================================================

    def record_heartbeat(
        self,
        session_id: str,
        task_id: str,
        mode: str,
        task_graph_state: Optional[Dict[str, Any]] = None,
        scratchpad: str = "",
        checkpoint_id: Optional[str] = None,
    ) -> RecoverySnapshot:
        snap = RecoverySnapshot(
            session_id=session_id,
            task_id=task_id,
            mode=mode,
            task_graph_state=task_graph_state or {},
            scratchpad=scratchpad,
            active_checkpoint_id=checkpoint_id,
            completed=False,
        )
        self._active_crash_snapshot = snap
        self._save_crash_state()
        return snap

    def mark_completed(self, session_id: str):
        if self._active_crash_snapshot and self._active_crash_snapshot.session_id == session_id:
            self._active_crash_snapshot.completed = True
            self._save_crash_state()

    def get_pending_recovery(self) -> Optional[RecoverySnapshot]:
        if self._active_crash_snapshot and not self._active_crash_snapshot.completed and self._active_crash_snapshot.session_id:
            return self._active_crash_snapshot
        return None

    def clear_recovery(self):
        self._active_crash_snapshot = None
        for p in [self.crash_file, os.path.join(os.path.expanduser("~"), ".cct_recovery_state.json")]:
            if os.path.exists(p):
                try: os.remove(p)
                except Exception: pass

    def _save_crash_state(self):
        if not self._active_crash_snapshot: return
        try:
            with open(self.crash_file, "w", encoding="utf-8") as f:
                json.dump(self._active_crash_snapshot.to_dict(), f, indent=2)
        except Exception:
            pass

    # =====================================================================
    # Snapshots & Change Tracking
    # =====================================================================

    def track_change(self, op_type: str, target: str, details: str = "", checkpoint_id: Optional[str] = None, recoverable: bool = True):
        rec = ChangeRecord(
            timestamp=time.time(),
            operation_type=op_type,
            target=target,
            details=details,
            checkpoint_id=checkpoint_id,
            recoverable=recoverable,
        )
        self.audit_log.append(rec)
        self._save_audit_log()

    def snapshot_before(self, description: str, files: List[str], op_type: str = "agent_patch") -> Checkpoint:
        chk = self.checkpoint_mgr.create_checkpoint(description, files)
        self.undo_stack.append(chk.id)
        self.redo_stack.clear()
        self.track_change(op_type=op_type, target=description, details=f"{len(files)} files", checkpoint_id=chk.id, recoverable=True)
        return chk

    def snapshot_before_agent(self, agent_name: str, files: List[str]) -> Checkpoint:
        return self.snapshot_before(f"Pre-agent execution: {agent_name}", files, op_type="agent_patch")

    def snapshot_before_refactor(self, refactor_name: str, files: List[str]) -> Checkpoint:
        return self.snapshot_before(f"Pre-refactoring: {refactor_name}", files, op_type="modify")

    def snapshot_before_update(self, component_name: str, files: List[str]) -> Checkpoint:
        return self.snapshot_before(f"Pre-update: {component_name}", files, op_type="extension")

    # =====================================================================
    # Transactional Execution
    # =====================================================================

    def begin_transaction(self, name: str, files: List[str]) -> RecoveryTransaction:
        chk = self.snapshot_before(f"Transaction: {name}", files, op_type="modify")
        tx = RecoveryTransaction(
            id=f"tx_{int(time.time())}_{uuid.uuid4().hex[:4]}",
            name=name,
            started_at=time.time(),
            affected_files=files,
            checkpoint_id=chk.id,
            status="active",
        )
        self.active_transaction = tx
        return tx

    def commit_transaction(self, test_validator: Optional[Callable[[], bool]] = None) -> Tuple[bool, str]:
        if not self.active_transaction:
            return False, "No active transaction to commit."

        if test_validator:
            try:
                passed = test_validator()
                if not passed:
                    self.abort_transaction()
                    return False, "Validation tests failed. Transaction automatically aborted and rolled back."
            except Exception as e:
                self.abort_transaction()
                return False, f"Validation test threw exception: {e}. Transaction aborted."

        tx = self.active_transaction
        tx.status = "committed"
        self.track_change("commit", tx.name, f"Transaction {tx.id} committed successfully.", checkpoint_id=tx.checkpoint_id)
        self.active_transaction = None
        return True, f"Transaction {tx.id} committed successfully."

    def abort_transaction(self) -> Tuple[bool, str]:
        if not self.active_transaction:
            return False, "No active transaction to abort."

        tx = self.active_transaction
        ok, restored = self.checkpoint_mgr.rollback(tx.checkpoint_id)
        tx.status = "aborted"
        self.track_change("abort", tx.name, f"Transaction {tx.id} aborted. Restored: {len(restored)} files.", checkpoint_id=tx.checkpoint_id)
        self.active_transaction = None
        return ok, f"Transaction aborted. Rolled back {len(restored)} file(s)."

    # =====================================================================
    # Recovery & Rollback Actions
    # =====================================================================

    def preview_rollback(self, checkpoint_id: str) -> Dict[str, Any]:
        chk = self.checkpoint_mgr.checkpoints.get(checkpoint_id)
        if not chk:
            return {"error": f"Checkpoint {checkpoint_id} not found"}

        diffs = self.checkpoint_mgr.get_diff(checkpoint_id)
        return {
            "checkpoint_id": checkpoint_id,
            "description": chk.description,
            "timestamp": chk.timestamp,
            "affected_files": list(chk.snapshots.keys()),
            "diffs": diffs,
            "recoverable": True,
        }

    def rollback_operation(self, checkpoint_id: str) -> Tuple[bool, List[str]]:
        ok, files = self.checkpoint_mgr.rollback(checkpoint_id)
        if ok:
            self.track_change("rollback", f"Rollback to {checkpoint_id}", f"Restored {len(files)} files.", checkpoint_id=checkpoint_id)
        return ok, files

    def restore_file(self, checkpoint_id: str, file_path: str) -> Tuple[bool, str]:
        chk = self.checkpoint_mgr.checkpoints.get(checkpoint_id)
        if not chk:
            return False, f"Checkpoint {checkpoint_id} not found"

        norm_path = os.path.abspath(os.path.expanduser(file_path))
        snap = chk.snapshots.get(norm_path)
        if not snap:
            return False, f"File {file_path} not found in checkpoint {checkpoint_id}"

        try:
            if snap.existed:
                os.makedirs(os.path.dirname(norm_path), exist_ok=True)
                with open(norm_path, "w", encoding="utf-8") as f:
                    f.write(snap.content)
                self.track_change("restore_file", norm_path, f"Restored from {checkpoint_id}", checkpoint_id=checkpoint_id)
                return True, f"Successfully restored {os.path.basename(norm_path)}"
            else:
                if os.path.exists(norm_path):
                    os.remove(norm_path)
                return True, f"Removed newly added file {os.path.basename(norm_path)} (did not exist at checkpoint)"
        except Exception as e:
            return False, f"Failed to restore {norm_path}: {e}"

    def undo(self) -> Tuple[bool, str]:
        if not self.undo_stack:
            return False, "Nothing to undo."
        cid = self.undo_stack.pop()
        self.redo_stack.append(cid)
        ok, files = self.checkpoint_mgr.rollback(cid)
        if ok:
            return True, f"Undo successful: restored {len(files)} file(s) from {cid}."
        return False, f"Undo failed: {files}"

    def redo(self) -> Tuple[bool, str]:
        if not self.redo_stack:
            return False, "Nothing to redo."
        cid = self.redo_stack.pop()
        self.undo_stack.append(cid)
        ok, files = self.checkpoint_mgr.rollback(cid)
        return ok, f"Redo processed for checkpoint {cid}."

    def get_status(self) -> Dict[str, Any]:
        return {
            "total_checkpoints": len(self.checkpoint_mgr.checkpoints),
            "undo_available": len(self.undo_stack) > 0,
            "redo_available": len(self.redo_stack) > 0,
            "active_transaction": self.active_transaction.name if self.active_transaction else None,
            "recent_audit_events": len(self.audit_log),
            "pending_crash_recovery": self.get_pending_recovery() is not None,
        }

    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        res = []
        for chk in self.checkpoint_mgr.list_checkpoints()[:limit]:
            res.append({
                "id": chk.id,
                "description": chk.description,
                "timestamp": chk.timestamp,
                "files_count": len(chk.snapshots),
                "applied": chk.applied,
            })
        return res


recovery_engine = RecoveryEngine.get()
