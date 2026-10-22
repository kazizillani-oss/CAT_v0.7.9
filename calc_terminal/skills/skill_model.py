"""
CAT Skills — Reusable, Versioned Skill Specifications.

Skills encapsulate reusable workflows, domain instructions, required tool sets,
and permission scopes that can be assigned to both canonical and custom Kitties.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class SkillDefinition:
    id: str
    name: str
    version: str = "1.0.0"
    description: str = ""
    category: str = "general"                 # "coding" | "testing" | "science" | "planning" | "research" | "devops"
    required_tools: List[str] = field(default_factory=list)
    permission_scope: Dict[str, Any] = field(default_factory=lambda: {
        "read_files": True,
        "write_files": False,
        "shell_commands": False,
        "execute_python": False,
        "network": False,
    })
    instructions: str = ""                    # Specialized instructions injected into agent system prompt
    parameters: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    enabled: bool = True
    builtin: bool = False
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def __init__(
        self,
        id: str,
        name: str,
        version: str = "1.0.0",
        description: str = "",
        category: str = "general",
        required_tools: Optional[List[str]] = None,
        permission_scope: Optional[Dict[str, Any]] = None,
        instructions: str = "",
        prompt_instructions: str = "",
        parameters: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        permissions: Optional[Dict[str, Any]] = None,
        enabled: bool = True,
        builtin: bool = False,
        created_at: Optional[float] = None,
        updated_at: Optional[float] = None,
    ):
        if not re.match(r"^\d+\.\d+\.\d+", str(version)):
            raise ValueError(f"Invalid semantic version '{version}'. Must follow SemVer (e.g. 1.0.0).")

        self.id = str(id)
        self.name = str(name)
        self.version = str(version)
        self.description = str(description)
        self.category = str(category)
        self.required_tools = list(required_tools or [])
        self.permission_scope = dict(permission_scope or permissions or {
            "read_files": True,
            "write_files": False,
            "shell_commands": False,
            "execute_python": False,
            "network": False,
        })
        self.instructions = instructions or prompt_instructions or ""
        self.parameters = dict(parameters or {})
        self.tags = list(tags or [])
        self.enabled = bool(enabled)
        self.builtin = bool(builtin)
        now = time.time()
        self.created_at = created_at if created_at is not None else now
        self.updated_at = updated_at if updated_at is not None else now

    @property
    def prompt_instructions(self) -> str:
        return self.instructions

    def is_enabled(self) -> bool:
        return self.enabled

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "category": self.category,
            "required_tools": self.required_tools,
            "permission_scope": self.permission_scope,
            "instructions": self.instructions,
            "parameters": self.parameters,
            "tags": self.tags,
            "enabled": self.enabled,
            "builtin": self.builtin,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SkillDefinition:
        cleaned = dict(data)
        if "id" not in cleaned or not cleaned["id"]:
            cleaned["id"] = "custom-skill"
        if "name" not in cleaned or not cleaned["name"]:
            cleaned["name"] = cleaned["id"].replace("-", " ").title()
        return cls(**cleaned)
