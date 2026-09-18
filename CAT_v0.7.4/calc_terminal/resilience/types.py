"""
CAT — Backup Provider & Resilience System: Core Types & Enums
Author: Kazi Zillani

Defines failure categories, security levels, cost policies, task requirements,
and health state contracts for CAT's unified AI Orchestrator.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class FailureType(str, Enum):
    """Normalized taxonomy of provider and model failure modes."""
    TRANSIENT = "transient"                       # Network blip, reset, 502/503 -> retryable
    TIMEOUT = "timeout"                           # Total or idle read timeout -> retryable/failover
    RATE_LIMIT = "rate_limit"                     # 429, request cap exceeded -> immediate failover
    QUOTA_EXHAUSTED = "quota_exhausted"           # Insufficient funds/credits -> immediate failover
    AUTH_FAILURE = "auth_failure"                 # 401, 403, invalid key -> immediate failover
    MODEL_UNAVAILABLE = "model_unavailable"       # 404, not loaded, deprecated -> model fallback
    CONTEXT_TOO_LARGE = "context_too_large"       # Token overflow -> high-ctx model fallback
    TOOL_CALLING_FAILURE = "tool_calling_failure" # Invalid function-calling or parsing collapse
    CAPABILITY_MISMATCH = "capability_mismatch"   # Missing vision/tools/coding -> skip target
    PROVIDER_OUTAGE = "provider_outage"           # Host completely unreachable / 500 storm
    SAFETY_RESTRICTION = "safety_restriction"     # Refusal or safety block -> fallback
    SERVER_ERROR = "server_error"                 # Internal 500 from provider
    UNKNOWN = "unknown"


class SecurityLevel(str, Enum):
    """Configurable security modes for automatic failover."""
    STRICT = "strict"         # Only explicitly approved backups, no auto-switch without permission
    BALANCED = "balanced"     # Configured backups may be used automatically; strict privacy rules
    AUTOMATIC = "automatic"   # CAT may select any enabled compatible provider adhering to privacy


class CostPolicy(str, Enum):
    """Cost-aware fallback constraints."""
    ANY = "any"               # Any available provider
    FREE_ONLY = "free_only"   # Strictly free providers (e.g. free tiers, Ollama local)
    LOCAL_ONLY = "local_only" # Strictly zero-cost local hardware inference


@dataclass
class TaskRequirements:
    """Explicit capability requirements for a task turn."""
    vision: bool = False
    tools: bool = False
    coding: bool = False
    reasoning: bool = False
    long_context: bool = False
    min_context: int = 0
    structured_output: bool = False
    audio: bool = False
    preferred_provider: Optional[str] = None
    preferred_model: Optional[str] = None

    def matches(self, caps: Any) -> bool:
        """Check whether a ModelCapabilities object or dict satisfies this task."""
        if isinstance(caps, dict):
            if self.vision and not caps.get("vision", False):
                return False
            if self.tools and not caps.get("tools", True):
                return False
            if self.min_context and caps.get("context_window", 32000) < self.min_context:
                return False
            if self.long_context and caps.get("context_window", 32000) < 60000:
                return False
            return True

        # Assume ModelCapabilities dataclass
        if self.vision and not getattr(caps, "vision", False):
            return False
        if self.tools and not getattr(caps, "tools", True):
            return False
        ctx = getattr(caps, "context_window", 32000)
        if self.min_context and ctx < self.min_context:
            return False
        if self.long_context and ctx < 60000:
            return False
        return True


@dataclass
class ProviderHealthState:
    """Real-time observed health metrics for a provider/model endpoint."""
    provider: str
    model: str
    status: str = "disconnected"  # healthy, slow, rate_limited, offline, local, disconnected
    latency_ms: Optional[float] = None
    consecutive_failures: int = 0
    circuit_open: bool = False
    cooldown_until: float = 0.0
    last_error: str = ""
    last_success: float = 0.0
    last_checked: float = 0.0
    success_count: int = 0
    failure_count: int = 0

    @property
    def is_healthy(self) -> bool:
        import time
        if self.circuit_open and time.time() < self.cooldown_until:
            return False
        return self.status in ("healthy", "local", "disconnected", "slow")

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "status": self.status,
            "latency_ms": round(self.latency_ms, 1) if self.latency_ms is not None else None,
            "consecutive_failures": self.consecutive_failures,
            "circuit_open": self.circuit_open,
            "cooldown_until": self.cooldown_until,
            "last_error": self.last_error,
            "last_success": self.last_success,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
        }


@dataclass
class CandidateTarget:
    """A scored, capability-checked candidate provider/model for failover."""
    provider: str
    model: str
    config: dict
    entry: Optional[dict] = None
    is_backup: bool = False
    is_local: bool = False
    score: float = 0.0
    tier: int = 1  # 1 = same-provider fallback model, 2 = cross-provider backup
