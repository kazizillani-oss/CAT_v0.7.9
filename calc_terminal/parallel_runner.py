"""
CAT Parallel Runner & Background Jobs Engine (v0.9.000).

Powers:
  1. Multi-Session Background Execution: Run tasks quietly in the background
     as a persistent helper without blocking the active chat UI.
  2. Dual-Agent Parallel Workflows: Run one AI model to build code (Aria)
     while another AI model reviews and inspects in parallel (Mira).
  3. Job lifecycle management: submit, status, inspect, and cancel.
"""

from __future__ import annotations

import os
import sys
import time
import json
import uuid
import logging
import threading
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Callable

_LOG = logging.getLogger("cct.parallel_runner")


@dataclass
class BackgroundJob:
    job_id: str
    title: str
    prompt: str
    role: str = "helper"
    model: str = "default"
    provider: str = "default"
    status: str = "running"  # running, completed, failed, cancelled
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    output: str = ""
    error: Optional[str] = None
    progress: float = 0.0

    @property
    def duration_seconds(self) -> float:
        end = self.completed_at or time.time()
        return max(0.0, end - self.created_at)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "title": self.title,
            "prompt": self.prompt,
            "role": self.role,
            "model": self.model,
            "provider": self.provider,
            "status": self.status,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "duration_seconds": round(self.duration_seconds, 2),
            "output": self.output,
            "error": self.error,
            "progress": self.progress,
        }


class BackgroundJobManager:
    """Singleton coordinator for persistent background helper tasks."""

    _instance: Optional[BackgroundJobManager] = None
    _lock = threading.Lock()

    def __init__(self):
        self._jobs: Dict[str, BackgroundJob] = {}
        self._threads: Dict[str, threading.Thread] = {}
        self._cancel_events: Dict[str, threading.Event] = {}

    @classmethod
    def get_instance(cls) -> BackgroundJobManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = BackgroundJobManager()
            return cls._instance

    def submit_job(
        self,
        prompt: str,
        title: Optional[str] = None,
        role: str = "helper",
        model: Optional[str] = None,
        provider: Optional[str] = None,
        on_complete: Optional[Callable[[BackgroundJob], None]] = None,
    ) -> BackgroundJob:
        """Submit a task to run quietly in the background as a persistent helper."""
        job_id = f"job-{uuid.uuid4().hex[:8]}"
        job_title = title or (prompt[:40] + "..." if len(prompt) > 40 else prompt)

        job = BackgroundJob(
            job_id=job_id,
            title=job_title,
            prompt=prompt,
            role=role,
            model=model or "default",
            provider=provider or "default",
            status="running",
        )

        with self._lock:
            self._jobs[job_id] = job
            cancel_evt = threading.Event()
            self._cancel_events[job_id] = cancel_evt

        def _worker():
            try:
                from . import aicore
                cfg = aicore.load_config() or {}
                use_prov = provider or cfg.get("provider", "OLLAMA")
                use_model = model or cfg.get("model", "deepseek-r1:latest")

                system_prompt = (
                    f"You are a quiet, persistent background helper agent in CAT CLI.\n"
                    f"Execute this task thoroughly, producing clean, structured, production-ready results.\n"
                    f"Role: {role}."
                )

                job.output = ""
                # Execute via stream_ai or query_ai
                collected = []
                cfg_override = dict(cfg) if cfg else {}
                if use_prov:
                    cfg_override["provider"] = use_prov
                if use_model:
                    cfg_override["model"] = use_model
                for chunk in aicore.stream_ai(
                    prompt,
                    system_prompt=system_prompt,
                    config=cfg_override,
                ):
                    if cancel_evt.is_set():
                        job.status = "cancelled"
                        job.completed_at = time.time()
                        return
                    if chunk:
                        collected.append(chunk)

                job.output = "".join(collected).strip()
                job.status = "completed"
                job.progress = 1.0
                job.completed_at = time.time()
            except Exception as ex:
                job.status = "failed"
                job.error = str(ex)
                job.completed_at = time.time()
                _LOG.error(f"Background job {job_id} failed: {ex}")
            finally:
                if on_complete:
                    try:
                        on_complete(job)
                    except Exception:
                        pass

        t = threading.Thread(target=_worker, name=f"cct-bg-{job_id}", daemon=True)
        with self._lock:
            self._threads[job_id] = t
        t.start()
        return job

    def list_jobs(self) -> List[BackgroundJob]:
        with self._lock:
            return list(self._jobs.values())

    def get_job(self, job_id: str) -> Optional[BackgroundJob]:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        with self._lock:
            evt = self._cancel_events.get(job_id)
            if evt:
                evt.set()
                job = self._jobs.get(job_id)
                if job and job.status == "running":
                    job.status = "cancelled"
                    job.completed_at = time.time()
                return True
            return False


