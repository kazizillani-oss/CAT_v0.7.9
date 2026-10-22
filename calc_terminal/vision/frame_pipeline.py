"""
CAT v0.8.a — Frame Pipeline.

Adaptive sampling, change detection, quality scoring, and frame selection.
The pipeline decides which frames are worth sending to the AI model,
discards duplicates/blur, and maintains a sliding window of context frames.
"""

from __future__ import annotations

import base64
import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ChangeLevel(str, Enum):
    NONE = "none"           # No meaningful change
    MINOR = "minor"         # Small UI update
    MODERATE = "moderate"   # Noticeable change, worth keeping
    MAJOR = "major"         # Significant change, must keep
    CRITICAL = "critical"   # Error/screen change, always keep


@dataclass
class FrameMeta:
    timestamp: float = 0.0
    width: int = 0
    height: int = 0
    pointer_x: float = 0.0
    pointer_y: float = 0.0
    pointer_down: bool = False
    scroll_y: int = 0
    active_element: str = ""
    url: str = ""
    title: str = ""
    annotations: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "width": self.width,
            "height": self.height,
            "pointer_x": self.pointer_x,
            "pointer_y": self.pointer_y,
            "pointer_down": self.pointer_down,
            "scroll_y": self.scroll_y,
            "active_element": self.active_element,
            "url": self.url,
            "title": self.title,
            "annotations": self.annotations,
        }


@dataclass
class FrameEntry:
    frame_b64: str
    meta: FrameMeta
    index: int
    change_level: ChangeLevel
    quality_score: float
    hash: str
    kept: bool = True


