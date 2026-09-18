"""
CAT v0.8.a — Vision Context Engine.

Fuses screen frame + code context + project structure + chat history
into a single VisualContext object for AI analysis.
"""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class VisualContext:
    """Complete visual context for AI analysis."""
    frame_b64: str
    frame_meta: Dict[str, Any]
    annotations: List[Dict[str, Any]]
    code_context: Optional[Dict[str, Any]] = None
    project_context: Optional[Dict[str, Any]] = None
    chat_history: List[Dict[str, str]] = field(default_factory=list)
    pointer_telemetry: Optional[Dict[str, Any]] = None
    before_frame_b64: Optional[str] = None
    before_meta: Optional[Dict[str, Any]] = None
    analysis_prompt: str = ""
    created_at: float = 0.0

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()

    def to_dict(self, include_frames: bool = False) -> Dict[str, Any]:
        result = {
            "frame_meta": self.frame_meta,
            "annotations": self.annotations,
            "code_context": self.code_context,
            "project_context": self.project_context,
            "chat_history": self.chat_history[-10:],
            "pointer_telemetry": self.pointer_telemetry,
            "analysis_prompt": self.analysis_prompt,
            "created_at": self.created_at,
            "has_frame": bool(self.frame_b64),
            "has_before_frame": bool(self.before_frame_b64),
        }
        if include_frames:
            result["frame_b64"] = self.frame_b64
            result["before_frame_b64"] = self.before_frame_b64
        return result

    def to_ai_messages(self) -> List[Dict[str, Any]]:
        """Build the message payload for the AI vision model."""
        messages = []
        system_parts = [
            "You are CAT Vision Agent. Analyze the screen state and provide "
            "actionable insights. Be specific about UI elements, errors, and "
            "suggested fixes."
        ]
        if self.code_context:
            system_parts.append(
                f"\nActive file: {self.code_context.get('file_path', 'unknown')}"
            )
            if self.code_context.get("cursor_line"):
                system_parts.append(
                    f"Cursor at line: {self.code_context['cursor_line']}"
                )
        if self.project_context:
            system_parts.append(
                f"Project type: {self.project_context.get('type', 'unknown')}"
            )
        messages.append({"role": "system", "content": "\n".join(system_parts)})

        user_parts = []
        if self.analysis_prompt:
            user_parts.append(self.analysis_prompt)
        else:
            user_parts.append(
                "Analyze this screen capture. Describe what you see, identify "
                "any issues, and suggest next steps."
            )

        if self.pointer_telemetry:
            pt = self.pointer_telemetry
            if pt.get("active_element"):
                user_parts.append(
                    f"\nFocused element: {pt['active_element']}"
                )
            if pt.get("cursor_moving"):
                user_parts.append("\nUser is actively moving the cursor.")

        if self.annotations:
            ann_desc = []
            for ann in self.annotations:
                tool = ann.get("tool", "")
                if tool == "text":
                    ann_desc.append(f"Text annotation: {ann.get('text', '')}")
                elif tool == "arrow":
                    ann_desc.append("Arrow annotation")
                elif tool == "highlight":
                    ann_desc.append("Highlighted region")
                else:
                    ann_desc.append(f"{tool} annotation")
            user_parts.append(
                "\nUser annotations: " + "; ".join(ann_desc)
            )

        user_content = [
            {"type": "text", "text": "\n".join(user_parts)}
        ]

        if self.frame_b64:
            mime = "image/png"
            user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime};base64,{self.frame_b64}",
                    "detail": "high",
                }
            })

        if self.before_frame_b64:
            user_content.append({
                "type": "text",
                "text": "\n--- BEFORE state (for comparison) ---"
            })
            user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{self.before_frame_b64}",
                    "detail": "high",
                }
            })

        messages.append({"role": "user", "content": user_content})
        return messages


class VisionContextEngine:
    """Builds VisualContext from multiple sources."""

    def __init__(self):
        self._code_context: Optional[Dict[str, Any]] = None
        self._project_context: Optional[Dict[str, Any]] = None
        self._chat_history: List[Dict[str, str]] = []
        self._max_chat = 20

    def set_code_context(self, file_path: str = "", content: str = "",
                         cursor_line: int = 0, language: str = "",
                         diagnostics: Optional[List[str]] = None):
        self._code_context = {
            "file_path": file_path,
            "content": content[:5000] if content else "",
            "cursor_line": cursor_line,
            "language": language,
            "diagnostics": diagnostics or [],
        }

    def set_project_context(self, project_type: str = "",
                            structure: Optional[Dict] = None,
                            dependencies: Optional[List[str]] = None):
        self._project_context = {
            "type": project_type,
            "structure": structure or {},
            "dependencies": dependencies or [],
        }

    def add_chat_turn(self, role: str, content: str):
        self._chat_history.append({"role": role, "content": content[:2000]})
        if len(self._chat_history) > self._max_chat:
            self._chat_history = self._chat_history[-self._max_chat:]

    def build_context(self, frame_b64: str,
                      frame_meta: Optional[Dict] = None,
                      annotations: Optional[List[Dict]] = None,
                      pointer_telemetry: Optional[Dict] = None,
                      analysis_prompt: str = "",
                      before_frame_b64: Optional[str] = None,
                      before_meta: Optional[Dict] = None) -> VisualContext:
        return VisualContext(
            frame_b64=frame_b64,
            frame_meta=frame_meta or {},
            annotations=annotations or [],
            code_context=self._code_context,
            project_context=self._project_context,
            chat_history=list(self._chat_history),
            pointer_telemetry=pointer_telemetry,
            analysis_prompt=analysis_prompt,
            before_frame_b64=before_frame_b64,
            before_meta=before_meta,
        )

    def build_visual_debug_prompt(self, error_message: str = "",
                                  user_intent: str = "") -> str:
        parts = [
            "VISUAL DEBUG SESSION — Analyze the current screen state.",
            "The user is experiencing an issue or wants to understand what's on screen.",
        ]
        if error_message:
            parts.append(f"\nError reported: {error_message}")
        if user_intent:
            parts.append(f"\nUser intent: {user_intent}")
        parts.append(
            "\nProvide:\n"
            "1. What you see on screen (UI elements, text, state)\n"
            "2. Any errors, warnings, or anomalies\n"
            "3. Root cause hypothesis\n"
            "4. Specific fix suggestion with code if applicable\n"
            "5. Before/after comparison if previous frame is available"
        )
        return "\n".join(parts)

    def build_code_review_prompt(self, file_path: str = "",
                                 code: str = "") -> str:
        parts = [
            "CODE-VISUAL REVIEW — The screen shows the current code state.",
            "Review the visible code and provide feedback.",
        ]
        if file_path:
            parts.append(f"\nFile: {file_path}")
        if code:
            parts.append(f"\nCode preview:\n```\n{code[:3000]}\n```")
        parts.append(
            "\nAnalyze:\n"
            "1. Code quality and correctness\n"
            "2. Visual rendering issues (if web app)\n"
            "3. UI/UX observations\n"
            "4. Suggested improvements"
        )
        return "\n".join(parts)
