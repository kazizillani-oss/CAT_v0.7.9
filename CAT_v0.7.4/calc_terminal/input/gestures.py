"""
CAT Input Architecture — gestures.py
Touchscreen gesture integration with CAT Gestures Extension.

Connects touch interactions (tap, double-tap, long-press, swipe) to the
existing Gestures extension without creating duplicate backends.
Works safely even when the Gestures extension is disabled.
"""

from __future__ import annotations

from typing import Optional, Dict, Any
from textual.widget import Widget
from textual.app import App


class GestureBridge:
    """Bridges touch gestures into the CAT Gestures subsystem."""

    @classmethod
    def dispatch_touch_gesture(
        cls,
        trigger: str,
        target: str,
        app: Optional[App] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Dispatch a gesture to calc_terminal.gestures.manager.
        Returns True if an enabled action was triggered, False otherwise.
        """
        try:
            from ..gestures.manager import handle_gesture
            # Map double_tap to double_click for gesture registry compatibility
            mapped_trigger = "double_click" if trigger == "double_tap" else trigger
            return bool(handle_gesture(mapped_trigger, target, app=app, context=context or {}))
        except Exception:
            return False

    @classmethod
    def resolve_target_surface(cls, widget: Optional[Widget]) -> str:
        """Map a Textual widget to a Gestures target surface (editor, chat, file, diff, preview, explorer)."""
        if widget is None:
            return "global"

        cur = widget
        while cur is not None:
            wid = getattr(cur, "id", "") or ""
            cls_name = cur.__class__.__name__

            if wid == "cct-editor" or "EditorPane" in cls_name or "TextArea" in cls_name:
                return "editor"
            if wid == "cct-conversation" or "Conversation" in cls_name or "MessageRow" in cls_name:
                return "chat"
            if wid in ("cct-sidebar", "cct-sidebar-body") or "DirectoryTree" in cls_name or "Explorer" in cls_name:
                return "file"
            if wid == "cct-preview" or "Preview" in cls_name:
                return "preview"
            if "diff" in wid.lower() or "Diff" in cls_name:
                return "diff"

            cur = getattr(cur, "parent", None)

        return "global"
