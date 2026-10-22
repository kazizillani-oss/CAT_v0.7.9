"""
CAT v0.8.a — Vision Event System (spec 41).

Shared event names + helper to emit on both the backend bus (eventbus)
and the UI event stream (event_stream) where appropriate.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

# Vision event names (spec 41)
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

ALL_VISION_EVENTS = [
    VISION_SESSION_STARTED,
    VISION_SESSION_STOPPED,
    VISION_CAPTURE_STARTED,
    VISION_CAPTURE_ENDED,
    VISION_FRAME_SELECTED,
    VISION_FRAME_ANALYZED,
    VISION_CURSOR_EVENT,
    VISION_ANNOTATION_CREATED,
    VISION_ANNOTATION_UPDATED,
    VISION_ANNOTATION_DELETED,
    VISION_USER_MESSAGE,
    VISION_AI_ANALYSIS,
    VISION_FIX_PROPOSED,
    VISION_FIX_APPLIED,
    VISION_PREVIEW_REFRESHED,
    VISION_VERIFICATION_COMPLETE,
]


def emit_vision_event(event: str, **data: Any):
    """Emit a vision event on the backend bus + event_stream (best effort)."""
    data.setdefault("ts", time.time())
    data.setdefault("source", "vision")
    # backend bus (sync pub/sub) — ui/app.py can subscribe
    try:
        from .. import eventbus
        eventbus.bus.publish(event, **data)
    except Exception:
        pass
    # event_stream (bounded buffer with subscribers)
    try:
        from .. import event_stream
        event_stream.stream.emit(event, **data)
    except Exception:
        pass