def run_parallel_build_and_review(
    build_prompt: str,
    review_prompt: Optional[str] = None,
    build_model: Optional[str] = None,
    review_model: Optional[str] = None,
    timeout_sec: float = 60.0,
) -> Dict[str, Any]:
    """Execute dual-agent parallel workflow: Aria builds while Mira reviews concurrently.

    Runs Model A (Aria - Build Agent) and Model B (Mira - Planning & Review Agent)
    in parallel threads, synchronizes their output, and returns a unified report.
    """
    from . import aicore, ai_modes

    if not review_prompt:
        review_prompt = (
            f"Review and inspect the architectural design, safety, security, edge cases, "
            f"and testing requirements for the following project request:\n\n{build_prompt}"
        )

    results = {
        "build_output": "",
        "review_output": "",
        "build_duration": 0.0,
        "review_duration": 0.0,
        "status": "pending",
        "error": None,
    }

    t_start = time.perf_counter()

    def _run_build():
        t0 = time.perf_counter()
        try:
            aria_prompt = ai_modes.system_prompt_for("build")
            collected = []
            cfg_b = aicore.load_config() or {}
            if build_model:
                cfg_b = dict(cfg_b)
                cfg_b["model"] = build_model
            for chunk in aicore.stream_ai(
                build_prompt,
                system_prompt=aria_prompt,
                config=cfg_b,
            ):
                if chunk:
                    collected.append(chunk)
            results["build_output"] = "".join(collected).strip()
        except Exception as e:
            results["build_output"] = f"[Build Error: {e}]"
        finally:
            results["build_duration"] = round(time.perf_counter() - t0, 2)

    def _run_review():
        t0 = time.perf_counter()
        try:
            mira_prompt = ai_modes.system_prompt_for("plan")
            collected = []
            cfg_r = aicore.load_config() or {}
            if review_model:
                cfg_r = dict(cfg_r)
                cfg_r["model"] = review_model
            for chunk in aicore.stream_ai(
                review_prompt,
                system_prompt=mira_prompt,
                config=cfg_r,
            ):
                if chunk:
                    collected.append(chunk)
            results["review_output"] = "".join(collected).strip()
        except Exception as e:
            results["review_output"] = f"[Review Error: {e}]"
        finally:
            results["review_duration"] = round(time.perf_counter() - t0, 2)

    tb = threading.Thread(target=_run_build, name="cct-parallel-aria-build", daemon=True)
    tr = threading.Thread(target=_run_review, name="cct-parallel-mira-review", daemon=True)

    tb.start()
    tr.start()

    tb.join(timeout=timeout_sec)
    tr.join(timeout=timeout_sec)

    results["total_duration"] = round(time.perf_counter() - t_start, 2)
    results["status"] = "completed"

    report = (
        f"# ⚡ Parallel Dual-Agent Execution: Aria (Build) & Mira (Review)\n\n"
        f"**Execution Summary**: Completed in {results['total_duration']}s (Aria: {results['build_duration']}s, Mira: {results['review_duration']}s)\n\n"
        f"---\n\n"
        f"## 🔨 Aria · Build Implementation\n\n"
        f"{results['build_output']}\n\n"
        f"---\n\n"
        f"## 🧭 Mira · Architectural Review & Inspection (Read-Only)\n\n"
        f"{results['review_output']}\n\n"
        f"---\n\n"
        f"### 🎯 Parallel Collaboration Synthesis\n"
        f"- **Implementation**: Aria generated the active code solution.\n"
        f"- **Verification & Inspection**: Mira completed non-destructive project and safety review in parallel.\n"
    )
    results["synthesized"] = report
    return results
