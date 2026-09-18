"""
CAT — Backup Provider & Resilience System: Agent Task State
Author: Kazi Zillani

Agent state belongs to CAT, independent of any AI provider.
Preserves objective, conversation history, executed tool steps, files inspected,
files modified, shell commands run, test results, and todo list across failovers.
"""

from dataclasses import dataclass, field
import json
import time
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class AgentTaskState:
    """Provider-independent record of an in-progress agent task."""
    task_id: str = ""
    objective: str = ""
    created_at: float = field(default_factory=time.time)
    convo: List[Dict[str, Any]] = field(default_factory=list)
    steps: List[Tuple[str, dict, str, dict]] = field(default_factory=list)
    files_inspected: Set[str] = field(default_factory=set)
    files_modified: Dict[str, str] = field(default_factory=dict)
    commands_executed: List[Dict[str, Any]] = field(default_factory=list)
    tests_run: List[Dict[str, Any]] = field(default_factory=list)
    todo_list: List[Dict[str, Any]] = field(default_factory=list)
    active_provider: str = ""
    active_model: str = ""
    failover_log: List[Dict[str, Any]] = field(default_factory=list)

    def record_step(self, tool_name: str, args: dict, obs: str, change: Optional[dict] = None) -> None:
        """Record executed tool step and analyze file/command side-effects."""
        chg = dict(change or {})
        self.steps.append((tool_name, args, obs, chg))

        # Track file inspection
        if tool_name in ("read_file", "inspect_project", "archive_list", "search_workspace"):
            p = str(args.get("path") or args.get("query") or "")
            if p:
                self.files_inspected.add(p)

        # Track file mutations
        if tool_name in ("write_file", "edit_file", "create_folder", "rename_file", "delete_file"):
            p = str(args.get("path") or args.get("new_path") or "")
            if p:
                reason = str(args.get("reason") or tool_name)
                self.files_modified[p] = reason

        # Track command executions
        if tool_name in ("run_build", "run_tests", "run_shell_command"):
            cmd = str(args.get("command") or "")
            passed = "error" not in obs.lower() and "failed" not in obs.lower()
            self.commands_executed.append({
                "command": cmd,
                "tool": tool_name,
                "passed": passed,
                "summary": str(obs)[:120],
                "ts": time.time(),
            })
            if tool_name == "run_tests":
                self.tests_run.append({
                    "command": cmd,
                    "passed": passed,
                    "output_preview": str(obs)[:160],
                    "ts": time.time(),
                })

    def record_failover(self, from_provider: str, to_provider: str, reason: str = "") -> None:
        """Log provider switch during task execution."""
        rec = {
            "from": from_provider,
            "to": to_provider,
            "reason": reason,
            "steps_at_failover": len(self.steps),
            "timestamp": time.time(),
        }
        self.failover_log.append(rec)
        self.active_provider = to_provider

    def format_continuation_context(self) -> str:
        """Minimum necessary context to allow a backup provider to continue seamlessly."""
        parts = ["## RESUMED CAT AGENT TASK CONTEXT"]
        parts.append(f"Objective: {self.objective}")
        parts.append(f"Completed Steps: {len(self.steps)}")

        if self.files_modified:
            parts.append("Files modified so far:")
            for p, desc in list(self.files_modified.items())[-8:]:
                parts.append(f"  - {p} ({desc})")

        if self.tests_run:
            last_test = self.tests_run[-1]
            status = "PASSED" if last_test["passed"] else "FAILED"
            parts.append(f"Latest test status: {status} ({last_test['command']})")

        if self.steps:
            parts.append("Recent tool executions:")
            for name, args, obs, _c in self.steps[-3:]:
                arg_summary = str(args.get("path") or args.get("command") or "")
                parts.append(f"  - {name}({arg_summary}): {str(obs)[:100]}")

        parts.append("Continue the user's task from this exact state. Do NOT repeat already completed actions.")
        return "\n".join(parts)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "objective": self.objective,
            "created_at": self.created_at,
            "step_count": len(self.steps),
            "files_inspected": list(self.files_inspected),
            "files_modified": self.files_modified,
            "commands_executed": self.commands_executed,
            "tests_run": self.tests_run,
            "todo_list": self.todo_list,
            "active_provider": self.active_provider,
            "active_model": self.active_model,
            "failovers": self.failover_log,
        }
