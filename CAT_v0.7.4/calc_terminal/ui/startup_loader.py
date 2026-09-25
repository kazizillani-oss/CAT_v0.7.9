"""
CCT UI — Startup Progress Loading Animation Overlay
Renders a centered, sleek, modern animated loading screen during CAT CLI startup.
Solves the initial blank-screen delay while heavy workspace, AI core, and extensions initialize.
"""

from __future__ import annotations

import os
import sys
from typing import Optional
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Static
from textual import events

_SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

_HEADER_ART = (
    "[bold #cba6f7]  /\\_/\\  [/bold #cba6f7] [bold #89b4fa]CAT CLI[/bold #89b4fa] [dim #a6adc8]v0.8.0[/dim #a6adc8]\n"
    "[bold #cba6f7] ( o.o ) [/bold #cba6f7] [bold #cdd6f4]AI Coding Agent Terminal[/bold #cdd6f4]\n"
    "[bold #cba6f7]  > ^ <  [/bold #cba6f7] [dim #bac2de]Initializing your workspace...[/dim #bac2de]"
)


class StartupLoadingOverlay(Container):
    """Full-screen centered loading overlay that displays an active spinner,
    dynamic progress bar, and status messages during CAT CLI startup."""

    DEFAULT_CSS = """
    StartupLoadingOverlay {
        dock: top;
        width: 100%;
        height: 100%;
        align: center middle;
        content-align: center middle;
        background: #1e1e2e;
    }

    #cct-startup-card {
        width: 60;
        height: auto;
        min-height: 13;
        border: double #89b4fa;
        background: #181825;
        padding: 1 2;
        align: center middle;
        content-align: center middle;
    }

    #cct-startup-header {
        width: 100%;
        content-align: center middle;
        text-align: center;
        margin-bottom: 1;
    }

    #cct-startup-bar {
        width: 100%;
        content-align: center middle;
        text-align: center;
        margin-bottom: 1;
        color: #89b4fa;
        text-style: bold;
    }

    #cct-startup-status {
        width: 100%;
        content-align: center middle;
        text-align: center;
        margin-bottom: 1;
        color: #cdd6f4;
    }

    #cct-startup-tip {
        width: 100%;
        content-align: center middle;
        text-align: center;
        color: #6c7086;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._frame_idx = 0
        self._progress = 0.08
        self._target_progress = 0.88
        self._is_finishing = False
        self._timer = None

    def compose(self) -> ComposeResult:
        with Vertical(id="cct-startup-card"):
            yield Static(_HEADER_ART, id="cct-startup-header")
            yield Static(self._render_bar(0.08), id="cct-startup-bar")
            yield Static(f"[bold #f9e2af]{_SPINNER_FRAMES[0]}[/] Starting CAT CLI core...", id="cct-startup-status")
            yield Static("[dim]Tap screen or press any key to skip[/dim]", id="cct-startup-tip")

    def on_mount(self) -> None:
        # Immediate dismissal in tests or headless mode
        if (
            os.environ.get("PYTEST_CURRENT_TEST")
            or getattr(self.app, "is_headless", False)
            or getattr(self.app, "_suppress_startup_loader", False)
        ):
            self.remove()
            return

        self._timer = self.set_interval(0.14, self._tick_loader)

    def _render_bar(self, fraction: float) -> str:
        fraction = max(0.0, min(1.0, fraction))
        total_width = 30
        filled = int(round(fraction * total_width))
        empty = total_width - filled
        pct = int(round(fraction * 100))
        return f"[bold #a6e3a1]{'█' * filled}[/][dim #45475a]{'░' * empty}[/] [bold #89b4fa]{pct:3d}%[/]"

    def _get_status_for_progress(self, p: float) -> str:
        if self._is_finishing or p >= 0.98:
            return "[bold #a6e3a1]✓ CAT CLI ready! Launching workspace...[/]"
        elif p < 0.28:
            return "Mounting workspace & environment..."
        elif p < 0.52:
            return "Calibrating touchscreen & finger gestures..."
        elif p < 0.74:
            return "Syncing AI providers & model runtime..."
        else:
            return "Finalizing CAT CLI interactive session..."

    def _tick_loader(self) -> None:
        if self._is_finishing:
            return

        self._frame_idx += 1
        spinner_char = _SPINNER_FRAMES[self._frame_idx % len(_SPINNER_FRAMES)]

        # Smooth asymptotic approach towards target progress
        remaining = self._target_progress - self._progress
        if remaining > 0:
            self._progress += max(0.03, remaining * 0.20)
        self._progress = min(0.92, self._progress)

        status_text = self._get_status_for_progress(self._progress)

        try:
            bar = self.query_one("#cct-startup-bar", Static)
            bar.update(self._render_bar(self._progress))

            status = self.query_one("#cct-startup-status", Static)
            status.update(f"[bold #f9e2af]{spinner_char}[/] {status_text}")
        except Exception:
            pass

    def complete_and_dismiss(self) -> None:
        """Called when CCTApp finishes mounting to seamlessly fade out the overlay."""
        if self._is_finishing:
            return
        self._is_finishing = True

        if self._timer is not None:
            try:
                self._timer.stop()
            except Exception:
                pass

        try:
            bar = self.query_one("#cct-startup-bar", Static)
            bar.update(self._render_bar(1.0))

            status = self.query_one("#cct-startup-status", Static)
            status.update("[bold #a6e3a1]✓ CAT CLI ready! Welcome[/]")
        except Exception:
            pass

        # Allow 180ms for user to perceive 100% completion before smooth removal
        try:
            app = self.app
            if app is not None and getattr(app, "_running", False):
                self.set_timer(0.18, self._remove_overlay)
                return
        except Exception:
            pass
        self._remove_overlay()

    def _remove_overlay(self) -> None:
        try:
            self.remove()
        except Exception:
            pass

    def on_key(self, event: events.Key) -> None:
        """Any key skips the startup animation immediately."""
        self._remove_overlay()

    def on_click(self, event: events.Click) -> None:
        """Any tap/click skips the startup animation immediately."""
        self._remove_overlay()
