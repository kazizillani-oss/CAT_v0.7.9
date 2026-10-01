"""
CAT Agents — Agent Specification & Structured Result Models.
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set


AGENT_STATUS_IDLE = "Idle"
AGENT_STATUS_THINKING = "Thinking"
AGENT_STATUS_USING_TOOL = "Using Tool"
AGENT_STATUS_WAITING_PERMISSION = "Waiting for Permission"
AGENT_STATUS_RUNNING = "Running"
AGENT_STATUS_COMPLETED = "Completed"
AGENT_STATUS_FAILED = "Failed"
AGENT_STATUS_RATE_LIMITED = "Rate Limited"
AGENT_STATUS_PROVIDER_ERROR = "Provider Error"
AGENT_STATUS_OFFLINE = "Offline"

ALL_AGENT_STATUSES = (
    AGENT_STATUS_IDLE,
    AGENT_STATUS_THINKING,
    AGENT_STATUS_USING_TOOL,
    AGENT_STATUS_WAITING_PERMISSION,
    AGENT_STATUS_RUNNING,
    AGENT_STATUS_COMPLETED,
    AGENT_STATUS_FAILED,
    AGENT_STATUS_RATE_LIMITED,
    AGENT_STATUS_PROVIDER_ERROR,
    AGENT_STATUS_OFFLINE,
)


@dataclass
class AgentSpec:
    id: str
    name: str
    description: str = ""
    icon: str = "🤖"
    provider: str = "default"                # "default" | provider id (e.g. "openai", "gemini", "ollama")
    model: str = ""                          # "" = provider default
    system_instructions: str = ""
    personality: str = ""
    primary_mode: str = "notebook"           # notebook | research | plan | build | debugger | agent
    allowed_modes: List[str] = field(default_factory=lambda: ["notebook", "build", "research", "plan", "debugger", "agent"])
    tools: List[str] = field(default_factory=list)  # allowed tool keys; empty = inherit mode default
    permissions: Dict[str, Any] = field(default_factory=lambda: {
        "level": "restricted",               # "ask" | "restricted" | "full"
        "read_files": True,
        "write_files": True,
        "shell_commands": False,
        "execute_python": True,
        "network": False,
        "mcp": True,
    })
    memory_scope: str = "project"            # none | session | project | workspace | persistent
    context_strategy: str = "smart"          # compact | full | sliding_window | smart
    temperature: Optional[float] = None
    backup_provider: str = "automatic"       # "automatic" | "none" | specific provider id
    workspace_scope: Optional[str] = None    # optional path binding
    tags: List[str] = field(default_factory=list)
    category: str = "custom"                 # "core" | "coding" | "research" | "system" | "custom"
    enabled: bool = True
    builtin: bool = False
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentSpec:
        # Filter only known fields
        field_names = {f.name for f in cls.__dataclass_fields__.values()}
        cleaned = {k: v for k, v in data.items() if k in field_names}
        # Defensive normalization
        if "id" not in cleaned:
            cleaned["id"] = "custom-agent"
        if "name" not in cleaned:
            cleaned["name"] = cleaned["id"].replace("-", " ").title()
        if "allowed_modes" not in cleaned or not cleaned["allowed_modes"]:
            cleaned["allowed_modes"] = ["notebook", "build", "research", "plan", "debugger", "agent"]
        if "permissions" in cleaned and isinstance(cleaned["permissions"], dict):
            p = {"level": "restricted", "read_files": True, "write_files": True, "shell_commands": False, "execute_python": True, "network": False, "mcp": True}
            p.update(cleaned["permissions"])
            cleaned["permissions"] = p
        return cls(**cleaned)


@dataclass
class AgentResult:
    agent_id: str
    status: str                              # "success" | "failure" | "paused" | "requires_input"
    summary: str = ""
    files_changed: List[str] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentResult:
        field_names = {f.name for f in cls.__dataclass_fields__.values()}
        cleaned = {k: v for k, v in data.items() if k in field_names}
        return cls(**cleaned)
