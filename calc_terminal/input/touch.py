"""
CAT Input Architecture — touch.py
High-fidelity touch interaction handling for terminal applications.

Implements:
1. TouchTapRecognizer:
   - Fuzzy coordinate matching (2-cell tolerance) solving Textual's click-drop bug.
   - Double-tap detection with relaxed offset tolerance.
   - Long-press recognition for touch context actions.
2. TouchScrollHandler:
   - Natural finger drag-to-scroll across all containers (chat, file tree, editor, modals, settings, model list).
   - Click suppression during drag-scrolling so lifting a finger never causes accidental clicks.
   - Kinetic flick/momentum scrolling with smooth deceleration.
"""

from __future__ import annotations

import time
import math
from typing import Optional, Tuple, Any, Callable
from textual import events
from textual.widget import Widget
from textual.containers import ScrollableContainer, VerticalScroll
from textual.scroll_view import ScrollView

# Tolerances & Thresholds (Calibrated for human finger pads on laptop touchscreens)
TAP_MAX_DISTANCE = 4.0         # Manhattan distance in cells (finger jitter allowance)
TAP_MAX_DURATION = 0.65        # Max seconds between down and up for a single tap
DOUBLE_TAP_MAX_DELAY = 0.40    # Max seconds between taps for double-tap
DOUBLE_TAP_MAX_DISTANCE = 4.0  # Max distance between consecutive taps
LONG_PRESS_DURATION = 0.55     # Seconds required to trigger long-press
SCROLL_DRAG_THRESHOLD = 3.0    # Movement cells required to switch into scroll mode


