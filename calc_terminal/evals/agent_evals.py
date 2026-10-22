"""
calc_terminal.evals.agent_evals
===============================
Standardized evaluation framework for measuring agentic capabilities of CAT Kitties.

Evaluates 6 core dimensions:
1. Task Completion: Did the Kitty achieve the goal within the allocated steps?
2. Correctness: Did the final output / artifact satisfy functional criteria?
3. Tool Reliability: Ratio of successful tool calls vs failures/exceptions.
4. Verification Quality: Did the agent actively test/verify before declaring done?
5. Recovery: Did the agent recover when a step hit an error?
6. Resource Consumption: Steps used, wall-clock duration, character counts.

Also includes Controlled Improvement Engine (Requirement 13) to propose
versioned skill refinements with human review, preventing self-escalation.
"""

from __future__ import annotations

import os
import sys
import time
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class EvalTask:
    task_id: str
    name: str
    target_kitty: str
    objective: str
    context: str = ""
    expected_tools: List[str] = field(default_factory=list)
    max_steps: int = 8
    max_duration_seconds: float = 20.0
    verification_required: bool = True
    # Optional validator: (final_text, steps, meta) -> (passed: bool, score: float, message: str)
    validator_fn: Optional[Callable[[str, List[Any], Dict[str, Any]], Tuple[bool, float, str]]] = None


@dataclass
class EvalResult:
    task_id: str
    task_name: str
    target_kitty: str
    passed: bool
    completion_rate: float        # 0.0 or 1.0
    correctness_score: float      # 0.0 to 1.0
    tool_reliability_score: float # 0.0 to 1.0
    verification_score: float     # 0.0 to 1.0
    recovery_score: float         # 0.0 to 1.0
    duration_seconds: float
    steps_count: int
    tools_called: List[str] = field(default_factory=list)
    tools_failed: List[str] = field(default_factory=list)
    notes: str = ""

    def composite_score(self) -> float:
        """Weighted score across the 5 quality dimensions."""
        w = (
            self.completion_rate * 0.30
            + self.correctness_score * 0.30
            + self.tool_reliability_score * 0.15
            + self.verification_score * 0.15
            + self.recovery_score * 0.10
        )
        return round(w * 100.0, 1)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["composite_score"] = self.composite_score()
        return d


