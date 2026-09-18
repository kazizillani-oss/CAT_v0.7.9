"""
CAT — Backup Provider & Resilience System
Creator: Kazi Zillani

Provides an intelligent, provider-independent failover and resilience layer
across all CAT AI workflows (chat, agent, coding, tools, browser, background tasks).
"""

from .agent_state import AgentTaskState
from .capability_matcher import CapabilityMatcher, get_capability_matcher
from .circuit_breaker import CircuitBreaker, CircuitBreakerState, get_circuit_breaker
from .failover_engine import FailoverEngine, get_failover_engine
from .health_monitor import HealthMonitor, get_health_monitor, sanitize_error
from .ollama_adapter import OllamaAdapter, get_ollama_adapter
from .orchestrator import AIOrchestrator, get_orchestrator
from .types import (
    CandidateTarget,
    CostPolicy,
    FailureType,
    ProviderHealthState,
    SecurityLevel,
    TaskRequirements,
)

__all__ = [
    "AIOrchestrator",
    "get_orchestrator",
    "HealthMonitor",
    "get_health_monitor",
    "CircuitBreaker",
    "CircuitBreakerState",
    "get_circuit_breaker",
    "CapabilityMatcher",
    "get_capability_matcher",
    "FailoverEngine",
    "get_failover_engine",
    "OllamaAdapter",
    "get_ollama_adapter",
    "AgentTaskState",
    "FailureType",
    "SecurityLevel",
    "CostPolicy",
    "TaskRequirements",
    "ProviderHealthState",
    "CandidateTarget",
    "sanitize_error",
]
