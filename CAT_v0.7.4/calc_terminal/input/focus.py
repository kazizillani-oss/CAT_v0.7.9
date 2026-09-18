"""
CAT Input Architecture — focus.py
Touch-friendly focus management and virtual/on-screen keyboard adaptation.

Prevents focus jumping, preserves text input focus when Windows touch keyboard appears,
and manages focus restoration on modal/popup dismissals.
"""

from __future__ import annotations

from typing import Optional
from textual.widget import Widget
from textual.widgets import Input, TextArea


class TouchFocusManager:
    """Manages focus state, input activation, and focus restoration for touchscreen interactions."""

    def __init__(self):
        self._last_focused: Optional[Widget] = None
        self._previous_screen_focus: Optional[Widget] = None

    def on_touch_tap_widget(self, target: Optional[Widget]) -> None:
        """Ensure tapped text inputs receive immediate and stable focus."""
        if target is None:
            return

        # Check if the target is an editable input or inside one
        cur = target
        input_widget = None
        while cur is not None:
            if isinstance(cur, (Input, TextArea)):
                input_widget = cur
                break
            cur = getattr(cur, "parent", None)

        if input_widget is not None and getattr(input_widget, "can_focus", True):
            try:
                if not input_widget.has_focus:
                    input_widget.focus()
                self._last_focused = input_widget
            except Exception:
                pass
            return

        # Check if target is inside composer card (prompt glyph, prompt row, card margin)
        cur = target
        inside_composer = False
        is_button = False
        from textual.widgets import Button
        while cur is not None:
            if getattr(cur, "id", None) == "cct-composer":
                inside_composer = True
            if isinstance(cur, (Button,)):
                is_button = True
            cur = getattr(cur, "parent", None)
        if inside_composer and not is_button:
            try:
                app = getattr(target, "app", None)
                if app is not None:
                    composer_input = app.query_one("#cct-input", TextArea)
                    if composer_input is not None and not composer_input.has_focus:
                        composer_input.focus()
                        self._last_focused = composer_input
                        return
            except Exception:
                pass

        if getattr(target, "can_focus", False):
            try:
                self._last_focused = target
            except Exception:
                pass

    def save_focus(self, widget: Optional[Widget]) -> None:
        """Save active focus before opening a modal or popup."""
        self._previous_screen_focus = widget or self._last_focused

    def restore_focus(self) -> None:
        """Restore saved focus after modal or popup dismisses."""
        if self._previous_screen_focus is not None:
            try:
                if self._previous_screen_focus.is_attached and getattr(self._previous_screen_focus, "can_focus", False):
                    self._previous_screen_focus.focus()
            except Exception:
                pass
            self._previous_screen_focus = None
