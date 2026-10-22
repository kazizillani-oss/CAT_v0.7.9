"""
CAT v0.8.a — Cursor / Pointer Tracking & Context Inference.

Records Pointer Events (mouse/pen/touch) with throttling, dwell detection,
and probabilistic attention inference — never "mind reading".

Spec 10/11: pointer metadata + Cursor Context Inference.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class PointerType(str, Enum):
    MOUSE = "mouse"
    PEN = "pen"
    TOUCH = "touch"
    UNKNOWN = "unknown"


@dataclass
class PointerEvent:
    timestamp: float
    x: float  # normalized 0.0-1.0
    y: float  # normalized 0.0-1.0
    pointer_id: int = 0
    pointer_type: str = "mouse"
    button: int = 0
    pressure: float = 0.5
    movement_x: float = 0.0
    movement_y: float = 0.0
    is_click: bool = False
    is_double_click: bool = False
    is_drag: bool = False
    is_scroll: bool = False
    scroll_delta: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "x": round(self.x, 4),
            "y": round(self.y, 4),
            "pointerId": self.pointer_id,
            "pointerType": self.pointer_type,
            "button": self.button,
            "pressure": round(self.pressure, 3),
            "movement": [round(self.movement_x, 4), round(self.movement_y, 4)],
            "click": self.is_click,
            "doubleClick": self.is_double_click,
            "drag": self.is_drag,
            "scroll": self.is_scroll,
        }


@dataclass
class DwellRegion:
    x: float
    y: float
    radius: float
    dwell_ms: float
    event_count: int
    started_at: float
    ended_at: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "x": round(self.x, 4),
            "y": round(self.y, 4),
            "radius": round(self.radius, 4),
            "dwell_ms": round(self.dwell_ms, 1),
            "event_count": self.event_count,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
        }


class CursorTracker:
    """
    Throttled pointer tracking + dwell detection + attention inference.

    - Throttle: coalesce high-rate pointermove (16ms min interval)
    - Dwell: cursor stays within radius for >= dwell_threshold_ms
    - Inference: probabilistic observations, never mind-reading
    """

    def __init__(self,
                 throttle_ms: float = 16.0,
                 dwell_threshold_ms: float = 800.0,
                 dwell_radius: float = 0.03,
                 max_events: int = 2000):
        self.throttle_ms = throttle_ms
        self.dwell_threshold_ms = dwell_threshold_ms
        self.dwell_radius = dwell_radius
        self.max_events = max_events

        self._events: List[PointerEvent] = []
        self._last_emit_time: float = 0.0
        self._last_pos: Tuple[float, float] = (0.0, 0.0)
        self._dwell_start: Optional[float] = None
        self._dwell_center: Tuple[float, float] = (0.0, 0.0)
        self._dwells: List[DwellRegion] = []
        self._click_count: int = 0
        self._scroll_total: float = 0.0

    # -- ingestion --

    def add_event(self, evt: PointerEvent) -> bool:
        """Add event with throttling. Returns True if stored."""
        now = evt.timestamp or time.time()
        # throttle pointermove without click/drag
        is_move_only = not (evt.is_click or evt.is_drag or evt.is_scroll or evt.is_double_click)
        if is_move_only and self._events:
            elapsed_ms = (now - self._last_emit_time) * 1000
            if elapsed_ms < self.throttle_ms:
                # coalesce: update last move position instead of appending
                if self._events and not self._events[-1].is_click:
                    self._events[-1].x = evt.x
                    self._events[-1].y = evt.y
                    self._events[-1].timestamp = now
                    self._events[-1].movement_x = evt.movement_x
                    self._events[-1].movement_y = evt.movement_y
                    self._update_dwell(evt.x, evt.y, now)
                    return False
        self._events.append(evt)
        self._last_emit_time = now
        self._last_pos = (evt.x, evt.y)
        if len(self._events) > self.max_events:
            self._events = self._events[-self.max_events:]
        if evt.is_click:
            self._click_count += 1
        if evt.is_scroll:
            self._scroll_total += abs(evt.scroll_delta)
        self._update_dwell(evt.x, evt.y, now)
        return True

    def add_raw(self, x: float, y: float,
                pointer_type: str = "mouse",
                pointer_id: int = 0,
                button: int = 0,
                pressure: float = 0.5,
                movement_x: float = 0.0,
                movement_y: float = 0.0,
                is_click: bool = False,
                is_double_click: bool = False,
                is_drag: bool = False,
                is_scroll: bool = False,
                scroll_delta: float = 0.0,
                timestamp: Optional[float] = None) -> bool:
        return self.add_event(PointerEvent(
            timestamp=timestamp or time.time(),
            x=max(0.0, min(1.0, x)),
            y=max(0.0, min(1.0, y)),
            pointer_id=pointer_id,
            pointer_type=pointer_type,
            button=button,
            pressure=pressure,
            movement_x=movement_x,
            movement_y=movement_y,
            is_click=is_click,
            is_double_click=is_double_click,
            is_drag=is_drag,
            is_scroll=is_scroll,
            scroll_delta=scroll_delta,
        ))

    # -- dwell --

    def _update_dwell(self, x: float, y: float, now: float):
        if self._dwell_start is None:
            self._dwell_start = now
            self._dwell_center = (x, y)
            return
        dist = math.hypot(x - self._dwell_center[0], y - self._dwell_center[1])
        if dist > self.dwell_radius:
            # moved away: finalize previous dwell if significant
            dwell_ms = (now - self._dwell_start) * 1000
            if dwell_ms >= self.dwell_threshold_ms:
                self._dwells.append(DwellRegion(
                    x=self._dwell_center[0],
                    y=self._dwell_center[1],
                    radius=self.dwell_radius,
                    dwell_ms=dwell_ms,
                    event_count=1,
                    started_at=self._dwell_start,
                    ended_at=now,
                ))
                if len(self._dwells) > 100:
                    self._dwells = self._dwells[-50:]
            self._dwell_start = now
            self._dwell_center = (x, y)
        # else still dwelling — no action until move away or query

    def get_current_dwell_ms(self) -> float:
        if self._dwell_start is None:
            return 0.0
        return (time.time() - self._dwell_start) * 1000

    # -- queries --

    @property
    def events(self) -> List[PointerEvent]:
        return list(self._events)

    @property
    def dwells(self) -> List[DwellRegion]:
        return list(self._dwells)

    def recent_events(self, n: int = 50) -> List[Dict]:
        return [e.to_dict() for e in self._events[-n:]]

    def get_cursor_context(self) -> Dict[str, Any]:
        """Probabilistic cursor context for AI — never mind-reading."""
        if not self._events:
            return {"has_data": False}
        latest = self._events[-1]
        dwell_ms = self.get_current_dwell_ms()
        recent = self._events[-20:]
        # attention inference
        observations: List[str] = []
        inferences: List[str] = []
        if dwell_ms >= self.dwell_threshold_ms:
            observations.append(f"Cursor remained near ({latest.x:.2f}, {latest.y:.2f}) for {dwell_ms:.0f}ms.")
            inferences.append("User is likely directing attention to this region.")
        if self._click_count >= 2:
            clicks_near = [e for e in recent if e.is_click and math.hypot(e.x - latest.x, e.y - latest.y) < 0.05]
            if len(clicks_near) >= 2:
                observations.append(f"User clicked near ({latest.x:.2f}, {latest.y:.2f}) {len(clicks_near)} times.")
                inferences.append("Repeated clicks suggest the target may be unresponsive or needs attention.")
        if any(e.is_drag for e in recent):
            observations.append("User performed a drag gesture recently.")
            inferences.append("User may be repositioning or selecting content.")
        if abs(self._scroll_total) > 0.5:
            observations.append(f"User scrolled (total delta {self._scroll_total:.1f}).")
        return {
            "has_data": True,
            "latest": latest.to_dict(),
            "dwell_ms": round(dwell_ms, 1),
            "is_dwelling": dwell_ms >= self.dwell_threshold_ms,
            "click_count": self._click_count,
            "scroll_total": round(self._scroll_total, 2),
            "recent_dwell_regions": [d.to_dict() for d in self._dwells[-5:]],
            "observations": observations,
            "inferences": inferences,
            "cursor_label": f"Cursor: X {int(latest.x*1920)}  Y {int(latest.y*1080)}  (normalized {latest.x:.3f}, {latest.y:.3f})",
        }

    def clear(self):
        self._events.clear()
        self._dwells.clear()
        self._click_count = 0
        self._scroll_total = 0
        self._dwell_start = None
        self._last_emit_time = 0.0
