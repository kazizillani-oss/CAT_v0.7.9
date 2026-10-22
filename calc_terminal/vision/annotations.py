"""
CAT v0.8.a — Annotation Engine.

Handles pen, arrow, rect, circle, text, and highlight annotations.
Manages undo/redo stack, serialization, and frame annotation binding.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class AnnotationTool(str, Enum):
    PEN = "pen"
    ARROW = "arrow"
    RECT = "rect"
    CIRCLE = "circle"
    TEXT = "text"
    HIGHLIGHT = "highlight"
    CROSSHAIR = "crosshair"
    ERASER = "eraser"


@dataclass
class Color:
    r: int = 255
    g: int = 0
    b: int = 0
    a: float = 1.0

    def to_css(self) -> str:
        return f"rgba({self.r},{self.g},{self.b},{self.a})"

    def to_hex(self) -> str:
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}"

    def to_dict(self) -> Dict[str, Any]:
        return {"r": self.r, "g": self.g, "b": self.b, "a": self.a}

    @classmethod
    def from_hex(cls, hex_str: str) -> "Color":
        h = hex_str.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) == 6:
            return cls(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        elif len(h) == 8:
            return cls(
                int(h[0:2], 16), int(h[2:4], 16),
                int(h[4:6], 16), int(h[6:8], 16) / 255.0
            )
        return cls()

    @classmethod
    def from_dict(cls, d: Dict) -> "Color":
        return cls(d.get("r", 255), d.get("g", 0), d.get("b", 0), d.get("a", 1.0))


@dataclass
class Annotation:
    id: str
    tool: AnnotationTool
    points: List[Tuple[float, float]]
    color: Color
    line_width: float
    text: str = ""
    text_position: Optional[Tuple[float, float]] = None
    opacity: float = 1.0
    created_at: float = 0.0
    frame_index: int = -1
    bounding_box: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tool": self.tool.value,
            "points": [[p[0], p[1]] for p in self.points],
            "color": self.color.to_dict(),
            "line_width": self.line_width,
            "text": self.text,
            "text_position": list(self.text_position) if self.text_position else None,
            "opacity": self.opacity,
            "created_at": self.created_at,
            "frame_index": self.frame_index,
            "bounding_box": self.bounding_box,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "Annotation":
        return cls(
            id=d.get("id", str(uuid.uuid4())),
            tool=AnnotationTool(d.get("tool", "pen")),
            points=[(p[0], p[1]) for p in d.get("points", [])],
            color=Color.from_dict(d.get("color", {})),
            line_width=d.get("line_width", 3),
            text=d.get("text", ""),
            text_position=tuple(d["text_position"]) if d.get("text_position") else None,
            opacity=d.get("opacity", 1.0),
            created_at=d.get("created_at", 0.0),
            frame_index=d.get("frame_index", -1),
            bounding_box=d.get("bounding_box"),
        )


class AnnotationEngine:
    """Manages annotation creation, undo/redo, and serialization."""

    def __init__(self):
        self.annotations: List[Annotation] = []
        self._undo_stack: List[Annotation] = []
        self._redo_stack: List[Annotation] = []
        self._max_undo = 50
        self._default_color = Color(255, 0, 0)
        self._default_width = 3.0

    def set_default_color(self, color: Color):
        self._default_color = color

    def set_default_width(self, width: float):
        self._default_width = width

    def add_annotation(self, tool: AnnotationTool,
                       points: List[Tuple[float, float]],
                       color: Optional[Color] = None,
                       line_width: Optional[float] = None,
                       text: str = "",
                       frame_index: int = -1,
                       annotation_id: Optional[str] = None) -> Annotation:
        ann = Annotation(
            id=annotation_id or str(uuid.uuid4()),
            tool=tool,
            points=points,
            color=color or self._default_color,
            line_width=line_width or self._default_width,
            text=text,
            text_position=points[0] if points else None,
            created_at=time.time(),
            frame_index=frame_index,
            bounding_box=self._compute_bbox(points),
        )
        self.annotations.append(ann)
        self._undo_stack.append(ann)
        if len(self._undo_stack) > self._max_undo:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        return ann

    def undo(self) -> Optional[Annotation]:
        if not self._undo_stack:
            return None
        ann = self._undo_stack.pop()
        self.annotations = [a for a in self.annotations if a.id != ann.id]
        self._redo_stack.append(ann)
        return ann

    def redo(self) -> Optional[Annotation]:
        if not self._redo_stack:
            return None
        ann = self._redo_stack.pop()
        self.annotations.append(ann)
        self._undo_stack.append(ann)
        return ann

    def clear(self):
        self.annotations.clear()
        self._undo_stack.clear()
        self._redo_stack.clear()

    def clear_frame(self, frame_index: int):
        self.annotations = [
            a for a in self.annotations if a.frame_index != frame_index
        ]

    def update_annotation(self, annotation_id: str, **kwargs) -> Optional[Annotation]:
        for ann in self.annotations:
            if ann.id == annotation_id:
                for key, val in kwargs.items():
                    if key == "color" and isinstance(val, dict):
                        ann.color = Color.from_dict(val)
                    elif key == "points" and isinstance(val, list):
                        ann.points = [(p[0], p[1]) for p in val]
                        ann.bounding_box = self._compute_bbox(ann.points)
                    elif hasattr(ann, key):
                        setattr(ann, key, val)
                return ann
        return None

    def delete_annotation(self, annotation_id: str) -> bool:
        before = len(self.annotations)
        self.annotations = [a for a in self.annotations if a.id != annotation_id]
        return len(self.annotations) < before

    def get_annotations_for_frame(self, frame_index: int) -> List[Dict]:
        return [a.to_dict() for a in self.annotations if a.frame_index == frame_index]

    def get_pointer_annotation(self, x: float, y: float,
                               radius: float = 15.0) -> Optional[Annotation]:
        """Find annotation near a pointer position."""
        for ann in reversed(self.annotations):
            if ann.tool == AnnotationTool.CROSSHAIR:
                continue
            if ann.bounding_box:
                bb = ann.bounding_box
                if (bb["x"] - radius <= x <= bb["x"] + bb["width"] + radius and
                        bb["y"] - radius <= y <= bb["y"] + bb["height"] + radius):
                    return ann
        return None

    def to_list(self) -> List[Dict]:
        return [a.to_dict() for a in self.annotations]

    def from_list(self, data: List[Dict]):
        self.clear()
        for d in data:
            self.annotations.append(Annotation.from_dict(d))
        self._undo_stack = list(self.annotations)
        self._redo_stack.clear()

    def _compute_bbox(self, points: List[Tuple[float, float]]) -> Optional[Dict[str, float]]:
        if not points:
            return None
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        return {
            "x": min(xs), "y": min(ys),
            "width": max(xs) - min(xs),
            "height": max(ys) - min(ys),
        }

    def export_svg(self, width: int = 1920, height: int = 1080) -> str:
        lines = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        ]
        for ann in self.annotations:
            color_hex = ann.color.to_hex()
            opacity = ann.opacity
            if ann.tool == AnnotationTool.PEN and len(ann.points) >= 2:
                path_d = "M " + " L ".join(
                    f"{p[0]:.1f},{p[1]:.1f}" for p in ann.points
                )
                lines.append(
                    f'  <path d="{path_d}" stroke="{color_hex}" '
                    f'stroke-width="{ann.line_width}" fill="none" '
                    f'opacity="{opacity}" stroke-linecap="round"/>'
                )
            elif ann.tool == AnnotationTool.ARROW and len(ann.points) >= 2:
                x1, y1 = ann.points[0]
                x2, y2 = ann.points[-1]
                lines.append(
                    f'  <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                    f'stroke="{color_hex}" stroke-width="{ann.line_width}" '
                    f'opacity="{opacity}" marker-end="url(#arrowhead)"/>'
                )
            elif ann.tool == AnnotationTool.RECT and len(ann.points) >= 2:
                x1, y1 = ann.points[0]
                x2, y2 = ann.points[-1]
                lines.append(
                    f'  <rect x="{min(x1,x2):.1f}" y="{min(y1,y2):.1f}" '
                    f'width="{abs(x2-x1):.1f}" height="{abs(y2-y1):.1f}" '
                    f'stroke="{color_hex}" stroke-width="{ann.line_width}" '
                    f'fill="none" opacity="{opacity}"/>'
                )
            elif ann.tool == AnnotationTool.CIRCLE and len(ann.points) >= 2:
                x1, y1 = ann.points[0]
                x2, y2 = ann.points[-1]
                cx = (x1 + x2) / 2
                cy = (y1 + y2) / 2
                rx = abs(x2 - x1) / 2
                ry = abs(y2 - y1) / 2
                lines.append(
                    f'  <ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" '
                    f'stroke="{color_hex}" stroke-width="{ann.line_width}" '
                    f'fill="none" opacity="{opacity}"/>'
                )
            elif ann.tool == AnnotationTool.TEXT and ann.text_position:
                tx, ty = ann.text_position
                escaped = ann.text.replace("&", "&amp;").replace("<", "&lt;")
                lines.append(
                    f'  <text x="{tx:.1f}" y="{ty:.1f}" fill="{color_hex}" '
                    f'font-size="{ann.line_width * 5:.0f}" opacity="{opacity}">'
                    f'{escaped}</text>'
                )
            elif ann.tool == AnnotationTool.HIGHLIGHT and len(ann.points) >= 2:
                x1, y1 = ann.points[0]
                x2, y2 = ann.points[-1]
                highlight_color = Color(ann.color.r, ann.color.g, ann.color.b, 0.3)
                lines.append(
                    f'  <rect x="{min(x1,x2):.1f}" y="{min(y1,y2):.1f}" '
                    f'width="{abs(x2-x1):.1f}" height="{abs(y2-y1):.1f}" '
                    f'fill="{highlight_color.to_hex()}" opacity="{opacity}"/>'
                )
        lines.append("</svg>")
        return "\n".join(lines)
