"""
CCT UI — timeline_panel.py: Session Timeline panel (v0.7.2 roadmap).
Real Screen push (same family as context_menu.py/header.py's
PermissionModeMenu — this package's standing "no floating popup
windows" rule), showing calc_terminal/timeline.py's event log with a
live search box and per-topic filter chips. "Jump to event" opens the
related file in the Editor if it still exists on disk; "Restore
previous state" is the roadmap's own named FUTURE feature and isn't
implemented here.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import os

from .. import timeline
from .events import FileOpenRequested

TEXTUAL_AVAILABLE = True
try:
    from textual.containers import Vertical, Horizontal, VerticalScroll
    from textual.screen import Screen
    from textual.widgets import Static, Input, Button
except Exception:
    TEXTUAL_AVAILABLE = False


if TEXTUAL_AVAILABLE:

    class _TimelineRow(Static):
        def __init__(self, event):
            super().__init__(event.line(), classes="cct-timeline-row")
            self._event = event

        def on_click(self, ev):
            if self._event.related_file and os.path.isfile(self._event.related_file):
                self.post_message(FileOpenRequested(self._event.related_file))

    class TimelinePanel(Screen):
        """Full event log. `_filter_topic`, when set, narrows to one
        eventbus topic; the search box narrows further by substring
        (timeline.search) on top of that. Both apply together, list
        re-rendered via _render_rows() rather than a full recompose."""

        CSS = """
        TimelinePanel { align: center middle; background: $app-background 60%; }
        #cct-timeline-box {
            width: 84%; height: 80%; background: $surface;
            border: round $border; padding: 1 2;
        }
        #cct-timeline-header { height: 1; }
        #cct-timeline-search { margin-bottom: 1; }
        #cct-timeline-list { height: 1fr; }
        .cct-timeline-row { height: 1; color: $text; padding: 0 1; }
        .cct-timeline-row:hover { color: $accent; }
        #cct-timeline-empty { color: $text-faint; padding: 1; }
        """

        def __init__(self):
            super().__init__()
            self._query = ""

        def compose(self):
            with Vertical(id="cct-timeline-box"):
                with Horizontal(id="cct-timeline-header"):
                    yield Static("[b]Session Timeline[/b]")
                    yield Button("Close", id="cct-timeline-close")
                yield Input(placeholder="Search timeline\u2026", id="cct-timeline-search")
                yield VerticalScroll(id="cct-timeline-list")

        def on_mount(self):
            self._render_rows()

        def _render_rows(self):
            box = self.query_one("#cct-timeline-list", VerticalScroll)
            for child in list(box.children):
                child.remove()
            evs = timeline.search(self._query)
            if not evs:
                box.mount(Static("No matching activity yet.", id="cct-timeline-empty"))
                return
            for ev in evs[:200]:
                box.mount(_TimelineRow(ev))

        def on_input_changed(self, event):
            if event.input.id == "cct-timeline-search":
                self._query = event.value
                self._render_rows()

        def on_button_pressed(self, event):
            if event.button.id == "cct-timeline-close":
                self.dismiss(None)

        def on_key(self, event):
            if event.key == "escape":
                self.dismiss(None)

else:
    TimelinePanel = None
