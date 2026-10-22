"""
CAT Task Scheduler & 24/7 Background Automation Engine.

Implements persistent, controllable background and scheduled agent workflows:
- Persistent task queue saved in user storage
- Scheduled intervals & one-shot triggers
- Concurrency bounding and per-task retry limits
- Pause, resume, cancel, and status inspections
- Non-simulated status reporting: never claims an agent is working when idle
"""

from __future__ import annotations

import copy
import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .. import storage

logger = logging.getLogger("cat.tasks.scheduler")


class TaskStatus(str, Enum):
    IDLE = "idle"
    WAITING = "waiting"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScheduledTask:
    task_id: str
    name: str
    agent_id: str
    objective: str
    schedule_type: str = "one_shot"         # "one_shot" | "interval" | "cron"
    interval_seconds: Optional[int] = None   # for interval jobs
    next_run_time: float = field(default_factory=time.time)
    last_run_time: Optional[float] = None
    status: TaskStatus = TaskStatus.IDLE
    max_retries: int = 3
    retry_count: int = 0
    timeout_seconds: int = 60
    enabled: bool = True
    last_result: Optional[str] = None
    last_error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ScheduledTask:
        cleaned = dict(data)
        if "status" in cleaned:
            cleaned["status"] = TaskStatus(cleaned["status"])
        return cls(**cleaned)


class TaskScheduler:
    """Persistent, thread-safe background workflow scheduler."""

    def __init__(self, state_file: Optional[str] = None, max_concurrency: int = 3):
        self.state_file = state_file or os.path.join(storage.get_subpath("tasks"), "scheduler_state.json")
        self.max_concurrency = max_concurrency
        self._tasks: Dict[str, ScheduledTask] = {}
        self._lock = threading.RLock()
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False
        self._active_workers: int = 0
        self._load_state()

    def _load_state(self) -> None:
        if os.path.isfile(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for t_dict in data.get("tasks", []):
                    task = ScheduledTask.from_dict(t_dict)
                    # Reset running tasks to idle on startup
                    if task.status == TaskStatus.RUNNING:
                        task.status = TaskStatus.IDLE
                    self._tasks[task.task_id] = task
            except Exception as e:
                logger.warning(f"Failed to load scheduler state: {e}")

    def _persist_state(self) -> None:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.state_file)), exist_ok=True)
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump({"tasks": [t.to_dict() for t in self._tasks.values()]}, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to persist scheduler state: {e}")

    def add_task(
        self,
        name: str,
        agent_id: str,
        objective: str,
        schedule_type: str = "one_shot",
        interval_seconds: Optional[int] = None,
        delay_seconds: int = 0,
        timeout_seconds: int = 60,
    ) -> ScheduledTask:
        """Registers a new scheduled or background task."""
        tid = f"sched-{uuid.uuid4().hex[:8]}"
        task = ScheduledTask(
            task_id=tid,
            name=name,
            agent_id=agent_id,
            objective=objective,
            schedule_type=schedule_type,
            interval_seconds=interval_seconds,
            next_run_time=time.time() + delay_seconds,
            timeout_seconds=timeout_seconds,
            status=TaskStatus.WAITING if delay_seconds > 0 else TaskStatus.IDLE,
        )
        with self._lock:
            self._tasks[tid] = task
            self._persist_state()
        return task

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        with self._lock:
            return self._tasks.get(task_id)

    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[ScheduledTask]:
        with self._lock:
            tasks = list(self._tasks.values())
            if status:
                tasks = [t for t in tasks if t.status == status]
            return tasks

    def pause_task(self, task_id: str) -> bool:
        with self._lock:
            t = self.get_task(task_id)
            if t and t.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
                t.status = TaskStatus.PAUSED
                self._persist_state()
                return True
        return False

    def resume_task(self, task_id: str) -> bool:
        with self._lock:
            t = self.get_task(task_id)
            if t and t.status == TaskStatus.PAUSED:
                t.status = TaskStatus.IDLE
                t.next_run_time = time.time()
                self._persist_state()
                return True
        return False

    def cancel_task(self, task_id: str) -> bool:
        with self._lock:
            t = self.get_task(task_id)
            if t:
                t.status = TaskStatus.CANCELLED
                t.enabled = False
                self._persist_state()
                return True
        return False

    def delete_task(self, task_id: str) -> bool:
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                self._persist_state()
                return True
        return False

    def execute_task_now(self, task_id: str) -> Dict[str, Any]:
        """Synchronously triggers task execution."""
        task = self.get_task(task_id)
        if not task:
            return {"error": f"Task '{task_id}' not found."}

        with self._lock:
            task.status = TaskStatus.RUNNING
            task.last_run_time = time.time()
            self._persist_state()

        try:
            from ..agent import run_agent
            from ..agents.registry import get_agent_registry
            reg = get_agent_registry()
            spec = reg.get(task.agent_id)

            res_text, steps, meta = run_agent(
                user_text=task.objective,
                max_steps=15,
                mode=spec.primary_mode if spec else "agent",
                agent_spec=spec,
                verbose=False,
            )
            with self._lock:
                task.last_result = res_text[:500]
                task.last_error = None
                if task.schedule_type == "interval" and task.interval_seconds:
                    task.status = TaskStatus.WAITING
                    task.next_run_time = time.time() + task.interval_seconds
                else:
                    task.status = TaskStatus.COMPLETED
                self._persist_state()
            return {"status": "success", "result": res_text, "steps_count": len(steps)}
        except Exception as e:
            with self._lock:
                task.retry_count += 1
                task.last_error = str(e)
                if task.retry_count >= task.max_retries:
                    task.status = TaskStatus.FAILED
                else:
                    task.status = TaskStatus.WAITING
                    task.next_run_time = time.time() + 10
                self._persist_state()
            return {"status": "failed", "error": str(e)}

    def start_background_loop(self) -> None:
        """Starts the background worker thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._worker_thread = threading.Thread(target=self._loop, daemon=True, name="cat-scheduler")
            self._worker_thread.start()

    def stop_background_loop(self) -> None:
        self._running = False

    def _loop(self) -> None:
        while self._running:
            now = time.time()
            to_run = []
            with self._lock:
                for t in self._tasks.values():
                    if t.enabled and t.status in (TaskStatus.IDLE, TaskStatus.WAITING) and t.next_run_time <= now:
                        to_run.append(t.task_id)

            for tid in to_run:
                if not self._running:
                    break
                if self._active_workers < self.max_concurrency:
                    self._active_workers += 1
                    threading.Thread(target=self._run_worker, args=(tid,), daemon=True).start()

            time.sleep(1.0)

    def _run_worker(self, task_id: str) -> None:
        try:
            self.execute_task_now(task_id)
        finally:
            with self._lock:
                self._active_workers = max(0, self._active_workers - 1)


task_scheduler = TaskScheduler()
