"""
CAT Missions — Persistent Mission, Task, and Checkpoint Subsystem.
"""

from .models import (
    Mission,
    Task,
    Checkpoint,
    MISSION_STATUS_PENDING,
    MISSION_STATUS_RUNNING,
    MISSION_STATUS_PAUSED,
    MISSION_STATUS_COMPLETED,
    MISSION_STATUS_FAILED,
    ALL_MISSION_STATUSES,
)
from .manager import MissionManager, get_mission_manager

__all__ = [
    "Mission",
    "Task",
    "Checkpoint",
    "MissionManager",
    "get_mission_manager",
    "MISSION_STATUS_PENDING",
    "MISSION_STATUS_RUNNING",
    "MISSION_STATUS_PAUSED",
    "MISSION_STATUS_COMPLETED",
    "MISSION_STATUS_FAILED",
    "ALL_MISSION_STATUSES",
]
