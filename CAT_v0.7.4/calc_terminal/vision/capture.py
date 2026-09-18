"""
CAT v0.8.a — Screen Capture Engine.

Manages getDisplayMedia() / getMedia() capture via the frontend.
The server side handles config, state, and fallback logic.
Actual pixel capture happens in the browser; the server receives
base64-encoded frames via WebSocket or HTTP POST.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class CaptureMode(str, Enum):
    DISPLAY = "display"        # getDisplayMedia — full screen / window / tab
    MEDIA = "media"            # getMedia with displaySurface hints
    AUDIO_VIDEO = "audio_video"
    AUDIO_ONLY = "audio_only"
    TAB = "tab"                # Browser tab capture
    WINDOW = "window"          # Specific window capture
    NONE = "none"              # No capture available


@dataclass
class CaptureConfig:
    mode: CaptureMode = CaptureMode.DISPLAY
    fps: float = 1.0
    quality: int = 85
    max_frames: int = 500
    width: Optional[int] = None
    height: Optional[int] = None
    auto_analyze: bool = True
    change_threshold: float = 0.05
    blur_detection: bool = True
    max_session_minutes: int = 60
    privacy_mode: bool = True
    suppress_notifications: bool = True
    suppress_system_audio: bool = False
    cursor_capture: bool = True
    annotations_enabled: bool = True
    saved_frames_max: int = 20
    context_window_frames: int = 5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "fps": self.fps,
            "quality": self.quality,
            "max_frames": self.max_frames,
            "width": self.width,
            "height": self.height,
            "auto_analyze": self.auto_analyze,
            "change_threshold": self.change_threshold,
            "blur_detection": self.blur_detection,
            "max_session_minutes": self.max_session_minutes,
            "privacy_mode": self.privacy_mode,
            "suppress_notifications": self.suppress_notifications,
            "cursor_capture": self.cursor_capture,
            "annotations_enabled": self.annotations_enabled,
        }


class CaptureEngine:
    """Server-side capture controller.

    The actual screen capture runs in the browser via getDisplayMedia().
    This engine:
      1. Generates the frontend capture config/instructions
      2. Processes incoming frames from the browser
      3. Detects capture capability and falls back gracefully
    """

    def __init__(self, config: CaptureConfig):
        self.config = config
        self.paused = False
        self._initialized = False
        self._frame_callback: Optional[Callable] = None
        self._stats = {
            "frames_received": 0,
            "frames_dropped": 0,
            "bytes_received": 0,
            "errors": 0,
            "started_at": None,
        }

    async def initialize(self):
        self._initialized = True
        self._stats["started_at"] = time.time()

    async def cleanup(self):
        self._initialized = False
        self._frame_callback = None

    def get_capture_config(self) -> Dict[str, Any]:
        """Return config dict for the frontend to initialize getDisplayMedia."""
        display_surface = "monitor"
        if self.config.mode == CaptureMode.TAB:
            display_surface = "browser"
        elif self.config.mode == CaptureMode.WINDOW:
            display_surface = "window"

        return {
            "video": {
                "displaySurface": display_surface,
                "logicalSurface": True,
                "cursor": "always" if self.config.cursor_capture else "never",
                "noiseSuppression": not self.config.suppress_system_audio,
                "suppressLocalAudioPlayback": self.config.suppress_system_audio,
                "selfBrowserSurface": "include",
                "systemAudio": "exclude" if self.config.suppress_system_audio else "include",
                "preferCurrentTab": self.config.mode == CaptureMode.TAB,
            },
            "audio": self.config.mode in (
                CaptureMode.AUDIO_VIDEO, CaptureMode.AUDIO_ONLY),
            "videoConstraints": {
                "width": {"ideal": self.config.width or 1920},
                "height": {"ideal": self.config.height or 1080},
                "frameRate": {"ideal": self.config.fps, "max": self.config.fps * 2},
            },
        }

    def get_capability_report(self) -> Dict[str, Any]:
        """Report what capture modes the frontend should attempt."""
        return {
            "display_api": True,
            "media_api": True,
            "audio_capture": self.config.mode in (
                CaptureMode.AUDIO_VIDEO, CaptureMode.AUDIO_ONLY),
            "tab_capture": True,
            "window_capture": True,
            "frame_rate": self.config.fps,
            "max_resolution": f"{self.config.width or 1920}x{self.config.height or 1080}",
            "browser_requirements": "getDisplayMedia() requires HTTPS or localhost",
        }

    def process_incoming_frame(self, frame_b64: str,
                               timestamp: Optional[float] = None,
                               metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Process a base64 frame received from the browser."""
        if self.paused:
            self._stats["frames_dropped"] += 1
            return {"processed": False, "reason": "paused"}

        self._stats["frames_received"] += 1
        self._stats["bytes_received"] += len(frame_b64)

        return {
            "processed": True,
            "frame_index": self._stats["frames_received"],
            "size_bytes": len(frame_b64),
            "timestamp": timestamp or time.time(),
            "metadata": metadata or {},
        }

    @property
    def stats(self) -> Dict[str, Any]:
        elapsed = 0.0
        if self._stats["started_at"]:
            elapsed = time.time() - self._stats["started_at"]
        return {
            **self._stats,
            "elapsed_seconds": round(elapsed, 2),
            "avg_fps": round(
                self._stats["frames_received"] / max(elapsed, 0.01), 2
            ),
        }