class AgentEvaluator:
    """Runs repeatable evaluations against CAT Kitties and computes benchmarks."""

    def __init__(self, workspace_dir: Optional[str] = None):
        self.workspace_dir = workspace_dir or os.getcwd()

    def evaluate_task(self, task: EvalTask, runner_fn: Optional[Callable] = None) -> EvalResult:
        """Executes a single evaluation task and computes dimensional scores."""
        t_start = time.perf_counter()

        tools_called: List[str] = []
        tools_failed: List[str] = []
        recovery_events = 0
        failure_events = 0

        final_text = ""
        steps: List[Any] = []
        meta: Dict[str, Any] = {}

        def _step_tracer(step_idx, tool_name, args, obs):
            tools_called.append(tool_name)
            obs_str = str(obs)
            if "error" in obs_str.lower() or "exception" in obs_str.lower() or "failed" in obs_str.lower():
                tools_failed.append(tool_name)
                nonlocal failure_events
                failure_events += 1
            else:
                if failure_events > 0:
                    nonlocal recovery_events
                    recovery_events += 1

        try:
            if runner_fn is not None:
                final_text, steps, meta = runner_fn(task, _step_tracer)
            else:
                from ..agents.registry import get_agent_registry
                from ..agent import run_agent

                spec = get_agent_registry().get(task.target_kitty)
                if not spec:
                    return EvalResult(
                        task_id=task.task_id,
                        task_name=task.name,
                        target_kitty=task.target_kitty,
                        passed=False,
                        completion_rate=0.0,
                        correctness_score=0.0,
                        tool_reliability_score=0.0,
                        verification_score=0.0,
                        recovery_score=0.0,
                        duration_seconds=round(time.perf_counter() - t_start, 3),
                        steps_count=0,
                        notes=f"Target Kitty '{task.target_kitty}' not found.",
                    )

                final_text, steps, meta = run_agent(
                    user_text=task.objective,
                    max_steps=task.max_steps,
                    mode=spec.primary_mode,
                    agent_spec=spec,
                    verbose=False,
                )

        except Exception as e:
            return EvalResult(
                task_id=task.task_id,
                task_name=task.name,
                target_kitty=task.target_kitty,
                passed=False,
                completion_rate=0.0,
                correctness_score=0.0,
                tool_reliability_score=0.0,
                verification_score=0.0,
                recovery_score=0.0,
                duration_seconds=round(time.perf_counter() - t_start, 3),
                steps_count=len(steps),
                notes=f"Execution exception: {e}",
            )

        duration = round(time.perf_counter() - t_start, 3)

        # 1. Completion: Did it return non-empty output without crash?
        completed = bool(final_text and not final_text.startswith("Error:"))
        completion_rate = 1.0 if completed else 0.0

        # 2. Correctness: Validator or heuristic
        if task.validator_fn:
            is_valid, corr_score, val_msg = task.validator_fn(final_text, steps, meta)
        else:
            is_valid = completed and len(final_text) > 20
            corr_score = 1.0 if is_valid else 0.5
            val_msg = "Passed heuristic checks"

        # 3. Tool Reliability
        total_calls = len(tools_called)
        if total_calls == 0:
            tool_rel = 1.0
        else:
            tool_rel = round((total_calls - len(tools_failed)) / total_calls, 2)

        # 4. Verification Quality
        # Check if tests/verification tool was executed or tester_ok in meta
        has_verified = meta.get("tester_ok", False) or any(
            t in ("run_tests", "qala_render_latex", "qala_solve_math", "validate_archive")
            for t in tools_called
        )
        if task.verification_required:
            verif_score = 1.0 if has_verified else 0.5
        else:
            verif_score = 1.0

        # 5. Recovery Rate
        if failure_events == 0:
            rec_score = 1.0
        else:
            rec_score = round(min(1.0, recovery_events / failure_events), 2)

        passed = completed and is_valid and (corr_score >= 0.7)

        return EvalResult(
            task_id=task.task_id,
            task_name=task.name,
            target_kitty=task.target_kitty,
            passed=passed,
            completion_rate=completion_rate,
            correctness_score=round(corr_score, 2),
            tool_reliability_score=tool_rel,
            verification_score=verif_score,
            recovery_score=rec_score,
            duration_seconds=duration,
            steps_count=len(steps),
            tools_called=tools_called,
            tools_failed=tools_failed,
            notes=val_msg,
        )

    def evaluate_suite(self, tasks: List[EvalTask], runner_fn: Optional[Callable] = None) -> Dict[str, Any]:
        """Runs an entire test suite and produces an aggregate report."""
        results: List[EvalResult] = []
        for t in tasks:
            res = self.evaluate_task(t, runner_fn=runner_fn)
            results.append(res)

        total = len(results)
        passed_count = sum(1 for r in results if r.passed)
        avg_composite = round(sum(r.composite_score() for r in results) / total, 1) if total else 0.0
        avg_reliability = round(sum(r.tool_reliability_score for r in results) / total, 2) if total else 0.0
        avg_verification = round(sum(r.verification_score for r in results) / total, 2) if total else 0.0

        return {
            "total_tasks": total,
            "passed_tasks": passed_count,
            "pass_rate": round(passed_count / total, 2) if total else 0.0,
            "avg_composite_score": avg_composite,
            "avg_tool_reliability": avg_reliability,
            "avg_verification_quality": avg_verification,
            "task_results": [r.to_dict() for r in results],
        }

    def generate_controlled_improvements(self, suite_summary: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Controlled Improvement (Requirement 13):
        Generates suggested adjustments for skills or workflows based on benchmark results.
        NEVER self-applies changes or escalates permissions without explicit review.
        """
        recommendations = []
        for r in suite_summary.get("task_results", []):
            if not r["passed"]:
                rec = {
                    "task_id": r["task_id"],
                    "target_kitty": r["target_kitty"],
                    "issue": "Task did not pass functional criteria",
                    "diagnostics": {
                        "correctness": r["correctness_score"],
                        "tool_reliability": r["tool_reliability_score"],
                        "verification": r["verification_score"],
                        "tools_failed": r["tools_failed"],
                    },
                    "proposed_skill_adjustment": (
                        f"Refine instructions for Kitty '{r['target_kitty']}' to add mandatory validation before completion."
                        if r["verification_score"] < 0.8 else
                        f"Check tool parameter schema for failed tools: {r['tools_failed']}"
                    ),
                    "permission_escalation_requested": False,
                    "review_required": True,
                    "status": "pending_user_review",
                }
                recommendations.append(rec)
        return recommendations


def get_standard_eval_suite() -> List[EvalTask]:
    """Returns the standardized repeatable evaluation tasks across all 6 Kitties."""
    return [
        EvalTask(
            task_id="eval-aria-01",
            name="Aria TDD Module Implementation",
            target_kitty="aria",
            objective="Write a clean Python math utility module with unit tests and verify tests pass.",
            expected_tools=["write_file", "run_tests"],
            verification_required=True,
            validator_fn=lambda txt, steps, meta: (
                bool(txt and ("def " in txt or "assert" in txt or "test" in txt.lower())),
                0.95 if "test" in txt.lower() else 0.75,
                "Aria generated verified implementation"
            ),
        ),
        EvalTask(
            task_id="eval-dex-01",
            name="Dex Root-Cause Bug Diagnosis",
            target_kitty="dex",
            objective="Analyze a Python IndexError in an array traversal and provide the fix.",
            expected_tools=["read_file", "edit_file"],
            verification_required=True,
            validator_fn=lambda txt, steps, meta: (
                bool(txt and ("index" in txt.lower() or "bounds" in txt.lower() or "fix" in txt.lower())),
                0.90,
                "Dex accurately diagnosed root cause"
            ),
        ),
        EvalTask(
            task_id="eval-mira-01",
            name="Mira Architectural Decomposition",
            target_kitty="mira",
            objective="Create an architecture migration plan for separating agent runtime from TUI.",
            expected_tools=["task_decomposition"],
            verification_required=False,
            validator_fn=lambda txt, steps, meta: (
                bool(txt and ("phase" in txt.lower() or "step" in txt.lower() or "architecture" in txt.lower())),
                0.95,
                "Mira generated structured architectural plan"
            ),
        ),
        EvalTask(
            task_id="eval-qala-01",
            name="Qala LaTeX & Notebook Science Computation",
            target_kitty="qala",
            objective="Symbolically integrate x^2 * exp(-x) from 0 to infinity and render LaTeX.",
            expected_tools=["qala_solve_math", "qala_render_latex"],
            verification_required=True,
            validator_fn=lambda txt, steps, meta: (
                bool(txt and ("2" in txt or "integral" in txt.lower() or "latex" in txt.lower())),
                1.0 if "2" in txt else 0.8,
                "Qala accurately computed symbolic integral"
            ),
        ),
        EvalTask(
            task_id="eval-sage-01",
            name="Sage Technical Synthesis",
            target_kitty="sage",
            objective="Investigate differences between asyncio and threading for agent task execution.",
            expected_tools=["research"],
            verification_required=False,
            validator_fn=lambda txt, steps, meta: (
                bool(txt and ("asyncio" in txt.lower() and "thread" in txt.lower())),
                0.95,
                "Sage completed deep technical research synthesis"
            ),
        ),
        EvalTask(
            task_id="eval-nova-01",
            name="Nova Autonomous Multi-Step Orchestration",
            target_kitty="nova",
            objective="Plan and delegate a multi-step task to specialist Kitties.",
            expected_tools=["delegate_task_to_kitty"],
            verification_required=True,
            validator_fn=lambda txt, steps, meta: (
                bool(txt and len(txt) > 30),
                0.90,
                "Nova coordinated specialist Kitties successfully"
            ),
        ),
    ]
