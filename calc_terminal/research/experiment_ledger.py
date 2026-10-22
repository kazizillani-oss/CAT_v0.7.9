"""
CAT Experiment Ledger & Scientific Time Machine per §48, §50, §59, §66, §98:
- Complete experiment record (ID, question, hypothesis, dataset, parameters, code, hardware, results, figures, citations)
- Scientific Time Machine: experiment versions (EXP-104 V1, V2, V3...)
- Side-by-side experiment comparison
- Natural language query answering from actual stored provenance
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

LEDGER_STORAGE_PATH = os.path.join(os.path.expanduser("~"), ".cct_experiment_ledger.json")


@dataclass
class ExperimentVersion:
    version: int
    timestamp: float = field(default_factory=time.time)
    parameters: Dict[str, Any] = field(default_factory=dict)
    code_version: str = ""
    results: Dict[str, Any] = field(default_factory=dict)
    figures: List[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExperimentRecord:
    id: str  # e.g. EXP-101
    question: str
    hypothesis: str = ""
    dataset: str = ""
    dataset_version: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    code_version: str = ""
    environment: Dict[str, Any] = field(default_factory=dict)
    hardware: Dict[str, Any] = field(default_factory=dict)
    model: str = ""
    random_seed: Optional[int] = None
    execution_logs: List[str] = field(default_factory=list)
    results: Dict[str, Any] = field(default_factory=dict)
    figures: List[str] = field(default_factory=list)
    citations: List[str] = field(default_factory=list)
    verification_status: str = "pending"  # verified, not_verified, pending
    versions: List[ExperimentVersion] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "hypothesis": self.hypothesis,
            "dataset": self.dataset,
            "dataset_version": self.dataset_version,
            "parameters": self.parameters,
            "code_version": self.code_version,
            "environment": self.environment,
            "hardware": self.hardware,
            "model": self.model,
            "random_seed": self.random_seed,
            "execution_logs": self.execution_logs[-50:],
            "results": self.results,
            "figures": self.figures,
            "citations": self.citations,
            "verification_status": self.verification_status,
            "versions": [v.to_dict() if isinstance(v, ExperimentVersion) else v for v in self.versions],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> ExperimentRecord:
        vers = [ExperimentVersion(**v) if isinstance(v, dict) else v for v in d.get("versions", [])]
        return cls(
            id=d["id"],
            question=d["question"],
            hypothesis=d.get("hypothesis", ""),
            dataset=d.get("dataset", ""),
            dataset_version=d.get("dataset_version", ""),
            parameters=d.get("parameters", {}),
            code_version=d.get("code_version", ""),
            environment=d.get("environment", {}),
            hardware=d.get("hardware", {}),
            model=d.get("model", ""),
            random_seed=d.get("random_seed"),
            execution_logs=d.get("execution_logs", []),
            results=d.get("results", {}),
            figures=d.get("figures", []),
            citations=d.get("citations", []),
            verification_status=d.get("verification_status", "pending"),
            versions=vers,
            created_at=d.get("created_at", time.time()),
            updated_at=d.get("updated_at", time.time()),
        )


class ExperimentLedger:
    """Central store for scientific and ML experiments, versions and provenance."""

    def __init__(self, storage_path: str = LEDGER_STORAGE_PATH):
        self.storage_path = storage_path
        self._experiments: Dict[str, ExperimentRecord] = {}
        self.load()

    def record_experiment(
        self,
        question: str,
        hypothesis: str = "",
        dataset: str = "",
        dataset_version: str = "",
        parameters: Optional[Dict[str, Any]] = None,
        code_version: str = "",
        environment: Optional[Dict[str, Any]] = None,
        results: Optional[Dict[str, Any]] = None,
        model: str = "",
        hardware: Optional[Dict[str, Any]] = None,
        figures: Optional[List[str]] = None,
        citations: Optional[List[str]] = None,
        experiment_id: Optional[str] = None,
    ) -> ExperimentRecord:
        eid = experiment_id or f"EXP-{len(self._experiments) + 101}"
        exp = ExperimentRecord(
            id=eid,
            question=question,
            hypothesis=hypothesis,
            dataset=dataset,
            dataset_version=dataset_version,
            parameters=parameters or {},
            code_version=code_version,
            environment=environment or {},
            results=results or {},
            model=model,
            hardware=hardware or {},
            figures=figures or [],
            citations=citations or [],
        )
        # Add V1
        exp.versions.append(ExperimentVersion(
            version=1,
            parameters=exp.parameters,
            results=exp.results,
            figures=exp.figures,
            notes="Initial run",
        ))
        self._experiments[eid] = exp
        self.save()
        return exp

    def get_experiment(self, experiment_id: str) -> Optional[ExperimentRecord]:
        return self._experiments.get(experiment_id.upper())

    def add_version(
        self,
        experiment_id: str,
        parameters: Dict[str, Any],
        results: Dict[str, Any],
        code_version: str = "",
        figures: Optional[List[str]] = None,
        notes: str = "",
    ) -> Optional[ExperimentVersion]:
        """Scientific Time Machine: branch/version an experiment per §50."""
        exp = self.get_experiment(experiment_id)
        if not exp:
            return None
        new_v_num = len(exp.versions) + 1
        new_v = ExperimentVersion(
            version=new_v_num,
            parameters=parameters,
            code_version=code_version or exp.code_version,
            results=results,
            figures=figures or [],
            notes=notes,
        )
        exp.versions.append(new_v)
        exp.parameters = parameters
        exp.results = results
        if code_version:
            exp.code_version = code_version
        if figures:
            exp.figures.extend(figures)
        exp.updated_at = time.time()
        self.save()
        return new_v

    def compare_experiments(self, id_a: str, id_b: str) -> Dict[str, Any]:
        """Side-by-side comparison highlighting factual differences per §66."""
        a = self.get_experiment(id_a)
        b = self.get_experiment(id_b)
        if not a or not b:
            return {"error": f"One or both experiments not found ({id_a}, {id_b})"}

        # Compare parameters
        all_params = sorted(set(list(a.parameters.keys()) + list(b.parameters.keys())))
        param_diff = {}
        for p in all_params:
            va = a.parameters.get(p)
            vb = b.parameters.get(p)
            if va != vb:
                param_diff[p] = {"run_a": va, "run_b": vb}

        # Compare results
        all_res = sorted(set(list(a.results.keys()) + list(b.results.keys())))
        res_diff = {}
        for r in all_res:
            va = a.results.get(r)
            vb = b.results.get(r)
            res_diff[r] = {"run_a": va, "run_b": vb}

        return {
            "experiment_a": a.id,
            "experiment_b": b.id,
            "question_a": a.question,
            "question_b": b.question,
            "dataset_diff": {"run_a": a.dataset, "run_b": b.dataset},
            "model_diff": {"run_a": a.model, "run_b": b.model},
            "parameter_differences": param_diff,
            "result_differences": res_diff,
        }

    def compare_versions(self, experiment_id: str, v_a: int, v_b: int) -> Dict[str, Any]:
        """Compare two versions within the same experiment."""
        exp = self.get_experiment(experiment_id)
        if not exp:
            return {"error": f"Experiment not found: {experiment_id}"}
        va_obj = next((v for v in exp.versions if v.version == v_a), None)
        vb_obj = next((v for v in exp.versions if v.version == v_b), None)
        if not va_obj or not vb_obj:
            return {"error": f"Versions not found ({v_a}, {v_b})"}

        all_params = sorted(set(list(va_obj.parameters.keys()) + list(vb_obj.parameters.keys())))
        param_diff = {}
        for p in all_params:
            pa = va_obj.parameters.get(p)
            pb = vb_obj.parameters.get(p)
            if pa != pb:
                param_diff[p] = {"v1": pa, "v2": pb}

        all_res = sorted(set(list(va_obj.results.keys()) + list(vb_obj.results.keys())))
        res_diff = {}
        for r in all_res:
            ra = va_obj.results.get(r)
            rb = vb_obj.results.get(r)
            if ra != rb:
                res_diff[r] = {"v1": ra, "v2": rb}

        return {
            "experiment_id": exp.id,
            "version_a": v_a,
            "version_b": v_b,
            "parameter_diffs": param_diff,
            "result_diffs": res_diff,
        }

    def query_ledger(self, query: str) -> List[ExperimentRecord]:
        """Answer queries from actual stored experiment data per §98."""
        q = query.lower()
        results = []
        for exp in self._experiments.values():
            if "gpu" in q and (exp.hardware.get("cuda") or "gpu" in str(exp.hardware).lower()):
                results.append(exp)
            elif "failed" in q and exp.verification_status == "failed":
                results.append(exp)
            elif exp.model and exp.model.lower() in q:
                results.append(exp)
            elif exp.dataset and exp.dataset.lower() in q:
                results.append(exp)
            elif exp.id.lower() in q or exp.question.lower() in q:
                results.append(exp)
        return results

    def query_experiments(self, query: str) -> List[ExperimentRecord]:
        return self.query_ledger(query)

    def save(self):
        try:
            data = {k: exp.to_dict() for k, exp in self._experiments.items()}
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def load(self):
        if not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._experiments = {k: ExperimentRecord.from_dict(v) for k, v in data.items()}
        except Exception:
            pass


experiment_ledger = ExperimentLedger()
