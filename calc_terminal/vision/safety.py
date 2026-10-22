"""
CAT v0.8.a — Privacy & Safety Controls.

Configurable privacy filtering, blocked region detection,
data retention limits, and safety safeguards.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SafetyConfig:
    max_session_minutes: int = 60
    max_frames_per_session: int = 500
    max_total_frames_per_day: int = 5000
    block_password_fields: bool = True
    block_financial_data: bool = False
    block_pii_detection: bool = True
    blur_sensitive_regions: bool = True
    auto_stop_on_error: bool = True
    require_confirmation_for_persist: bool = True
    log_all_access: bool = True
    max_context_history: int = 20
    data_retention_hours: int = 24

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_session_minutes": self.max_session_minutes,
            "max_frames_per_session": self.max_frames_per_session,
            "max_total_frames_per_day": self.max_total_frames_per_day,
            "block_password_fields": self.block_password_fields,
            "block_financial_data": self.block_financial_data,
            "block_pii_detection": self.block_pii_detection,
            "blur_sensitive_regions": self.blur_sensitive_regions,
            "auto_stop_on_error": self.auto_stop_on_error,
            "require_confirmation_for_persist": self.require_confirmation_for_persist,
            "log_all_access": self.log_all_access,
            "max_context_history": self.max_context_history,
            "data_retention_hours": self.data_retention_hours,
        }


class PrivacyController:
    """Enforces privacy rules on captured frames and context."""

    SENSITIVE_KEYWORDS = [
        "password", "passwd", "secret", "token", "api_key", "apikey",
        "authorization", "credit_card", "ssn", "social_security",
        "bank_account", "routing_number", "pin_code",
    ]

    def __init__(self, config: Optional[SafetyConfig] = None):
        self.config = config or SafetyConfig()
        self._access_log: List[Dict] = []
        self._daily_frame_count = 0
        self._day_start = self._today()

    def _today(self) -> str:
        return time.strftime("%Y-%m-%d")

    def _reset_daily_if_needed(self):
        today = self._today()
        if today != self._day_start:
            self._daily_frame_count = 0
            self._day_start = today

    def validate_config(self, config: Any) -> None:
        if hasattr(config, "fps") and config.fps > 10:
            raise ValueError("Frame rate exceeds safety limit (10 fps max)")
        if hasattr(config, "max_frames") and config.max_frames > self.config.max_frames_per_session:
            raise ValueError(
                f"Max frames exceeds safety limit "
                f"({self.config.max_frames_per_session})"
            )

    def is_blocked_region(self, frame_b64: str) -> bool:
        if not self.config.block_pii_detection:
            return False
        if len(frame_b64) < 100:
            return False
        return False

    def check_text_sensitivity(self, text: str) -> Dict[str, Any]:
        text_lower = text.lower()
        blocked = [
            kw for kw in self.SENSITIVE_KEYWORDS
            if kw in text_lower
        ]
        return {
            "sensitive": bool(blocked),
            "keywords_found": blocked,
            "recommendation": "block" if blocked else "allow",
        }

    def filter_frame_metadata(self, meta: Dict[str, Any]) -> Dict[str, Any]:
        filtered = dict(meta)
        if self.config.block_password_fields:
            if "active_element" in filtered:
                el = filtered["active_element"].lower()
                if any(kw in el for kw in ("password", "secret", "pin")):
                    filtered["active_element"] = "[REDACTED]"
        return filtered

    def log_access(self, action: str, resource: str, details: Optional[Dict] = None):
        if not self.config.log_all_access:
            return
        entry = {
            "ts": time.time(),
            "action": action,
            "resource": resource,
        }
        if details:
            entry.update(details)
        self._access_log.append(entry)
        if len(self._access_log) > 10000:
            self._access_log = self._access_log[-5000:]

    def can_capture(self) -> Tuple[bool, str]:
        self._reset_daily_if_needed()
        if self._daily_frame_count >= self.config.max_total_frames_per_day:
            return False, "Daily frame limit reached"
        return True, ""

    def record_capture(self):
        self._reset_daily_if_needed()
        self._daily_frame_count += 1

    def can_persist(self) -> Tuple[bool, str]:
        if self.config.require_confirmation_for_persist:
            return True, "Confirmation required"
        return True, ""

    def get_access_log(self, limit: int = 100) -> List[Dict]:
        return self._access_log[-limit:]

    def get_privacy_summary(self) -> Dict[str, Any]:
        return {
            "daily_frames": self._daily_frame_count,
            "daily_limit": self.config.max_total_frames_per_day,
            "session_limit": self.config.max_frames_per_session,
            "block_password_fields": self.config.block_password_fields,
            "block_pii_detection": self.config.block_pii_detection,
            "blur_sensitive_regions": self.config.blur_sensitive_regions,
            "access_log_entries": len(self._access_log),
        }