class TouchTapRecognizer:
    """Detects clean taps, double-taps, and long-presses despite finger jitter."""

    def __init__(self, on_tap: Optional[Callable[[Widget, events.MouseUp, int], None]] = None,
                 on_long_press: Optional[Callable[[Widget, Tuple[int, int]], None]] = None):
        self.on_tap = on_tap
        self.on_long_press = on_long_press

        self._active = False
        self._down_time = 0.0
        self._down_pos: Tuple[int, int] = (0, 0)
        self._down_screen_pos: Tuple[int, int] = (0, 0)
        self._down_widget: Optional[Widget] = None

        # Double-click / chained tap state
        self._last_tap_time = 0.0
        self._last_tap_pos: Tuple[int, int] = (0, 0)
        self._last_tap_widget: Optional[Widget] = None
        self._chain = 1

        # Long-press timer tracking
        self._long_press_triggered = False

    def on_mouse_down(self, widget: Optional[Widget], event: events.MouseDown) -> None:
        """Handle finger contact."""
        if getattr(event, "button", 1) != 1:
            return
        now = time.monotonic()
        self._active = True
        self._down_time = now
        self._down_pos = (event.x, event.y)
        self._down_screen_pos = (getattr(event, "screen_x", event.x), getattr(event, "screen_y", event.y))
        self._down_widget = widget
        self._long_press_triggered = False

    def on_mouse_move(self, event: events.MouseMove) -> bool:
        """Check if movement exceeds tap jitter threshold."""
        if not self._active:
            return False
        cur_screen = (getattr(event, "screen_x", event.x), getattr(event, "screen_y", event.y))
        dx = abs(cur_screen[0] - self._down_screen_pos[0])
        dy = abs(cur_screen[1] - self._down_screen_pos[1])
        if dx + dy > TAP_MAX_DISTANCE:
            # Finger moved beyond tap threshold — no longer a tap
            self._active = False
            return False
        return True

    def check_long_press(self) -> bool:
        """Poll or timer check for long-press trigger."""
        if not self._active or self._long_press_triggered or self._down_widget is None:
            return False
        now = time.monotonic()
        if now - self._down_time >= LONG_PRESS_DURATION:
            self._long_press_triggered = True
            self._active = False  # Suppress normal tap on release
            if self.on_long_press and self._down_widget is not None:
                try:
                    self.on_long_press(self._down_widget, self._down_screen_pos)
                except Exception:
                    pass
            return True
        return False

    def on_mouse_up(self, up_widget: Optional[Widget], event: events.MouseUp) -> Tuple[bool, int, Optional[Widget]]:
        """
        Handle finger lift.
        Returns: (is_tap, click_chain, resolved_target_widget)
        """
        if not self._active or self._long_press_triggered:
            self._active = False
            return False, 1, None

        self._active = False
        now = time.monotonic()
        duration = now - self._down_time

        if duration > TAP_MAX_DURATION:
            return False, 1, None

        cur_screen = (getattr(event, "screen_x", event.x), getattr(event, "screen_y", event.y))
        dx = abs(cur_screen[0] - self._down_screen_pos[0])
        dy = abs(cur_screen[1] - self._down_screen_pos[1])

        if dx + dy > TAP_MAX_DISTANCE:
            return False, 1, None

        # Resolve best target widget:
        # If up_widget is down_widget, exact match.
        # Otherwise, check if down_widget is an interactive widget or descendant/ancestor
        target = self._resolve_target(self._down_widget, up_widget)
        if target is None:
            return False, 1, None

        # Determine chain (double-tap)
        dist_from_last = (abs(cur_screen[0] - self._last_tap_pos[0]) +
                          abs(cur_screen[1] - self._last_tap_pos[1]))
        if (now - self._last_tap_time <= DOUBLE_TAP_MAX_DELAY and
                dist_from_last <= DOUBLE_TAP_MAX_DISTANCE and
                (self._last_tap_widget is target or self._is_related(self._last_tap_widget, target))):
            self._chain += 1
        else:
            self._chain = 1

        self._last_tap_time = now
        self._last_tap_pos = cur_screen
        self._last_tap_widget = target

        if self.on_tap:
            try:
                self.on_tap(target, event, self._chain)
            except Exception:
                pass

        return True, self._chain, target

    def cancel(self) -> None:
        """Cancel tap recognition (e.g. when drag-to-scroll takes over)."""
        self._active = False
        self._long_press_triggered = False

    @staticmethod
    def _is_related(w1: Optional[Widget], w2: Optional[Widget]) -> bool:
        if w1 is None or w2 is None:
            return False
        if w1 is w2:
            return True
        # Check parent hierarchy
        cur = w1
        while cur is not None:
            if cur is w2:
                return True
            cur = getattr(cur, "parent", None)
        cur = w2
        while cur is not None:
            if cur is w1:
                return True
            cur = getattr(cur, "parent", None)
        return False

    @classmethod
    def _resolve_target(cls, down_w: Optional[Widget], up_w: Optional[Widget]) -> Optional[Widget]:
        if down_w is None:
            return up_w
        if up_w is None:
            return down_w
        if down_w is up_w:
            return down_w

        # Check comprehensive interactive types and focusable controls
        from textual.widgets import (
            Button, Input, TextArea, Tab, Tabs, Select, OptionList,
            Checkbox, RadioSet, RadioButton, Switch, Tree, ListItem, ListView
        )
        interactive_types = (
            Button, Input, TextArea, Tab, Tabs, Select, OptionList,
            Checkbox, RadioSet, RadioButton, Switch, Tree, ListItem, ListView
        )

        def _find_interactive(w: Optional[Widget]) -> Optional[Widget]:
            cur = w
            while cur is not None:
                if isinstance(cur, interactive_types):
                    return cur
                if hasattr(cur, "press") or hasattr(cur, "action_press"):
                    return cur
                if getattr(cur, "can_focus", False) and not isinstance(cur, (ScrollableContainer, VerticalScroll, ScrollView)):
                    return cur
                # Check for standard interactive button/item CSS classes
                classes = getattr(cur, "classes", set())
                if any(c in classes for c in ("btn", "button", "clickable", "interactive", "nav-item")):
                    return cur
                cur = getattr(cur, "parent", None)
            return None

        # Prioritize down_widget first (the element the finger touched initially)
        down_target = _find_interactive(down_w)
        if down_target is not None:
            return down_target

        up_target = _find_interactive(up_w)
        if up_target is not None:
            return up_target

        # Fallback to down_w (what the user aimed at initially)
        return down_w


