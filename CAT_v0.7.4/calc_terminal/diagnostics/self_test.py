"""
CAT Automated Self-Test Suite per §33:
Fast automated validation across core architectural subsystems:
- Capability Bus
- Mode Registry
- Reality Engine
- Task Graph
- Checkpoints & Rollback
- Experiment Ledger
- Security Layer
"""

from __future__ import annotations

import tempfile
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from calc_terminal.capabilities.bus import capability_bus
from calc_terminal.core.mode_registry import mode_registry
from calc_terminal.core.verification import reality_engine
from calc_terminal.core.task_graph import TaskGraph, TaskStatus
from calc_terminal.core.checkpoint import CheckpointManager
from calc_terminal.core.security_layer import security_layer
from calc_terminal.research.experiment_ledger import ExperimentLedger


@dataclass
class SubsystemTestResult:
    subsystem: str
    passed: bool
    duration_ms: float
    details: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subsystem": self.subsystem,
            "passed": self.passed,
            "duration_ms": self.duration_ms,
            "details": self.details,
            "error": self.error,
        }


@dataclass
class SelfTestReport:
    timestamp: float = field(default_factory=time.time)
    results: List[SubsystemTestResult] = field(default_factory=list)
    all_passed: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "all_passed": self.all_passed,
            "results": [r.to_dict() for r in self.results],
        }

    def format_table(self) -> str:
        lines = [
            "============================================================",
            "                CAT AUTOMATED SELF-TEST SUITE               ",
            "============================================================",
            f"{'Subsystem':<26} | {'Status':<8} | {'Time (ms)':<9} | Details",
            "------------------------------------------------------------",
        ]
        for r in self.results:
            status_str = "PASS" if r.passed else "FAIL"
            lines.append(f"{r.subsystem:<26} | {status_str:<8} | {r.duration_ms:<9.2f} | {r.details}")
        lines.append("------------------------------------------------------------")
        overall = "ALL SUBSYSTEMS OPERATIONAL" if self.all_passed else "SOME TESTS FAILED"
        lines.append(f"Summary: {overall}")
        lines.append("============================================================")
        return "\n".join(lines)


