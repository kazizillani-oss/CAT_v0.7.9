"""
CAT Lab — Experiment Tracking & Queue Subsystem.
Creator: Kazi Zillani (CAT Platform).

Provides reproducible experiment tracking, environment snapshots,
checkpoints, progress tracking, and experiment queue execution.
"""

from __future__ import annotations

import copy
import datetime
import json
import logging
import os
import shutil
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

from .hardware import get_hardware_profile
from .models import ExperimentSpec, ExperimentStatus, TrainingProgress
from ..storage import (
    create_cat_envelope,
    get_storage_dir,
    get_subpath,
    read_cat_file,
    write_cat_file,
)

logger = logging.getLogger("cat.lab.experiments")


class ExperimentTracker:
    """Manages reproducible experiments, checkpoints, and execution history."""

    def __init__(self, experiments_dir: Optional[str] = None):
        self.experiments_dir = experiments_dir or get_subpath("experiments")
        os.makedirs(self.experiments_dir, exist_ok=True)
        self._experiments: Dict[str, ExperimentSpec] = {}
        self.reload()

    def reload(self) -> None:
        """Loads experiments from disk (.cat format)."""
        if not os.path.isdir(self.experiments_dir):
            return
        for file in os.listdir(self.experiments_dir):
            if file.endswith((".cat", ".json")):
                full_p = os.path.join(self.experiments_dir, file)
                try:
                    valid, envelope, err, _ = read_cat_file(full_p)
                    if valid and envelope:
                        payload = envelope.get("data", {})
                        data = payload.get("experiment", payload)
                        spec = ExperimentSpec.from_dict(data)
                        self._experiments[spec.id] = spec
                except Exception as e:
                    logger.warning(f"Could not load experiment file {file}: {e}")

    def create(
        self,
        name: str,
        model_id: str,
        dataset_id: Optional[str] = None,
        benchmark_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        description: str = "",
    ) -> ExperimentSpec:
        """Creates a new reproducible experiment with an environment snapshot."""
        exp_id = f"exp-{int(time.time())}-{uuid.uuid4().hex[:6]}"
        hw = get_hardware_profile()

        spec = ExperimentSpec(
            id=exp_id,
            name=name,
            description=description,
            model_id=model_id,
            dataset_id=dataset_id,
            benchmark_id=benchmark_id,
            status=ExperimentStatus.DRAFT,
            config=dict(config or {}),
            environment={
                "os": hw.get("os_name"),
                "python": hw.get("python_version"),
                "cat_version": hw.get("cat_version"),
                "primary_device": hw.get("primary_device"),
                "cpu": hw.get("cpu", {}).get("model"),
                "gpu": hw.get("gpu", {}).get("name"),
                "vram_gb": hw.get("gpu", {}).get("vram_total_gb"),
                "ram_gb": hw.get("ram", {}).get("total_gb"),
                "pytorch_version": hw.get("pytorch", {}).get("version"),
                "cuda_version": hw.get("cuda", {}).get("version"),
            },
        )
        self._save_experiment(spec)
        self._experiments[spec.id] = spec
        return spec

    def _save_experiment(self, spec: ExperimentSpec) -> None:
        dest = os.path.join(self.experiments_dir, f"{spec.id}.cat")
        spec.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        payload = {"experiment": spec.to_dict()}
        write_cat_file(
            dest,
            obj_type="experiment",
            payload=payload,
            metadata={"experiment_id": spec.id, "name": spec.name, "status": spec.status},
        )

    def get(self, experiment_id: str) -> Optional[ExperimentSpec]:
        """Gets experiment by ID."""
        return self._experiments.get(experiment_id)

    def list(self) -> List[ExperimentSpec]:
        """Lists all experiments."""
        return list(self._experiments.values())

    def update_progress(self, experiment_id: str, progress: TrainingProgress) -> Optional[ExperimentSpec]:
        """Updates live training progress."""
        exp = self.get(experiment_id)
        if not exp:
            return None
        exp.progress = progress
        self._save_experiment(exp)
        return exp

    def add_checkpoint(
        self,
        experiment_id: str,
        name: str,
        metrics: Dict[str, Any],
        weights_path: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Saves a milestone checkpoint with metrics and artifact reference."""
        exp = self.get(experiment_id)
        if not exp:
            return None
        cp_id = f"cp-{len(exp.checkpoints) + 1:03d}"
        cp = {
            "checkpoint_id": cp_id,
            "name": name,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "epoch": exp.progress.epoch,
            "step": exp.progress.step,
            "metrics": dict(metrics),
            "weights_path": weights_path,
        }
        exp.checkpoints.append(cp)
        self._save_experiment(exp)
        return cp

    def set_status(self, experiment_id: str, status: str) -> Optional[ExperimentSpec]:
        """Updates experiment lifecycle status."""
        exp = self.get(experiment_id)
        if not exp:
            return None
        exp.status = status
        self._save_experiment(exp)
        return exp

    def delete(self, experiment_id: str) -> bool:
        """Deletes experiment record."""
        if experiment_id in self._experiments:
            del self._experiments[experiment_id]
            for ext in (".cat", ".json"):
                target = os.path.join(self.experiments_dir, f"{experiment_id}{ext}")
                if os.path.isfile(target):
                    try:
                        os.remove(target)
                    except Exception:
                        pass
            return True
        return False


class ExperimentQueue:
    """Execution queue for scheduling multiple experiments/benchmarks."""

    def __init__(self, tracker: ExperimentTracker):
        self.tracker = tracker
        self._queue: List[str] = []

    def enqueue(self, experiment_id: str) -> bool:
        """Adds experiment to queue."""
        exp = self.tracker.get(experiment_id)
        if not exp:
            return False
        exp.status = ExperimentStatus.QUEUED
        self.tracker._save_experiment(exp)
        if experiment_id not in self._queue:
            self._queue.append(experiment_id)
        return True

    def list_queue(self) -> List[ExperimentSpec]:
        """Returns ordered list of queued experiments."""
        res = []
        for eid in self._queue:
            exp = self.tracker.get(eid)
            if exp:
                res.append(exp)
        return res

    def clear(self) -> None:
        """Clears queue."""
        self._queue.clear()


# Global tracker singleton
_GLOBAL_EXPERIMENT_TRACKER: Optional[ExperimentTracker] = None


def get_experiment_tracker() -> ExperimentTracker:
    global _GLOBAL_EXPERIMENT_TRACKER
    if _GLOBAL_EXPERIMENT_TRACKER is None:
        _GLOBAL_EXPERIMENT_TRACKER = ExperimentTracker()
    return _GLOBAL_EXPERIMENT_TRACKER
