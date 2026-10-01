"""
CAT Mission System — Task, Checkpoint, and Mission Models.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

MISSION_STATUS_PENDING = "pending"
MISSION_STATUS_RUNNING = "running"
MISSION_STATUS_PAUSED = "paused"
MISSION_STATUS_COMPLETED = "completed"
MISSION_STATUS_FAILED = "failed"

ALL_MISSION_STATUSES = (
    MISSION_STATUS_PENDING,
    MISSION_STATUS_RUNNING,
    MISSION_STATUS_PAUSED,
    MISSION_STATUS_COMPLETED,
    MISSION_STATUS_FAILED,
)


@dataclass
class Task:
    id: str
    title: str
    status: str = "pending"                  # pending | running | completed | failed | paused
    assigned_agent: Optional[str] = None
    tools_used: List[str] = field(default_factory=list)
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Task:
        field_names = {f.name for f in cls.__dataclass_fields__.values()}
        cleaned = {k: v for k, v in data.items() if k in field_names}
        return cls(**cleaned)


@dataclass
class Checkpoint:
    id: str
    name: str
    timestamp: float = field(default_factory=time.time)
    tasks_completed: int = 0
    active_task: Optional[str] = None
    snapshot: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Checkpoint:
        field_names = {f.name for f in cls.__dataclass_fields__.values()}
        cleaned = {k: v for k, v in data.items() if k in field_names}
        return cls(**cleaned)


@dataclass
class Mission:
    id: str
    title: str
    objective: str
    status: str = MISSION_STATUS_PENDING
    plan: List[str] = field(default_factory=list)
    tasks: List[Task] = field(default_factory=list)
    agents: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    checkpoints: List[Checkpoint] = field(default_factory=list)
    test_results: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    final_result: Optional[str] = None
    workspace_path: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["tasks"] = [t.to_dict() if isinstance(t, Task) else t for t in self.tasks]
        d["checkpoints"] = [c.to_dict() if isinstance(c, Checkpoint) else c for c in self.checkpoints]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Mission:
        d = dict(data)
        if "tasks" in d and isinstance(d["tasks"], list):
            d["tasks"] = [Task.from_dict(t) if isinstance(t, dict) else t for t in d["tasks"]]
        if "checkpoints" in d and isinstance(d["checkpoints"], list):
            d["checkpoints"] = [Checkpoint.from_dict(c) if isinstance(c, dict) else c for c in d["checkpoints"]]

        field_names = {f.name for f in cls.__dataclass_fields__.values()}
        cleaned = {k: v for k, v in d.items() if k in field_names}
        return cls(**cleaned)
