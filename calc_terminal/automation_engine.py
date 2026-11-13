"""
CAT Automation Engine (v0.7.9 Complete Platform Expansion)

Scheduled tasks, event triggers, and multi-agent workflow delegation.
"""

import os
import time
import json
import uuid
import threading
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional, Callable

@dataclass
class AutomationJob:
    id: str
    name: str
    trigger_type: str  # interval, cron, event
    trigger_config: Dict[str, Any]  # {"interval_seconds": 3600} or {"event": "git_commit"}
    action_type: str  # command, agent_task, python_fn
    action_payload: str  # e.g. "/security scan" or "Run security scan"
    assigned_agent: str = "Aria"
    enabled: bool = True
    last_run: Optional[float] = None
    last_status: str = "never_run"  # success, failure, never_run
    run_count: int = 0
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AutomationEngine:
    """Manages background automations, scheduled routines, and agent delegation."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._jobs: Dict[str, AutomationJob] = {}
            cls._instance._storage_path = os.path.expanduser("~/.cat/automations.json")
            os.makedirs(os.path.dirname(cls._instance._storage_path), exist_ok=True)
            cls._instance._load_jobs()
            cls._instance._bootstrap_default_automations()
        return cls._instance

    def _load_jobs(self):
        if os.path.exists(self._storage_path):
            try:
                with open(self._storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data:
                    job = AutomationJob(**item)
                    self._jobs[job.id] = job
            except Exception:
                self._jobs = {}

    def _save_jobs(self):
        try:
            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump([j.to_dict() for j in self._jobs.values()], f, indent=2)
        except Exception:
            pass

    def _bootstrap_default_automations(self):
        """Seed default useful developer automations if none exist."""
        if not self._jobs:
            defaults = [
                AutomationJob(
                    id="auto_git_status",
                    name="Workspace Git Status Check",
                    trigger_type="interval",
                    trigger_config={"interval_seconds": 1800},
                    action_type="command",
                    action_payload="git status -s",
                    assigned_agent="Dexter",
                    enabled=True
                ),
                AutomationJob(
                    id="auto_security_scan",
                    name="Daily Dependency Security Scan",
                    trigger_type="interval",
                    trigger_config={"interval_seconds": 86400},
                    action_type="command",
                    action_payload="/security",
                    assigned_agent="Aria",
                    enabled=True
                ),
                AutomationJob(
                    id="auto_clean_cache",
                    name="CAT Browser Cache Cleanup",
                    trigger_type="interval",
                    trigger_config={"interval_seconds": 43200},
                    action_type="command",
                    action_payload="/clear",
                    assigned_agent="Echo",
                    enabled=True
                )
            ]
            for d in defaults:
                self._jobs[d.id] = d
            self._save_jobs()

    def add_job(
        self,
        name: str,
        trigger_type: str,
        trigger_config: Dict[str, Any],
        action_type: str,
        action_payload: str,
        assigned_agent: str = "Aria"
    ) -> AutomationJob:
        """Create and register a new automation job."""
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        job = AutomationJob(
            id=job_id,
            name=name,
            trigger_type=trigger_type,
            trigger_config=trigger_config,
            action_type=action_type,
            action_payload=action_payload,
            assigned_agent=assigned_agent,
            enabled=True
        )
        self._jobs[job_id] = job
        self._save_jobs()
        return job

    def remove_job(self, job_id: str) -> bool:
        if job_id in self._jobs:
            del self._jobs[job_id]
            self._save_jobs()
            return True
        return False

    def list_jobs(self) -> List[Dict[str, Any]]:
        return [j.to_dict() for j in self._jobs.values()]

    def toggle_job(self, job_id: str) -> Optional[bool]:
        job = self._jobs.get(job_id)
        if job:
            job.enabled = not job.enabled
            self._save_jobs()
            return job.enabled
        return None

    def run_job_now(self, job_id: str, executor_fn: Optional[Callable] = None) -> Dict[str, Any]:
        """Manually trigger execution of an automation job."""
        job = self._jobs.get(job_id)
        if not job:
            return {"success": False, "error": f"Job '{job_id}' not found"}

        start_t = time.time()
        job.last_run = start_t
        job.run_count += 1

        success = True
        output = ""
        try:
            if executor_fn:
                output = executor_fn(job.action_payload)
            else:
                output = f"Executed {job.action_type}: {job.action_payload}"
            job.last_status = "success"
        except Exception as e:
            success = False
            output = str(e)
            job.last_status = "failure"

        self._save_jobs()
        return {
            "success": success,
            "job_id": job.id,
            "name": job.name,
            "duration_ms": round((time.time() - start_t) * 1000, 2),
            "output": output
        }

    def delegate_task(self, task_description: str, target_kitty: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Delegate a subtask to a specialized Kitty agent."""
        delegation_id = f"del_{uuid.uuid4().hex[:8]}"
        return {
            "delegation_id": delegation_id,
            "assigned_agent": target_kitty,
            "task": task_description,
            "context": context or {},
            "status": "delegated",
            "timestamp": time.time(),
            "summary": f"Task '{task_description}' delegated to {target_kitty}."
        }


# Global singleton
automation_engine = AutomationEngine()

def get_automation_engine() -> AutomationEngine:
    return automation_engine