class TouchScrollHandler:
    """Manages finger drag-to-scroll with kinetic momentum across any scroll container."""

    def __init__(self):
        self._is_scrolling = False
        self._container: Optional[Widget] = None
        self._down_screen_y = 0.0
        self._down_screen_x = 0.0
        self._last_move_y = 0.0
        self._last_move_time = 0.0
        self._initial_scroll_y = 0.0
        self._velocity_y = 0.0  # cells per second

    @property
    def is_scrolling(self) -> bool:
        return self._is_scrolling

    def on_mouse_down(self, target_widget: Optional[Widget], event: events.MouseDown) -> bool:
        """Start tracking potential touch drag."""
        if getattr(event, "button", 1) != 1:
            return False

        self._container = self._find_scroll_container(target_widget)
        self._is_scrolling = False
        self._down_screen_y = float(getattr(event, "screen_y", event.y))
        self._down_screen_x = float(getattr(event, "screen_x", event.x))
        self._last_move_y = self._down_screen_y
        self._last_move_time = time.monotonic()
        self._velocity_y = 0.0

        if self._container is not None:
            self._initial_scroll_y = float(getattr(self._container, "scroll_y", 0.0))
            return True
        return False

    def on_mouse_move(self, event: events.MouseMove) -> bool:
        """Handle finger movement and perform drag scrolling."""
        if self._container is None:
            return False

        now = time.monotonic()
        cur_y = float(getattr(event, "screen_y", event.y))
        dt = max(0.001, now - self._last_move_time)

        dy_total = cur_y - self._down_screen_y
        step_dy = cur_y - self._last_move_y

        if not self._is_scrolling:
            # Check threshold to enter drag-scroll mode
            if abs(dy_total) >= SCROLL_DRAG_THRESHOLD:
                self._is_scrolling = True

        if self._is_scrolling:
            # Invert delta: dragging finger UP scrolls content DOWN
            scroll_delta = -step_dy
            self._apply_scroll(self._container, scroll_delta)

            # Update velocity moving average
            instant_velocity = -step_dy / dt
            self._velocity_y = 0.6 * self._velocity_y + 0.4 * instant_velocity

            self._last_move_y = cur_y
            self._last_move_time = now
            return True

        return False

    def on_mouse_up(self, event: events.MouseUp) -> bool:
        """Finish drag-scroll and trigger flick momentum if applicable."""
        was_scrolling = self._is_scrolling
        container = self._container

        self._is_scrolling = False
        self._container = None

        if was_scrolling and container is not None:
            # Apply momentum if released with velocity (> 8 cells/sec)
            if abs(self._velocity_y) > 8.0:
                self._apply_momentum(container, self._velocity_y)
            return True

        return False

    @classmethod
    def _find_scroll_container(cls, start_widget: Optional[Widget]) -> Optional[Widget]:
        """Find the nearest scrollable ancestor with actual overflowing content."""
        if start_widget is None:
            return None

        # Single-line text input fields shouldn't trigger drag-scroll (reserved for caret / selection)
        from textual.widgets import Input
        if isinstance(start_widget, Input):
            return None

        cur = start_widget
        while cur is not None:
            # Check for scrollable containers that actually have scrollable content
            if isinstance(cur, (ScrollableContainer, VerticalScroll, ScrollView)):
                if getattr(cur, "max_scroll_y", 0) > 0:
                    return cur
            cur = getattr(cur, "parent", None)
        return None

    @classmethod
    def _apply_scroll(cls, container: Widget, delta_y: float) -> None:
        """Apply vertical scroll offset."""
        try:
            if hasattr(container, "scroll_relative"):
                container.scroll_relative(y=delta_y, animate=False)
            elif hasattr(container, "scroll_to"):
                new_y = max(0.0, getattr(container, "scroll_y", 0.0) + delta_y)
                container.scroll_to(y=new_y, animate=False)
        except Exception:
            pass

    @classmethod
    def _apply_momentum(cls, container: Widget, initial_velocity: float) -> None:
        """Apply smooth kinetic flick decay."""
        try:
            # Cap momentum travel to prevent runaway scrolls
            travel = math.copysign(min(18.0, abs(initial_velocity) * 0.18), initial_velocity)
            if hasattr(container, "scroll_relative"):
                container.scroll_relative(y=travel, animate=True, duration=0.22, easing="out_cubic")
        except Exception:
            pass
