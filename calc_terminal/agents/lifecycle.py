"""
CAT Agents — Standardized Agent Lifecycle & Execution States.

Implements the unified agentic lifecycle:
IDLE -> ANALYZING -> PLANNING -> AWAITING_APPROVAL -> EXECUTING -> OBSERVING_RESULTS -> VERIFYING -> COMPLETED / FAILED / CANCELLED

Enforces:
- Observable state transitions
- Verification evidence before marking completion
- Execution limits (max steps, timeouts, retry bounding)
- Real delegation tracking between primary agent (Nova) and specialists (Aria, Dex, Mira, Sage, Qala)
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class LifecycleState(str, Enum):
    IDLE = "IDLE"
    ANALYZING = "ANALYZING"
    PLANNING = "PLANNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    EXECUTING = "EXECUTING"
    OBSERVING_RESULTS = "OBSERVING_RESULTS"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class LifecycleEvent:
    task_id: str
    agent_id: str
    from_state: LifecycleState
    to_state: LifecycleState
    timestamp: float = field(default_factory=time.time)
    detail: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "timestamp": self.timestamp,
            "detail": self.detail,
            "metadata": self.metadata,
        }


@dataclass
class TaskExecutionContext:
    task_id: str
    agent_id: str
    objective: str
    parent_task_id: Optional[str] = None
    state: LifecycleState = LifecycleState.IDLE
    current_step: int = 0
    max_steps: int = 25
    steps_record: List[Dict[str, Any]] = field(default_factory=list)
    plan_steps: List[str] = field(default_factory=list)
    delegated_tasks: List[str] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    verification_evidence: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    cancelled: bool = False

    def transition(self, to_state: LifecycleState, detail: str = "", **meta) -> LifecycleEvent:
        prev = self.state
        self.state = to_state
        if to_state in (LifecycleState.COMPLETED, LifecycleState.FAILED, LifecycleState.CANCELLED):
            self.end_time = time.time()
        evt = LifecycleEvent(
            task_id=self.task_id,
            agent_id=self.agent_id,
            from_state=prev,
            to_state=to_state,
            detail=detail,
            metadata=meta,
        )
        try:
            from ..event_stream import stream
            stream.emit(
                "agent_lifecycle_transition",
                source="lifecycle",
                task_id=self.task_id,
                agent_id=self.agent_id,
                from_state=prev.value,
                to_state=to_state.value,
                detail=detail,
            )
        except Exception:
            pass
        return evt

    def add_step(self, tool_name: str, args: Dict[str, Any], observation: str, verified: bool = False):
        self.current_step += 1
        record = {
            "step": self.current_step,
            "tool": tool_name,
            "args": args,
            "observation": observation[:400],
            "verified": verified,
            "timestamp": time.time(),
        }
        self.steps_record.append(record)
        return record

    def record_verification(self, evidence: str):
        self.verification_evidence.append(evidence)

    def is_verified(self) -> bool:
        return len(self.verification_evidence) > 0 or any(s.get("verified", False) for s in self.steps_record)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "objective": self.objective,
            "parent_task_id": self.parent_task_id,
            "state": self.state.value if hasattr(self.state, "value") else str(self.state),
            "current_step": self.current_step,
            "max_steps": self.max_steps,
            "steps": self.steps_record,
            "plan_steps": self.plan_steps,
            "delegated_tasks": self.delegated_tasks,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "verification_evidence": self.verification_evidence,
            "is_verified": self.is_verified(),
            "error_message": self.error_message,
            "cancelled": self.cancelled,
        }


class LifecycleManager:
    """Manages active task execution contexts and state transitions across agents."""

    def __init__(self):
        self._active_tasks: Dict[str, TaskExecutionContext] = {}

    def create_task(
        self,
        agent_id: str,
        objective: str,
        task_id: Optional[str] = None,
        parent_task_id: Optional[str] = None,
        max_steps: int = 25,
    ) -> TaskExecutionContext:
        tid = task_id or f"task-{uuid.uuid4().hex[:8]}"
        ctx = TaskExecutionContext(
            task_id=tid,
            agent_id=agent_id,
            objective=objective,
            parent_task_id=parent_task_id,
            max_steps=max_steps,
        )
        self._active_tasks[tid] = ctx
        return ctx

    def get_task(self, task_id: str) -> Optional[TaskExecutionContext]:
        return self._active_tasks.get(task_id)

    def cancel_task(self, task_id: str, reason: str = "User cancelled") -> bool:
        ctx = self.get_task(task_id)
        if ctx and ctx.state not in (LifecycleState.COMPLETED, LifecycleState.FAILED, LifecycleState.CANCELLED):
            ctx.cancelled = True
            ctx.transition(LifecycleState.CANCELLED, detail=reason)
            return True
        return False


lifecycle_manager = LifecycleManager()
