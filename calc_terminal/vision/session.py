"""
CAT v0.8.a — Vision Session Manager.

Manages session lifecycle with an explicit state machine:
  IDLE → STARTING → ACTIVE → PAUSED → STOPPING → STOPPED → IDLE

Each session owns a capture engine, frame pipeline, annotation engine,
and context engine.  Sessions are identified by UUID and stored in a
registry for the duration of their lifetime.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .capture import CaptureConfig, CaptureEngine, CaptureMode
from .frame_pipeline import FrameMeta, FramePipeline
from .annotations import Annotation, AnnotationEngine, AnnotationTool
from .context import VisualContext, VisionContextEngine
from .safety import PrivacyController, SafetyConfig
from .cursor import CursorTracker
from .priority import FramePriorityEngine


class SessionState(str, Enum):
    IDLE = "idle"
    STARTING = "starting"
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class VisionSession:
    """A single vision capture session."""

    __slots__ = (
        "id", "state", "created_at", "started_at", "stopped_at",
        "config", "capture", "pipeline", "annotations", "context",
        "cursor", "priority",
        "privacy", "event_log", "error",
    )

    def __init__(self, config: CaptureConfig, privacy: PrivacyController):
        self.id: str = str(uuid.uuid4())
        self.state: SessionState = SessionState.IDLE
        self.created_at: float = time.time()
        self.started_at: Optional[float] = None
        self.stopped_at: Optional[float] = None
        self.config = config
        self.capture = CaptureEngine(config)
        self.pipeline = FramePipeline(config)
        self.annotations = AnnotationEngine()
        self.context = VisionContextEngine()
        self.cursor = CursorTracker()
        self.priority = FramePriorityEngine()
        self.privacy = privacy
        self.event_log: List[Dict[str, Any]] = []
        self.error: Optional[str] = None

    def log_event(self, event: str, data: Optional[Dict] = None):
        entry = {"ts": time.time(), "event": event}
        if data:
            entry.update(data)
        self.event_log.append(entry)
        if len(self.event_log) > 2000:
            self.event_log = self.event_log[-1000:]

    @property
    def duration(self) -> Optional[float]:
        if self.started_at is None:
            return None
        end = self.stopped_at or time.time()
        return end - self.started_at

    @property
    def frame_count(self) -> int:
        return self.pipeline.frame_count

    @property
    def annotation_count(self) -> int:
        return len(self.annotations.annotations)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "state": self.state.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "duration": self.duration,
            "frame_count": self.frame_count,
            "annotation_count": self.annotation_count,
            "config": {
                "mode": self.config.mode.value,
                "fps": self.config.fps,
                "quality": self.config.quality,
                "max_frames": self.config.max_frames,
            },
            "error": self.error,
            "event_count": len(self.event_log),
            "cursor": self.cursor.get_cursor_context(),
            "priority_level": self.priority._consecutive_skips,
        }


class VisionSessionManager:
    """Registry and lifecycle controller for vision sessions."""

    def __init__(self, safety_config: Optional[SafetyConfig] = None):
        self._sessions: Dict[str, VisionSession] = {}
        self._privacy = PrivacyController(safety_config or SafetyConfig())
        self._callbacks: Dict[str, List[Callable]] = {}
        self._max_sessions = 5

    def on(self, event: str, cb: Callable):
        self._callbacks.setdefault(event, []).append(cb)

    def _emit(self, event: str, data: Any = None):
        for cb in self._callbacks.get(event, []):
            try:
                cb(data)
            except Exception:
                pass

    @property
    def active_count(self) -> int:
        return sum(
            1 for s in self._sessions.values()
            if s.state in (SessionState.ACTIVE, SessionState.PAUSED)
        )

    def list_sessions(self) -> List[Dict]:
        return [s.to_dict() for s in self._sessions.values()]

    def get_session(self, session_id: str) -> Optional[VisionSession]:
        return self._sessions.get(session_id)

    def create_session(self, config: Optional[CaptureConfig] = None) -> VisionSession:
        if self.active_count >= self._max_sessions:
            raise RuntimeError(
                f"Maximum concurrent sessions ({self._max_sessions}) reached"
            )
        if config is None:
            config = CaptureConfig()
        self._privacy.validate_config(config)
        session = VisionSession(config, self._privacy)
        session.state = SessionState.IDLE
        self._sessions[session.id] = session
        session.log_event("session_created")
        self._emit("session_created", session)
        return session

    async def start_session(self, session_id: str) -> VisionSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Session {session_id} not found")
        if session.state not in (SessionState.IDLE, SessionState.STOPPED):
            raise RuntimeError(
                f"Cannot start session in state {session.state.value}"
            )
        session.state = SessionState.STARTING
        session.log_event("session_starting")
        try:
            await session.capture.initialize()
            session.state = SessionState.ACTIVE
            session.started_at = time.time()
            session.log_event("session_started")
            self._emit("session_started", session)
        except Exception as e:
            session.state = SessionState.ERROR
            session.error = str(e)
            session.log_event("session_error", {"error": str(e)})
            self._emit("session_error", session)
            raise
        return session

    async def stop_session(self, session_id: str) -> VisionSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Session {session_id} not found")
        if session.state in (SessionState.STOPPED, SessionState.STOPPING):
            return session
        session.state = SessionState.STOPPING
        session.log_event("session_stopping")
        try:
            await session.capture.cleanup()
            session.state = SessionState.STOPPED
            session.stopped_at = time.time()
            session.log_event("session_stopped")
            self._emit("session_stopped", session)
        except Exception as e:
            session.state = SessionState.ERROR
            session.error = str(e)
            session.log_event("session_error", {"error": str(e)})
        return session

    async def pause_session(self, session_id: str):
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Session {session_id} not found")
        if session.state != SessionState.ACTIVE:
            raise RuntimeError("Can only pause an active session")
        session.state = SessionState.PAUSED
        session.capture.paused = True
        session.log_event("session_paused")
        self._emit("session_paused", session)

    async def resume_session(self, session_id: str):
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Session {session_id} not found")
        if session.state != SessionState.PAUSED:
            raise RuntimeError("Can only resume a paused session")
        session.state = SessionState.ACTIVE
        session.capture.paused = False
        session.log_event("session_resumed")
        self._emit("session_resumed", session)

    async def destroy_session(self, session_id: str):
        session = self._sessions.get(session_id)
        if session is None:
            return
        if session.state in (SessionState.ACTIVE, SessionState.PAUSED):
            await self.stop_session(session_id)
        self._sessions.pop(session_id, None)
        self._emit("session_destroyed", session)

    async def cleanup_all(self):
        ids = list(self._sessions.keys())
        for sid in ids:
            try:
                await self.destroy_session(sid)
            except Exception:
                pass
        self._sessions.clear()

    def process_frame(self, session_id: str, frame_b64: str,
                      meta: Optional[FrameMeta] = None,
                      priority_force: bool = False) -> Optional[Dict]:
        session = self._sessions.get(session_id)
        if session is None or session.state != SessionState.ACTIVE:
            return None
        if session.privacy.is_blocked_region(frame_b64):
            return {"blocked": True, "reason": "privacy_block"}
        # Priority engine gates expensive work
        change_level = session.pipeline._detect_change(frame_b64, session.pipeline._compute_hash(frame_b64)) if hasattr(session.pipeline, '_detect_change') else None
        level_str = change_level.value if change_level else "minor"
        has_ann = bool(meta.annotations) if meta and getattr(meta, 'annotations', None) else False
        prio = session.priority.score_frame(
            visual_change=level_str,
            has_annotation=has_ann,
            has_cursor_event=bool(session.cursor.events),
            force=priority_force,
        )
        if not prio.should_send and not priority_force:
            return None
        result = session.pipeline.ingest(frame_b64, meta)
        if result:
            result["priority"] = {
                "total": prio.total,
                "level": prio.level.value,
                "should_send": prio.should_send,
                "reasons": prio.reasons,
            }
            session.log_event("frame_selected", {
                "index": session.pipeline.frame_count,
                "change_level": result.get("change_level"),
                "priority": prio.level.value,
            })
            try:
                from .events import emit_vision_event, VISION_FRAME_SELECTED
                emit_vision_event(VISION_FRAME_SELECTED, session_id=session_id, frame_index=result.get("frame_index"), priority=prio.level.value)
            except Exception:
                pass
        return result
