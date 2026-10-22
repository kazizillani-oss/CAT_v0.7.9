"""
CAT Agents — Modular Agent and AI Bots Platform.
"""

from .agent_model import (
    AgentSpec,
    AgentResult,
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
from .builtin_agents import BUILTIN_AGENTS, get_builtin_agents, get_builtin_agent
from .registry import AgentRegistry, get_agent_registry
from .handoff import AgentHandoffPipeline
from .orchestration import AgentOrchestrationEngine

__all__ = [
    "AgentSpec",
    "AgentResult",
    "AgentRegistry",
    "get_agent_registry",
    "BUILTIN_AGENTS",
    "get_builtin_agents",
    "get_builtin_agent",
    "AgentHandoffPipeline",
    "AgentOrchestrationEngine",
    "AGENT_STATUS_IDLE",
    "AGENT_STATUS_THINKING",
    "AGENT_STATUS_USING_TOOL",
    "AGENT_STATUS_WAITING_PERMISSION",
    "AGENT_STATUS_RUNNING",
    "AGENT_STATUS_COMPLETED",
    "AGENT_STATUS_FAILED",
    "AGENT_STATUS_RATE_LIMITED",
    "AGENT_STATUS_PROVIDER_ERROR",
    "AGENT_STATUS_OFFLINE",
]
