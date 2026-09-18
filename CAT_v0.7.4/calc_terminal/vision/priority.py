"""
CAT v0.8.a — Frame Priority Engine (spec 9).

Scores frames/events for AI analysis priority:

  score = visual_change + interaction_event + annotation_event
        + user_request + error_signal + AI_requested_frame

Only high-value frames are sent to expensive multimodal reasoning.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class PriorityLevel(str, Enum):
    SKIP = "skip"
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PriorityScore:
    total: float
    level: PriorityLevel
    breakdown: Dict[str, float]
    should_send: bool
    reasons: List[str]


class FramePriorityEngine:
    """
    Event-driven priority scoring. Call score_event() for each signal;
    call score_frame() to combine into a final decision for a candidate frame.
    """

    # Weights — tuned so obvious signals dominate redundant frame dribbles
    WEIGHTS = {
        "visual_change_none": 0,
        "visual_change_minor": 5,
        "visual_change_moderate": 15,
        "visual_change_major": 30,
        "visual_change_critical": 50,
        "cursor_move": 2,
        "cursor_dwell": 12,
        "click": 18,
        "annotation": 25,
        "scroll": 4,
        "user_chat": 35,
        "user_analyze_request": 40,
        "ai_requested_frame": 45,
        "error_signal": 40,
        "preview_change": 20,
        "ui_state_change": 10,
    }

    # Thresholds for final level
    THRESHOLDS = {
        PriorityLevel.SKIP: 0,
        PriorityLevel.LOW: 5,
        PriorityLevel.NORMAL: 15,
        PriorityLevel.HIGH: 30,
        PriorityLevel.CRITICAL: 45,
    }

    def __init__(self, high_threshold: float = 30.0):
        self.high_threshold = high_threshold
        self._pending_signals: List[Dict[str, Any]] = []
        self._last_send_time: float = 0.0
        self._min_send_interval: float = 1.0  # seconds, adaptive
        self._consecutive_skips: int = 0

    def add_signal(self, kind: str, value: float = 1.0, detail: str = ""):
        """Queue a signal; it will be consumed on next score_frame()."""
        self._pending_signals.append({
            "kind": kind,
            "value": value,
            "detail": detail,
            "ts": time.time(),
        })
        # keep bounded
        if len(self._pending_signals) > 100:
            self._pending_signals = self._pending_signals[-50:]

    # Convenience helpers
    def signal_visual_change(self, level: str):
        key = f"visual_change_{level}"
        self.add_signal(key, detail=level)

    def signal_cursor_move(self): self.add_signal("cursor_move")
    def signal_cursor_dwell(self): self.add_signal("cursor_dwell")
    def signal_click(self): self.add_signal("click")
    def signal_annotation(self, tool: str = ""): self.add_signal("annotation", detail=tool)
    def signal_scroll(self): self.add_signal("scroll")
    def signal_user_chat(self): self.add_signal("user_chat")
    def signal_user_analyze(self): self.add_signal("user_analyze_request")
    def signal_ai_request(self): self.add_signal("ai_requested_frame")
    def signal_error(self, msg: str = ""): self.add_signal("error_signal", detail=msg)
    def signal_preview_change(self): self.add_signal("preview_change")
    def signal_ui_state_change(self): self.add_signal("ui_state_change")

    def score_frame(self,
                    visual_change: str = "none",
                    has_annotation: bool = False,
                    has_cursor_event: bool = False,
                    has_user_request: bool = False,
                    has_error: bool = False,
                    ai_requested: bool = False,
                    force: bool = False) -> PriorityScore:
        """
        Score a candidate frame. Also drains pending signals.
        Set force=True for explicit user Analyze actions (always send).
        """
        breakdown: Dict[str, float] = {}
        reasons: List[str] = []
        total = 0.0

        # visual change component
        vc_key = f"visual_change_{visual_change}"
        vc_score = self.WEIGHTS.get(vc_key, 0)
        if vc_score:
            breakdown["visual_change"] = vc_score
            reasons.append(f"visual:{visual_change} +{vc_score}")
            total += vc_score

        # pending signals
        for sig in self._pending_signals:
            w = self.WEIGHTS.get(sig["kind"], 0)
            if w:
                breakdown[sig["kind"]] = breakdown.get(sig["kind"], 0) + w
                reasons.append(f"{sig['kind']} +{w}")
                total += w
        self._pending_signals.clear()

        # explicit flags (additive if not already counted via signals)
        if has_annotation and "annotation" not in breakdown:
            w = self.WEIGHTS["annotation"]
            breakdown["annotation"] = w
            reasons.append(f"annotation +{w}")
            total += w
        if has_cursor_event and "cursor_move" not in breakdown and "cursor_dwell" not in breakdown:
            w = self.WEIGHTS["cursor_move"]
            breakdown["cursor_event"] = w
            total += w
        if has_user_request and "user_chat" not in breakdown:
            w = self.WEIGHTS["user_chat"]
            breakdown["user_request"] = w
            reasons.append(f"user_request +{w}")
            total += w
        if has_error:
            w = self.WEIGHTS["error_signal"]
            breakdown["error_signal"] = breakdown.get("error_signal", 0) + w
            reasons.append(f"error +{w}")
            total += w
        if ai_requested:
            w = self.WEIGHTS["ai_requested_frame"]
            breakdown["ai_requested"] = w
            reasons.append(f"ai_requested +{w}")
            total += w

        # level
        if force:
            level = PriorityLevel.CRITICAL
            should_send = True
        elif total >= self.THRESHOLDS[PriorityLevel.CRITICAL]:
            level = PriorityLevel.CRITICAL
            should_send = True
        elif total >= self.THRESHOLDS[PriorityLevel.HIGH]:
            level = PriorityLevel.HIGH
            should_send = True
        elif total >= self.THRESHOLDS[PriorityLevel.NORMAL]:
            level = PriorityLevel.NORMAL
            # throttle normal frames
            should_send = (time.time() - self._last_send_time) >= self._min_send_interval
            if not should_send:
                reasons.append("throttled (normal priority, interval)")
        elif total >= self.THRESHOLDS[PriorityLevel.LOW]:
            level = PriorityLevel.LOW
            should_send = False
            reasons.append("low priority — skipped")
        else:
            level = PriorityLevel.SKIP
            should_send = False

        if should_send:
            self._last_send_time = time.time()
            self._consecutive_skips = 0
        else:
            self._consecutive_skips += 1
            # anti-starvation: force send after many skips if we have moderate visual change
            if self._consecutive_skips >= 10 and visual_change in ("moderate", "major", "critical"):
                should_send = True
                level = PriorityLevel.NORMAL
                reasons.append("anti-starvation override")
                self._consecutive_skips = 0
                self._last_send_time = time.time()

        return PriorityScore(
            total=round(total, 1),
            level=level,
            breakdown=breakdown,
            should_send=should_send,
            reasons=reasons,
        )

    def set_min_interval(self, seconds: float):
        self._min_send_interval = max(0.2, seconds)

    def reset(self):
        self._pending_signals.clear()
        self._last_send_time = 0.0
        self._consecutive_skips = 0
