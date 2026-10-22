"""
CAT Artifacts — Task-Aware Artifact Management & Provenance.

Tracks files, notebooks, reports, and assets generated or modified by agents,
preserving reviewable changes and associating outputs with originating tasks.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from .. import storage

logger = logging.getLogger("cat.artifacts")

_ARTIFACTS_LOCK = threading.RLock()
_ARTIFACT_MANAGER_INSTANCE: Optional[ArtifactManager] = None


@dataclass
class ArtifactRecord:
    artifact_id: str
    task_id: str
    agent_id: str
    path: str
    filename: str
    action: str = "created"                   # "created" | "modified" | "deleted" | "exported"
    artifact_type: str = "code"               # "code" | "notebook" | "report" | "visualization" | "latex" | "data"
    sha256: str = ""
    diff_summary: str = ""
    size_bytes: int = 0
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def file_path(self) -> str:
        return self.path

    @property
    def category(self) -> str:
        return self.artifact_type

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ArtifactRecord:
        fields = {f.name for f in cls.__dataclass_fields__.values()}
        cleaned = {k: v for k, v in data.items() if k in fields}
        return cls(**cleaned)


def detect_artifact_type(file_path: str) -> str:
    """Classifies file path into standard artifact types."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".ipynb",):
        return "notebook"
    elif ext in (".tex", ".bib"):
        return "latex"
    elif ext in (".png", ".svg", ".jpg", ".jpeg", ".gif"):
        return "visualization"
    elif ext in (".md", ".txt", ".rst", ".pdf", ".html"):
        return "report"
    elif ext in (".csv", ".json", ".parquet", ".tsv", ".yaml", ".yml"):
        return "data"
    return "code"


def compute_file_sha256(file_path: str) -> str:
    """Computes SHA-256 hash of a file if it exists."""
    if not os.path.isfile(file_path):
        return ""
    try:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


class ArtifactManager:
    """Thread-safe manager for agent-generated artifacts and provenance."""

    def __init__(self, artifacts_dir: Optional[str] = None, storage_dir: Optional[str] = None):
        self.artifacts_dir = storage_dir or artifacts_dir or storage.get_subpath("artifacts")
        os.makedirs(self.artifacts_dir, exist_ok=True)
        self._manifest_file = os.path.join(self.artifacts_dir, "manifest.json")
        self._artifacts: Dict[str, ArtifactRecord] = {}
        self._task_index: Dict[str, List[str]] = {}
        self._load_manifest()

    def _load_manifest(self) -> None:
        if os.path.isfile(self._manifest_file):
            try:
                with open(self._manifest_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        rec = ArtifactRecord.from_dict(item)
                        self._artifacts[rec.artifact_id] = rec
                        self._task_index.setdefault(rec.task_id, []).append(rec.artifact_id)
            except Exception as e:
                logger.warning(f"Error loading artifacts manifest: {e}")

    def _save_manifest(self) -> None:
        try:
            records = [a.to_dict() for a in self._artifacts.values()]
            with open(self._manifest_file, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving artifacts manifest: {e}")

    def record_artifact(
        self,
        task_id: str,
        agent_id: str,
        file_path: str,
        action: str = "created",
        diff_summary: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ArtifactRecord:
        """Register or update an artifact produced by an agent task."""
        with _ARTIFACTS_LOCK:
            art_id = f"art-{uuid.uuid4().hex[:8]}"
            norm_path = os.path.normpath(file_path)
            fname = os.path.basename(norm_path)
            atype = detect_artifact_type(norm_path)
            sha = compute_file_sha256(norm_path)
            size = os.path.getsize(norm_path) if os.path.isfile(norm_path) else 0

            rec = ArtifactRecord(
                artifact_id=art_id,
                task_id=task_id or "default-task",
                agent_id=agent_id or "nova",
                path=norm_path,
                filename=fname,
                action=action,
                artifact_type=atype,
                sha256=sha,
                diff_summary=diff_summary,
                size_bytes=size,
                timestamp=time.time(),
                metadata=metadata or {},
            )
            self._artifacts[art_id] = rec
            self._task_index.setdefault(rec.task_id, []).append(art_id)
            self._save_manifest()
            return rec

    def get_artifacts_for_task(self, task_id: str) -> List[ArtifactRecord]:
        """Retrieve all artifacts associated with a specific task."""
        with _ARTIFACTS_LOCK:
            a_ids = self._task_index.get(task_id, [])
            return [self._artifacts[aid] for aid in a_ids if aid in self._artifacts]

    def get_all_artifacts(self) -> List[ArtifactRecord]:
        """Retrieve all recorded artifacts."""
        with _ARTIFACTS_LOCK:
            return sorted(self._artifacts.values(), key=lambda a: a.timestamp, reverse=True)

    def export_task_manifest(self, task_id: str, export_path: str) -> bool:
        """Export provenance manifest for a specific task."""
        arts = self.get_artifacts_for_task(task_id)
        try:
            os.makedirs(os.path.dirname(os.path.abspath(export_path)), exist_ok=True)
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump([a.to_dict() for a in arts], f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error exporting manifest for task {task_id}: {e}")
            return False


def get_artifact_manager() -> ArtifactManager:
    """Thread-safe singleton accessor."""
    global _ARTIFACT_MANAGER_INSTANCE
    if _ARTIFACT_MANAGER_INSTANCE is None:
        with _ARTIFACTS_LOCK:
            if _ARTIFACT_MANAGER_INSTANCE is None:
                _ARTIFACT_MANAGER_INSTANCE = ArtifactManager()
    return _ARTIFACT_MANAGER_INSTANCE
