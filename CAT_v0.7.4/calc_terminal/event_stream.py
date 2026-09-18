import time
import threading
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

MODEL_RESPONSE = "model_response"
TOOL_REQUEST = "tool_request"
TOOL_STARTED = "tool_started"
TOOL_RESULT = "tool_result"
FILE_CREATED = "file_created"
FILE_EDITED = "file_edited"
FILE_DELETED = "file_deleted"
FILE_MOVED = "file_moved"
COMMAND_STARTED = "command_started"
COMMAND_RESULT = "command_result"
MEMORY_READ = "memory_read"
MEMORY_CREATED = "memory_created"
MEMORY_UPDATED = "memory_updated"
MEMORY_DELETED = "memory_deleted"
AGENT_STARTED = "agent_started"
AGENT_COMPLETED = "agent_completed"
AGENT_FAILED = "agent_failed"
SESSION_CLEARED = "session_cleared"
CONTEXT_SWITCHED = "context_switched"

# ---------------------------------------------------------------------------
# v0.7.9.0 — unified real-time activity vocabulary (requirement #2/#29).
# Every displayed operation must correspond to an actual backend event;
# these are the topics the whole runtime (model router, agent loop, vision
# pipeline, multi-AI orchestrator) publishes and the UI subscribes to.
# ---------------------------------------------------------------------------
USER_MESSAGE = "user_message"                  # request entered the pipeline
ROUTE_DECIDED = "route_decided"                # smart router picked a path
MODEL_SELECTED = "model_selected"              # which model/config will answer
MODEL_REQUEST_STARTED = "model_request_started"
MODEL_FIRST_TOKEN = "model_first_token"        # real first token arrived
TEXT_DELTA = "text_delta"                      # streamed text fragment
AGENT_THINKING = "agent_thinking"              # waiting on model reasoning
TOOL_DETECTED = "tool_detected"
TOOL_PROGRESS = "tool_progress"
TOOL_FINISHED = "tool_finished"
AGENT_CONTINUING = "agent_continuing"          # tool result fed back → looping
AGENT_SWITCHED = "agent_switched"
MULTI_AGENT_STARTED = "multi_agent_started"
MULTI_AGENT_PROGRESS = "multi_agent_progress"
MULTI_AGENT_FINISHED = "multi_agent_finished"
IMAGE_ANALYSIS_STARTED = "image_analysis_started"
IMAGE_ANALYSIS_FINISHED = "image_analysis_finished"
FINAL_RESPONSE = "final_response"              # turn truly complete
ERROR = "error"

# Vision events (v0.8.a CAT Vision — spec 41)
VISION_SESSION_STARTED = "VISION_SESSION_STARTED"
VISION_SESSION_STOPPED = "VISION_SESSION_STOPPED"
VISION_CAPTURE_STARTED = "VISION_CAPTURE_STARTED"
VISION_CAPTURE_ENDED = "VISION_CAPTURE_ENDED"
VISION_FRAME_SELECTED = "VISION_FRAME_SELECTED"
VISION_FRAME_ANALYZED = "VISION_FRAME_ANALYZED"
VISION_CURSOR_EVENT = "VISION_CURSOR_EVENT"
VISION_ANNOTATION_CREATED = "VISION_ANNOTATION_CREATED"
VISION_ANNOTATION_UPDATED = "VISION_ANNOTATION_UPDATED"
VISION_ANNOTATION_DELETED = "VISION_ANNOTATION_DELETED"
VISION_USER_MESSAGE = "VISION_USER_MESSAGE"
VISION_AI_ANALYSIS = "VISION_AI_ANALYSIS"
VISION_FIX_PROPOSED = "VISION_FIX_PROPOSED"
VISION_FIX_APPLIED = "VISION_FIX_APPLIED"
VISION_PREVIEW_REFRESHED = "VISION_PREVIEW_REFRESHED"
VISION_VERIFICATION_COMPLETE = "VISION_VERIFICATION_COMPLETE"

# Bounded buffer: a very long session must not grow this without limit.
_MAX_BUFFER = 500


@dataclass
class Event:
    event_type: str
    timestamp: float
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = ""


class EventStream:
    def __init__(self):
        self._buffer: List[Event] = []
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()

    def emit(self, event_type: str, source: str = "", **data: Any) -> Event:
        event = Event(
            event_type=event_type,
            timestamp=time.time(),
            data=data,
            source=source,
        )
        with self._lock:
            self._buffer.append(event)
            if len(self._buffer) > _MAX_BUFFER:
                del self._buffer[:len(self._buffer) - _MAX_BUFFER]
            subscribers = list(self._subscribers.get(event_type, []))

        for callback in subscribers:
            try:
                callback(event)
            except Exception as e:
                logger.debug("Subscriber error for %s: %s", event_type, e)

        return event

    def subscribe(self, event_type: str, callback: Callable) -> Callable:
        with self._lock:
            self._subscribers.setdefault(event_type, []).append(callback)
        return callback

    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        with self._lock:
            subscribers = self._subscribers.get(event_type, [])
            if callback in subscribers:
                subscribers.remove(callback)

    def get_recent(self, event_type: Optional[str] = None, limit: int = 50) -> List[Event]:
        with self._lock:
            if event_type is None:
                return list(self._buffer[-limit:])
            return [e for e in self._buffer if e.event_type == event_type][-limit:]

    def get_all(self, event_type: Optional[str] = None) -> List[Event]:
        with self._lock:
            if event_type is None:
                return list(self._buffer)
            return [e for e in self._buffer if e.event_type == event_type]

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()

    def subscriber_count(self, event_type: Optional[str] = None) -> int:
        with self._lock:
            if event_type is None:
                return sum(len(subs) for subs in self._subscribers.values())
            return len(self._subscribers.get(event_type, []))


stream = EventStream()