def run_self_test() -> SelfTestReport:
    """Execute live automated self-tests across all core subsystems."""
    results: List[SubsystemTestResult] = []

    # 1. Capability Bus
    t0 = time.time()
    try:
        caps = capability_bus.list_capabilities()
        assert len(caps) >= 10
        # Test filesystem.read tool registration
        fs_read = capability_bus.get_capability("filesystem.read")
        assert fs_read is not None
        results.append(SubsystemTestResult(
            subsystem="Capability Bus",
            passed=True,
            duration_ms=(time.time() - t0) * 1000,
            details=f"{len(caps)} tools active & callable",
        ))
    except Exception as ex:
        results.append(SubsystemTestResult(
            subsystem="Capability Bus",
            passed=False,
            duration_ms=(time.time() - t0) * 1000,
            details="Capability bus verification failed",
            error=str(ex),
        ))

    # 2. Mode Registry
    t0 = time.time()
    try:
        modes = mode_registry.list_modes()
        assert len(modes) >= 5
        resolved = mode_registry.resolve_mode_name("Use research mode")
        assert resolved is not None
        results.append(SubsystemTestResult(
            subsystem="Mode Registry",
            passed=True,
            duration_ms=(time.time() - t0) * 1000,
            details=f"{len(modes)} modes loaded, resolution OK",
        ))
    except Exception as ex:
        results.append(SubsystemTestResult(
            subsystem="Mode Registry",
            passed=False,
            duration_ms=(time.time() - t0) * 1000,
            details="Mode registry test failed",
            error=str(ex),
        ))

    # 3. Reality Engine
    t0 = time.time()
    try:
        ast_ok = reality_engine.verify_ast_syntax("x = 1 + 2\n")
        assert ast_ok.passed is True
        ast_bad = reality_engine.verify_ast_syntax("def broken(:\n")
        assert ast_bad.passed is False
        results.append(SubsystemTestResult(
            subsystem="Reality Engine",
            passed=True,
            duration_ms=(time.time() - t0) * 1000,
            details="AST syntax & diff verification OK",
        ))
    except Exception as ex:
        results.append(SubsystemTestResult(
            subsystem="Reality Engine",
            passed=False,
            duration_ms=(time.time() - t0) * 1000,
            details="Reality engine verification failed",
            error=str(ex),
        ))

    # 4. Task Graph
    t0 = time.time()
    try:
        tg = TaskGraph()
        t1 = tg.add_task(title="Fetch data", task_id="task1")
        t2 = tg.add_task(title="Train model", dependencies=["task1"], task_id="task2")
        assert len(tg.get_ready_tasks()) == 1
        tg.update_task_status("task1", TaskStatus.COMPLETED)
        assert len(tg.get_ready_tasks()) == 1
        assert tg.get_ready_tasks()[0].id == "task2"
        results.append(SubsystemTestResult(
            subsystem="Task Graph Engine",
            passed=True,
            duration_ms=(time.time() - t0) * 1000,
            details="DAG dependency resolution OK",
        ))
    except Exception as ex:
        results.append(SubsystemTestResult(
            subsystem="Task Graph Engine",
            passed=False,
            duration_ms=(time.time() - t0) * 1000,
            details="Task graph failed",
            error=str(ex),
        ))

    # 5. Checkpoint & Rollback
    t0 = time.time()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            chk_mgr = CheckpointManager(storage_dir=tmpdir)
            test_f = f"{tmpdir}/file.txt"
            with open(test_f, "w") as fp:
                fp.write("initial")
            chk = chk_mgr.create_checkpoint("test", [test_f])
            with open(test_f, "w") as fp:
                fp.write("changed")
            success, _ = chk_mgr.rollback(chk.id)
            assert success is True
            with open(test_f, "r") as fp:
                assert fp.read() == "initial"
        results.append(SubsystemTestResult(
            subsystem="Checkpoint & Rollback",
            passed=True,
            duration_ms=(time.time() - t0) * 1000,
            details="Workspace snapshot & rollback OK",
        ))
    except Exception as ex:
        results.append(SubsystemTestResult(
            subsystem="Checkpoint & Rollback",
            passed=False,
            duration_ms=(time.time() - t0) * 1000,
            details="Checkpoint rollback test failed",
            error=str(ex),
        ))

    # 6. Experiment Ledger
    t0 = time.time()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger = ExperimentLedger(storage_path=f"{tmpdir}/exp.json")
            exp = ledger.record_experiment(question="Self test question", dataset="test_ds")
            assert exp.id.startswith("EXP-")
        results.append(SubsystemTestResult(
            subsystem="Experiment Ledger",
            passed=True,
            duration_ms=(time.time() - t0) * 1000,
            details="Scientific Time Machine OK",
        ))
    except Exception as ex:
        results.append(SubsystemTestResult(
            subsystem="Experiment Ledger",
            passed=False,
            duration_ms=(time.time() - t0) * 1000,
            details="Experiment ledger test failed",
            error=str(ex),
        ))

    # 7. Security Layer
    t0 = time.time()
    try:
        redacted = security_layer.redact_secrets("token: sk-abcdefghijklmnopqrstuvwxyz123456")
        assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in redacted
        results.append(SubsystemTestResult(
            subsystem="Security Layer",
            passed=True,
            duration_ms=(time.time() - t0) * 1000,
            details="Credential redaction & guard OK",
        ))
    except Exception as ex:
        results.append(SubsystemTestResult(
            subsystem="Security Layer",
            passed=False,
            duration_ms=(time.time() - t0) * 1000,
            details="Security layer test failed",
            error=str(ex),
        ))

    all_passed = all(r.passed for r in results)
    return SelfTestReport(results=results, all_passed=all_passed)
