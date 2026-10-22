"""
CAT v0.8.a — Before/After Verification System.

Captures before state, applies code change, captures after state,
and compares to verify the fix worked visually.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class VerificationStatus(str, Enum):
    PENDING = "pending"
    CAPTURING_BEFORE = "capturing_before"
    APPLYING_FIX = "applying_fix"
    CAPTURING_AFTER = "capturing_after"
    COMPARING = "comparing"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class VerificationResult:
    status: VerificationStatus
    before_frame_b64: Optional[str] = None
    after_frame_b64: Optional[str] = None
    before_meta: Optional[Dict[str, Any]] = None
    after_meta: Optional[Dict[str, Any]] = None
    change_description: str = ""
    visual_differences: List[str] = field(default_factory=list)
    ai_analysis: str = ""
    confidence: float = 0.0
    duration_ms: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "before_meta": self.before_meta,
            "after_meta": self.after_meta,
            "change_description": self.change_description,
            "visual_differences": self.visual_differences,
            "ai_analysis": self.ai_analysis,
            "confidence": self.confidence,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "has_before_frame": bool(self.before_frame_b64),
            "has_after_frame": bool(self.after_frame_b64),
        }


class BeforeAfterVerifier:
    """Manages the before → fix → after → compare verification cycle."""

    def __init__(self):
        self._history: List[VerificationResult] = []
        self._current: Optional[VerificationResult] = None
        self._max_history = 20

    @property
    def current(self) -> Optional[VerificationResult]:
        return self._current

    @property
    def history(self) -> List[Dict]:
        return [r.to_dict() for r in self._history[-self._max_history:]]

    def start_verification(self) -> VerificationResult:
        self._current = VerificationResult(
            status=VerificationStatus.CAPTURING_BEFORE,
            change_description="",
        )
        return self._current

    def set_before_frame(self, frame_b64: str, meta: Optional[Dict] = None):
        if self._current is None:
            self.start_verification()
        self._current.before_frame_b64 = frame_b64
        self._current.before_meta = meta
        self._current.status = VerificationStatus.APPLYING_FIX

    def set_fix_applied(self, description: str = ""):
        if self._current is None:
            return
        self._current.change_description = description
        self._current.status = VerificationStatus.CAPTURING_AFTER

    def set_after_frame(self, frame_b64: str, meta: Optional[Dict] = None):
        if self._current is None:
            return
        self._current.after_frame_b64 = frame_b64
        self._current.after_meta = meta
        self._current.status = VerificationStatus.COMPARING

    def complete(self, ai_analysis: str, passed: bool,
                 confidence: float = 0.0,
                 visual_differences: Optional[List[str]] = None):
        if self._current is None:
            return
        self._current.ai_analysis = ai_analysis
        self._current.confidence = confidence
        self._current.visual_differences = visual_differences or []
        self._current.status = (
            VerificationStatus.PASSED if passed
            else VerificationStatus.FAILED
        )
        self._current.duration_ms = (
            (time.time() - (self._current.before_meta or {}).get("timestamp", time.time()))
            * 1000
        )
        self._history.append(self._current)
        result = self._current
        self._current = None
        return result

    def error(self, message: str):
        if self._current is None:
            return
        self._current.status = VerificationStatus.ERROR
        self._current.error = message
        self._history.append(self._current)
        self._current = None

    def skip(self, reason: str = ""):
        if self._current is None:
            return
        self._current.status = VerificationStatus.SKIPPED
        self._current.change_description = reason
        self._history.append(self._current)
        self._current = None

    def build_comparison_prompt(self) -> str:
        if self._current is None:
            return ""
        parts = [
            "BEFORE/AFTER VISUAL VERIFICATION",
            f"Fix applied: {self._current.change_description}",
            "",
            "Compare the BEFORE and AFTER screen captures.",
            "Determine if the fix was successful by checking:",
            "1. Did the error/warning disappear?",
            "2. Did the expected UI change occur?",
            "3. Were there any unintended side effects?",
            "4. Is the visual state correct now?",
            "",
            "Respond with:",
            "- PASS or FAIL",
            "- Confidence level (0-100%)",
            "- List of visual differences observed",
            "- Brief explanation of what changed",
        ]
        return "\n".join(parts)

    def clear_history(self):
        self._history.clear()
        self._current = None