class FramePipeline:
    """Manages frame ingestion, change detection, and selection."""

    def __init__(self, config: Any = None):
        self._config = config
        self._frames: List[FrameEntry] = []
        self._last_hash: str = ""
        self._last_change_time: float = 0.0
        self._frame_count: int = 0
        self._change_threshold = getattr(config, "change_threshold", 0.05)
        self._max_frames = getattr(config, "max_frames", 500)
        self._saved_max = getattr(config, "saved_frames_max", 20)
        self._context_window = getattr(config, "context_window_frames", 5)
        self._min_frame_interval = 1.0 / max(getattr(config, "fps", 1.0), 0.1)

    @property
    def frame_count(self) -> int:
        return self._frame_count

    def ingest(self, frame_b64: str,
               meta: Optional[FrameMeta] = None) -> Optional[Dict[str, Any]]:
        """Ingest a frame, detect change, decide whether to keep it.
        Returns frame info dict if the frame was selected, None otherwise.
        """
        if meta is None:
            meta = FrameMeta(timestamp=time.time())

        self._frame_count += 1
        frame_hash = self._compute_hash(frame_b64)
        change_level = self._detect_change(frame_b64, frame_hash)
        quality = self._score_quality(frame_b64, meta)

        if change_level == ChangeLevel.NONE and quality < 0.3:
            return None

        entry = FrameEntry(
            frame_b64=frame_b64,
            meta=meta,
            index=self._frame_count,
            change_level=change_level,
            quality_score=quality,
            hash=frame_hash,
            kept=True,
        )

        if len(self._frames) >= self._max_frames:
            self._prune()

        self._frames.append(entry)
        self._last_hash = frame_hash
        if change_level.value in ("moderate", "major", "critical"):
            self._last_change_time = time.time()

        return {
            "frame_index": entry.index,
            "change_level": change_level.value,
            "quality_score": round(quality, 3),
            "kept": True,
            "meta": meta.to_dict(),
            "total_frames": self._frame_count,
            "stored_frames": len(self._frames),
        }

    def get_context_frames(self, n: Optional[int] = None) -> List[Dict]:
        """Return the last N frames for AI context (without full base64)."""
        n = n or self._context_window
        recent = [f for f in self._frames if f.kept][-n:]
        return [
            {
                "frame_index": f.index,
                "change_level": f.change_level.value,
                "quality_score": round(f.quality_score, 3),
                "meta": f.meta.to_dict(),
                "has_annotations": bool(f.meta.annotations),
            }
            for f in recent
        ]

    def get_latest_frame(self) -> Optional[FrameEntry]:
        kept = [f for f in self._frames if f.kept]
        return kept[-1] if kept else None

    def get_frame_b64(self, frame_index: int) -> Optional[str]:
        for f in self._frames:
            if f.index == frame_index:
                return f.frame_b64
        return None

    def get_best_frame(self) -> Optional[FrameEntry]:
        """Select the best frame for AI analysis: highest change + quality."""
        kept = [f for f in self._frames if f.kept]
        if not kept:
            return None
        ranked = sorted(
            kept,
            key=lambda f: (
                list(ChangeLevel).index(f.change_level) * 10
                + f.quality_score
            ),
            reverse=True,
        )
        return ranked[0]

    def get_summary(self) -> Dict[str, Any]:
        kept = [f for f in self._frames if f.kept]
        return {
            "total_frames": self._frame_count,
            "stored_frames": len(self._frames),
            "kept_frames": len(kept),
            "change_levels": {
                level.value: sum(
                    1 for f in kept if f.change_level == level
                )
                for level in ChangeLevel
            },
            "avg_quality": round(
                sum(f.quality_score for f in kept) / max(len(kept), 1), 3
            ),
            "context_window": self._context_window,
        }

    def clear(self):
        self._frames.clear()
        self._last_hash = ""
        self._frame_count = 0

    def _compute_hash(self, frame_b64: str) -> str:
        sample = frame_b64[:4096] if len(frame_b64) > 4096 else frame_b64
        return hashlib.md5(sample.encode("ascii", errors="ignore")).hexdigest()

    def _detect_change(self, frame_b64: str, frame_hash: str) -> ChangeLevel:
        if not self._last_hash:
            return ChangeLevel.MAJOR

        if frame_hash == self._last_hash:
            return ChangeLevel.NONE

        similarity = self._compare_hashes(self._last_hash, frame_hash)
        if similarity > 0.97:
            return ChangeLevel.NONE
        elif similarity > 0.90:
            return ChangeLevel.MINOR
        elif similarity > 0.75:
            return ChangeLevel.MODERATE
        elif similarity > 0.50:
            return ChangeLevel.MAJOR
        else:
            return ChangeLevel.CRITICAL

    def _compare_hashes(self, h1: str, h2: str) -> float:
        """Compare two MD5 hashes by hex char similarity."""
        if not h1 or not h2 or len(h1) != len(h2):
            return 0.0
        matches = sum(a == b for a, b in zip(h1, h2))
        return matches / len(h1)

    def _score_quality(self, frame_b64: str, meta: FrameMeta) -> float:
        """Score frame quality 0.0-1.0. Higher = clearer, more useful."""
        score = 0.5
        data_len = len(frame_b64)
        if data_len < 1000:
            return 0.1
        if 5000 < data_len < 500000:
            score += 0.15
        elif data_len > 500000:
            score += 0.1
        if meta.width > 800 and meta.height > 600:
            score += 0.15
        elif meta.width > 400 and meta.height > 300:
            score += 0.05
        if meta.pointer_down:
            score += 0.1
        if meta.active_element:
            score += 0.1
        if meta.annotations:
            score += 0.1
        return min(score, 1.0)

    def _prune(self):
        """Remove oldest low-priority frames when at capacity."""
        if len(self._frames) <= self._max_frames:
            return
        removable = [
            f for f in self._frames
            if f.change_level in (ChangeLevel.NONE, ChangeLevel.MINOR)
        ]
        removable.sort(key=lambda f: f.index)
        to_remove = len(self._frames) - self._max_frames + 50
        for f in removable[:to_remove]:
            self._frames.remove(f)
        if len(self._frames) > self._max_frames:
            self._frames = self._frames[-self._max_frames:]
