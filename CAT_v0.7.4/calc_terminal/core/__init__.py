"""
CAT Core Package — re-exports core architectural modules and singletons.
"""

from __future__ import annotations

from calc_terminal.core.mode_registry import ModeRegistry, mode_registry
from calc_terminal.core.task_graph import TaskGraph, TaskNode, TaskStatus
from calc_terminal.core.verification import RealityEngine, reality_engine
from calc_terminal.core.unified_runtime import UnifiedAgentRuntime, unified_runtime
from calc_terminal.core.project_graph import ProjectGraph, project_graph, SymbolInfo
from calc_terminal.core.checkpoint import CheckpointManager, checkpoint_manager, Checkpoint
from calc_terminal.core.recovery import RecoveryEngine, recovery_engine, RecoverySnapshot
from calc_terminal.core.security_layer import SecurityLayer, security_layer, PermissionTier

from .. import input

__all__ = [
    "input",
    "ModeRegistry",
    "mode_registry",
    "TaskGraph",
    "TaskNode",
    "TaskStatus",
    "RealityEngine",
    "reality_engine",
    "UnifiedAgentRuntime",
    "unified_runtime",
    "ProjectGraph",
    "project_graph",
    "SymbolInfo",
    "CheckpointManager",
    "checkpoint_manager",
    "Checkpoint",
    "RecoveryEngine",
    "recovery_engine",
    "RecoverySnapshot",
    "SecurityLayer",
    "security_layer",
    "PermissionTier",
]
