"""
CAT Task Graph & Background Task Engine per §9, §20:
Represents complex multi-step requests as directed acyclic task graphs.
Supports dependency resolution, retry, cancellation, pause/resume, and verification states.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


class TaskStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    COMPLETED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"
    VERIFYING = "VERIFYING"


TASK_SYMBOLS = {
    TaskStatus.QUEUED: "○",
    TaskStatus.RUNNING: "●",
    TaskStatus.SUCCEEDED: "✓",
    TaskStatus.FAILED: "✗",
    TaskStatus.CANCELLED: "⊘",
    TaskStatus.PAUSED: "⏸",
    TaskStatus.VERIFYING: "⟳",
}


@dataclass
class TaskNode:
    id: str
    title: str
    description: str = ""
    dependencies: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.QUEUED
    progress: float = 0.0  # 0.0 to 1.0
    logs: List[str] = field(default_factory=list)
    result: Any = None
    failure_reason: str = ""
    verification_state: str = "pending"  # pending, verified, not_verified
    subtasks: List[str] = field(default_factory=list)
    parent_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    duration_ms: float = 0.0
    retries_left: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "progress": self.progress,
            "logs": self.logs[-50:],
            "result": str(self.result)[:200] if self.result is not None else None,
            "failure_reason": self.failure_reason,
            "verification_state": self.verification_state,
            "subtasks": self.subtasks,
            "parent_id": self.parent_id,
            "duration_ms": self.duration_ms,
        }


class TaskGraph:
    """DAG managing structured tasks, dependencies, and execution progress."""

    def __init__(self, trace_id: Optional[str] = None):
        self.trace_id = trace_id or f"trace-{uuid.uuid4().hex[:8]}"
        self.nodes: Dict[str, TaskNode] = {}
        self.root_tasks: List[str] = []

    def add_task(
        self,
        title: str,
        description: str = "",
        dependencies: Optional[List[str]] = None,
        parent_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> str:
        tid = task_id or f"task-{uuid.uuid4().hex[:6]}"
        node = TaskNode(
            id=tid,
            title=title,
            description=description,
            dependencies=dependencies or [],
            parent_id=parent_id,
        )
        self.nodes[tid] = node
        if parent_id and parent_id in self.nodes:
            self.nodes[parent_id].subtasks.append(tid)
        elif not parent_id:
            self.root_tasks.append(tid)
        return tid

    def get_task(self, task_id: str) -> Optional[TaskNode]:
        return self.nodes.get(task_id)

    def update_status(self, task_id: str, status: TaskStatus, result: Any = None, failure_reason: str = ""):
        node = self.nodes.get(task_id)
        if not node:
            return
        node.status = status
        now = time.time()
        if status == TaskStatus.RUNNING and node.started_at is None:
            node.started_at = now
        elif status in (TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            node.finished_at = now
            if node.started_at:
                node.duration_ms = round((now - node.started_at) * 1000.0, 2)
        if result is not None:
            node.result = result
        if failure_reason:
            node.failure_reason = failure_reason

    def update_task_status(self, task_id: str, status: TaskStatus, result: Any = None, failure_reason: str = ""):
        self.update_status(task_id, status, result, failure_reason)

    def set_progress(self, task_id: str, progress: float):
        node = self.nodes.get(task_id)
        if node:
            node.progress = max(0.0, min(1.0, float(progress)))

    def log(self, task_id: str, message: str):
        node = self.nodes.get(task_id)
        if node:
            node.logs.append(f"[{time.strftime('%H:%M:%S')}] {message}")

    def get_ready_tasks(self) -> List[TaskNode]:
        """Return tasks whose dependencies are all SUCCEEDED and are currently QUEUED."""
        ready = []
        for node in self.nodes.values():
            if node.status != TaskStatus.QUEUED:
                continue
            deps_met = all(
                dep in self.nodes and self.nodes[dep].status == TaskStatus.SUCCEEDED
                for dep in node.dependencies
            )
            if deps_met:
                ready.append(node)
        return ready

    def cancel_all(self):
        for node in self.nodes.values():
            if node.status in (TaskStatus.QUEUED, TaskStatus.RUNNING, TaskStatus.PAUSED):
                node.status = TaskStatus.CANCELLED

    def is_finished(self) -> bool:
        return all(
            n.status in (TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED)
            for n in self.nodes.values()
        )

    def render_ascii_tree(self) -> str:
        """Render tree format matching §9 spec."""
        lines = ["TASK GRAPH"]

        def _render_node(tid: str, prefix: str = "", is_last: bool = True):
            node = self.nodes.get(tid)
            if not node:
                return
            connector = "└── " if is_last else "├── "
            symbol = TASK_SYMBOLS.get(node.status, "○")
            lines.append(f"{prefix}{connector}{node.title:<30} {symbol}")
            child_prefix = prefix + ("    " if is_last else "│   ")
            for i, child_id in enumerate(node.subtasks):
                _render_node(child_id, child_prefix, is_last=(i == len(node.subtasks) - 1))

        for i, root_id in enumerate(self.root_tasks):
            _render_node(root_id, "", is_last=(i == len(self.root_tasks) - 1))

        return "\n".join(lines)


class BackgroundTaskManager:
    """Manages background asynchronous tasks across the platform."""

    def __init__(self):
        self._graphs: Dict[str, TaskGraph] = {}

    def create_graph(self, title: str) -> TaskGraph:
        graph = TaskGraph()
        self._graphs[graph.trace_id] = graph
        return graph

    def get_graph(self, trace_id: str) -> Optional[TaskGraph]:
        return self._graphs.get(trace_id)


task_manager = BackgroundTaskManager()
