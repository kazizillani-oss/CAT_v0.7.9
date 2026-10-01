"""
CAT Integrations — Specification & Status Models.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

STATE_CONNECTED = "Connected"
STATE_DISCONNECTED = "Disconnected"
STATE_NEEDS_AUTH = "Needs Authentication"
STATE_UNAVAILABLE = "Unavailable"
STATE_ERROR = "Error"

ALL_INTEGRATION_STATES = (
    STATE_CONNECTED,
    STATE_DISCONNECTED,
    STATE_NEEDS_AUTH,
    STATE_UNAVAILABLE,
    STATE_ERROR,
)


@dataclass
class IntegrationSpec:
    id: str
    name: str
    category: str                           # "ai_providers" | "development" | "research" | "tools" | "communication"
    description: str = ""
    icon: str = "🔌"
    status: str = STATE_DISCONNECTED        # Connected | Disconnected | Needs Authentication | Unavailable | Error
    capabilities: List[str] = field(default_factory=list)
    auth_type: str = "token"                # "token" | "oauth" | "cli" | "url" | "none"
    details: str = ""
    last_checked: float = field(default_factory=time.time)
    config: Dict[str, Any] = field(default_factory=dict)
    builtin: bool = True

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Redact config values for safety
        if "config" in d and isinstance(d["config"], dict):
            d["config"] = {k: "[CONFIGURED]" for k in d["config"]}
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> IntegrationSpec:
        field_names = {f.name for f in cls.__dataclass_fields__.values()}
        cleaned = {k: v for k, v in data.items() if k in field_names}
        return cls(**cleaned)
