"""
CAT Missions — Mission Lifecycle & Persistence Manager.

Persists missions to ~/.cat/missions/ as native `.cat` files, manages checkpoints,
and enables pausing, resuming, and exporting multi-agent missions.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

from .models import (
    Mission,
    Task,
    Checkpoint,
    MISSION_STATUS_PENDING,
    MISSION_STATUS_RUNNING,
    MISSION_STATUS_PAUSED,
    MISSION_STATUS_COMPLETED,
    MISSION_STATUS_FAILED,
)
from .. import storage
from .. import activity as act_mod

logger = logging.getLogger("cat.missions.manager")

_MISSION_LOCK = threading.RLock()
_INSTANCE: Optional[MissionManager] = None


class MissionManager:
    """Thread-safe manager for CAT missions."""

    def __init__(self, missions_dir: Optional[str] = None):
        self.missions_dir = missions_dir or storage.get_subpath("missions")
        self._missions: Dict[str, Mission] = {}
        self._loaded = False
        os.makedirs(self.missions_dir, exist_ok=True)

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with _MISSION_LOCK:
            if self._loaded:
                return
            self._load_missions()
            self._loaded = True

    def _load_missions(self) -> None:
        if not os.path.isdir(self.missions_dir):
            return

        for fname in os.listdir(self.missions_dir):
            fpath = os.path.join(self.missions_dir, fname)
            if not os.path.isfile(fpath):
                continue

            try:
                if fname.endswith(".cat") or fname.endswith(".mission.cat"):
                    valid, envelope, _, _ = storage.read_cat_file(fpath)
                    if valid and envelope and envelope.get("type") == "mission":
                        data = envelope.get("data", {})
                        if "id" not in data:
                            data["id"] = envelope.get("id")
                        mission = Mission.from_dict(data)
                        self._missions[mission.id] = mission
                elif fname.endswith(".json"):
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict) and "id" in data:
                        mission = Mission.from_dict(data)
                        self._missions[mission.id] = mission
            except Exception as e:
                logger.warning(f"Error loading mission file {fname}: {e}")

    def save_mission(self, mission: Mission) -> str:
        """Persists mission to a `.cat` file."""
        mission.updated_at = time.time()
        safe_id = re.sub(r"[^\w\-.]", "_", mission.id)
        out_path = os.path.join(self.missions_dir, f"{safe_id}.cat")
        storage.export_cat_file(
            obj_type="mission",
            obj_id=mission.id,
            data=mission.to_dict(),
            metadata={"name": mission.title, "description": mission.objective},
            out_path=out_path,
        )
        return out_path

    def create(
        self,
        title: str,
        objective: str,
        agents: Optional[List[str]] = None,
        workspace_path: Optional[str] = None,
        plan: Optional[List[str]] = None,
    ) -> Mission:
        """Creates and stores a new mission."""
        self._ensure_loaded()
        with _MISSION_LOCK:
            mission_id = f"mission-{int(time.time())}-{uuid.uuid4().hex[:6]}"
            mission = Mission(
                id=mission_id,
                title=title,
                objective=objective,
                status=MISSION_STATUS_PENDING,
                agents=agents or ["cat-planner", "cat-coder", "cat-tester", "cat-reviewer"],
                workspace_path=workspace_path or os.getcwd(),
                plan=plan or [],
            )

            # Generate initial plan task list if provided
            if plan:
                for idx, step in enumerate(plan):
                    mission.tasks.append(
                        Task(
                            id=f"task-{idx+1}",
                            title=step,
                            status="pending",
                        )
                    )

            # Create initial checkpoint
            cp = Checkpoint(
                id="cp-0",
                name="Initial Objective Defined",
                tasks_completed=0,
                snapshot={"objective": objective},
            )
            mission.checkpoints.append(cp)

            self._missions[mission.id] = mission
            self.save_mission(mission)

            act_mod.publish(
                type="system",
                action="mission",
                status="completed",
                title=f"Created Mission: {title}",
                details=f"ID: {mission_id} | Objective: {objective[:80]}",
            )
            return mission

    def get(self, mission_id: str) -> Optional[Mission]:
        self._ensure_loaded()
        with _MISSION_LOCK:
            return self._missions.get(mission_id)

    def list(self, status: Optional[str] = None) -> List[Mission]:
        self._ensure_loaded()
        with _MISSION_LOCK:
            missions = list(self._missions.values())
            if status:
                missions = [m for m in missions if m.status == status]
            missions.sort(key=lambda m: m.created_at, reverse=True)
            return missions

    def pause(self, mission_id: str) -> bool:
        self._ensure_loaded()
        with _MISSION_LOCK:
            m = self.get(mission_id)
            if not m:
                return False
            m.status = MISSION_STATUS_PAUSED
            self.add_checkpoint(mission_id, f"Paused at {time.strftime('%H:%M:%S')}")
            self.save_mission(m)

            act_mod.publish(
                type="system",
                action="mission",
                status="waiting",
                title=f"Mission Paused: {m.title}",
                details=f"Status: paused",
            )
            return True

    def resume(self, mission_id: str) -> bool:
        self._ensure_loaded()
        with _MISSION_LOCK:
            m = self.get(mission_id)
            if not m:
                return False
            m.status = MISSION_STATUS_RUNNING
            self.add_checkpoint(mission_id, f"Resumed at {time.strftime('%H:%M:%S')}")
            self.save_mission(m)

            act_mod.publish(
                type="system",
                action="mission",
                status="running",
                title=f"Mission Resumed: {m.title}",
                details=f"Status: running",
            )
            return True

    def complete(self, mission_id: str, final_result: str = "") -> bool:
        self._ensure_loaded()
        with _MISSION_LOCK:
            m = self.get(mission_id)
            if not m:
                return False
            m.status = MISSION_STATUS_COMPLETED
            m.final_result = final_result or "Mission completed successfully."
            self.add_checkpoint(mission_id, "Mission Complete", snapshot={"final_result": m.final_result})
            self.save_mission(m)

            act_mod.publish(
                type="system",
                action="mission",
                status="completed",
                title=f"Mission Completed: {m.title}",
                details=m.final_result[:100],
            )
            return True

    def delete(self, mission_id: str) -> bool:
        self._ensure_loaded()
        with _MISSION_LOCK:
            if mission_id in self._missions:
                del self._missions[mission_id]
                safe_id = re.sub(r"[^\w\-.]", "_", mission_id)
                for ext in (".cat", ".json"):
                    fpath = os.path.join(self.missions_dir, f"{safe_id}{ext}")
                    if os.path.isfile(fpath):
                        try:
                            os.remove(fpath)
                        except OSError:
                            pass
                return True
            return False

    def add_checkpoint(self, mission_id: str, name: str, snapshot: Optional[Dict[str, Any]] = None) -> Optional[Checkpoint]:
        self._ensure_loaded()
        with _MISSION_LOCK:
            m = self.get(mission_id)
            if not m:
                return None
            completed_count = sum(1 for t in m.tasks if t.status == "completed")
            active_task = next((t.title for t in m.tasks if t.status == "running"), None)
            cp = Checkpoint(
                id=f"cp-{len(m.checkpoints)+1}",
                name=name,
                tasks_completed=completed_count,
                active_task=active_task,
                snapshot=snapshot or {},
            )
            m.checkpoints.append(cp)
            self.save_mission(m)
            return cp

    def export_mission(self, mission_id: str, filepath: Optional[str] = None) -> str:
        m = self.get(mission_id)
        if not m:
            raise ValueError(f"Mission '{mission_id}' not found.")

        if not filepath:
            safe_id = re.sub(r"[^\w\-.]", "_", m.id)
            filepath = os.path.join(os.getcwd(), f"{safe_id}.cat")

        return storage.export_cat_file(
            obj_type="mission",
            obj_id=m.id,
            data=m.to_dict(),
            metadata={"name": m.title, "description": m.objective},
            out_path=filepath,
        )

    def import_mission(self, filepath_or_content: Union[str, dict], force: bool = False) -> Mission:
        if isinstance(filepath_or_content, dict):
            envelope = filepath_or_content
        else:
            valid, envelope, _, _ = storage.read_cat_file(filepath_or_content)
            if not valid or not envelope:
                with open(filepath_or_content, "r", encoding="utf-8") as f:
                    envelope = json.load(f)

        if envelope.get("format") == "cat" and envelope.get("type") == "mission":
            data = envelope.get("data", {})
        else:
            data = envelope

        mission = Mission.from_dict(data)
        existing = self.get(mission.id)
        if existing and not force:
            mission.id = f"{mission.id}-imported-{int(time.time())}"
            mission.title = f"{mission.title} (Imported)"

        self._missions[mission.id] = mission
        self.save_mission(mission)
        return mission


def get_mission_manager() -> MissionManager:
    global _INSTANCE
    if _INSTANCE is None:
        with _MISSION_LOCK:
            if _INSTANCE is None:
                _INSTANCE = MissionManager()
    return _INSTANCE
