"""
CAT Lab — Dataset Management Subsystem.
Creator: Kazi Zillani (CAT Platform).

Provides local dataset registration, inspection, schema validation,
and lightweight profiling without loading entire massive files into RAM.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import shutil
import time
from typing import Any, Dict, List, Optional, Tuple

from .models import DatasetFormat, DatasetSpec
from ..storage import (
    create_cat_envelope,
    get_storage_dir,
    get_subpath,
    read_cat_file,
    write_cat_file,
)

logger = logging.getLogger("cat.lab.datasets")


class DatasetRegistry:
    """Local dataset registry for AI and machine learning tasks."""

    def __init__(self, datasets_dir: Optional[str] = None):
        self.datasets_dir = datasets_dir or get_subpath("datasets")
        os.makedirs(self.datasets_dir, exist_ok=True)
        self._datasets: Dict[str, DatasetSpec] = {}
        self._load_builtins()
        self.reload()

    def _load_builtins(self):
        """Reference sample datasets built into CAT Lab."""
        builtins = [
            DatasetSpec(
                id="cat-coding-eval-v1",
                name="CAT Python Coding Benchmark Suite",
                description="Curated Python code generation and algorithmic verification prompts.",
                version="1.0.0",
                format=DatasetFormat.JSON,
                num_samples=10,
                num_features=4,
                labels=["prompt", "test_cases", "difficulty", "category"],
                file_size_bytes=4096,
                missing_values=0,
            ),
            DatasetSpec(
                id="cat-reasoning-math-v1",
                name="CAT Reasoning & Mathematical Verification",
                description="Logical inference, step-by-step arithmetic, and constraint satisfaction.",
                version="1.0.0",
                format=DatasetFormat.JSONL,
                num_samples=15,
                num_features=3,
                labels=["problem", "solution", "verification_rule"],
                file_size_bytes=5120,
                missing_values=0,
            ),
        ]
        for d in builtins:
            self._datasets[d.id] = d

    def reload(self) -> None:
        """Loads user-registered datasets from disk (.cat format)."""
        if not os.path.isdir(self.datasets_dir):
            return
        for file in os.listdir(self.datasets_dir):
            if file.endswith((".cat", ".json")):
                full_p = os.path.join(self.datasets_dir, file)
                try:
                    valid, envelope, err, _ = read_cat_file(full_p)
                    if valid and envelope:
                        payload = envelope.get("data", {})
                        data = payload.get("dataset", payload)
                        spec = DatasetSpec.from_dict(data)
                        self._datasets[spec.id] = spec
                except Exception as e:
                    logger.warning(f"Could not load dataset file {file}: {e}")

    def add(self, spec: DatasetSpec, persist: bool = True) -> DatasetSpec:
        """Registers a dataset spec and persists its metadata."""
        self._datasets[spec.id] = spec
        if persist:
            dest = os.path.join(self.datasets_dir, f"{spec.id}.cat")
            payload = {"dataset": spec.to_dict()}
            write_cat_file(dest, obj_type="dataset", payload=payload, metadata={"dataset_id": spec.id, "name": spec.name})
        return spec

    def inspect_file(self, file_path: str, max_sample_rows: int = 100) -> DatasetSpec:
        """Inspects a dataset file on disk and computes lightweight statistics."""
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Dataset file does not exist: {file_path}")

        file_size = os.path.getsize(file_path)
        base_name = os.path.basename(file_path)
        dataset_id = base_name.split(".")[0].lower().replace(" ", "-")
        ext = os.path.splitext(file_path)[1].lower()

        fmt = DatasetFormat.CUSTOM
        num_samples = 0
        num_features = 0
        labels: List[str] = []
        missing_values = 0

        if ext == ".csv":
            fmt = DatasetFormat.CSV
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    if header:
                        labels = [h.strip() for h in header if h.strip()]
                        num_features = len(labels)
                    for idx, row in enumerate(reader):
                        num_samples += 1
                        if idx < max_sample_rows:
                            for val in row:
                                if val.strip() == "" or val.strip().lower() in ("null", "none", "nan"):
                                    missing_values += 1
            except Exception as e:
                logger.warning(f"CSV inspection error: {e}")

        elif ext == ".json":
            fmt = DatasetFormat.JSON
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        num_samples = len(data)
                        if data and isinstance(data[0], dict):
                            labels = list(data[0].keys())
                            num_features = len(labels)
                    elif isinstance(data, dict):
                        labels = list(data.keys())
                        num_features = len(labels)
                        num_samples = 1
            except Exception as e:
                logger.warning(f"JSON inspection error: {e}")

        elif ext in (".jsonl", ".txt"):
            fmt = DatasetFormat.JSONL if ext == ".jsonl" else DatasetFormat.TEXT
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    first = True
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        num_samples += 1
                        if first and ext == ".jsonl":
                            try:
                                obj = json.loads(line)
                                if isinstance(obj, dict):
                                    labels = list(obj.keys())
                                    num_features = len(labels)
                            except Exception:
                                pass
                            first = False
            except Exception as e:
                logger.warning(f"JSONL inspection error: {e}")

        spec = DatasetSpec(
            id=dataset_id,
            name=base_name,
            description=f"Auto-profiled dataset from {file_path}",
            version="1.0.0",
            format=fmt,
            file_path=os.path.abspath(file_path),
            num_samples=num_samples,
            num_features=num_features,
            labels=labels,
            file_size_bytes=file_size,
            missing_values=missing_values,
        )
        return spec

    def get(self, dataset_id: str) -> Optional[DatasetSpec]:
        """Gets dataset by ID."""
        return self._datasets.get(dataset_id)

    def list(self) -> List[DatasetSpec]:
        """Lists all registered datasets."""
        return list(self._datasets.values())

    def remove(self, dataset_id: str) -> bool:
        """Removes dataset metadata."""
        if dataset_id in self._datasets:
            del self._datasets[dataset_id]
            for ext in (".cat", ".json"):
                target = os.path.join(self.datasets_dir, f"{dataset_id}{ext}")
                if os.path.isfile(target):
                    try:
                        os.remove(target)
                    except Exception:
                        pass
            return True
        return False


# Global dataset registry singleton
_GLOBAL_DATASET_REGISTRY: Optional[DatasetRegistry] = None


def get_dataset_registry() -> DatasetRegistry:
    global _GLOBAL_DATASET_REGISTRY
    if _GLOBAL_DATASET_REGISTRY is None:
        _GLOBAL_DATASET_REGISTRY = DatasetRegistry()
    return _GLOBAL_DATASET_REGISTRY
