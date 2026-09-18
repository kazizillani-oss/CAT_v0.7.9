"""
CCT UI — activity_stream_panel.py: Activity Stream panel (v0.7.6).
A Textual-based embedded panel that shows real-time tool execution
activity from the event_stream. Displays a live-scrolling list of
recent events with timestamps, icons, and color-coded status.

Each event is formatted with:
  - Human-readable timestamp
  - Event-type icon/label
  - Short description from event data
  - Color: green (success), red (failure), yellow (in-progress)

Auto-refreshes every 2 seconds via a Textual timer. Max 50 visible
items in a scrollable container.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import datetime
import time

TEXTUAL_AVAILABLE = True
try:
    from textual.containers import Vertical, ScrollView
    from textual.widgets import Static
except Exception:
    TEXTUAL_AVAILABLE = False

if TEXTUAL_AVAILABLE:
    from . import theme_css
    from .. import event_stream as _event_stream_mod


    _EVENT_ICONS = {
        _event_stream_mod.TOOL_STARTED:      ("\U0001f527", "[TOOL]",       "yellow"),
        _event_stream_mod.TOOL_RESULT:       ("\u2705",    "[DONE]",       "green"),
        _event_stream_mod.FILE_CREATED:      ("\u2795",    "[CREATE]",     "green"),
        _event_stream_mod.FILE_EDITED:       ("\u270f\ufe0f", "[EDIT]",     "yellow"),
        _event_stream_mod.FILE_DELETED:      ("\u2716\ufe0f", "[DELETE]",   "red"),
        _event_stream_mod.FILE_MOVED:        ("\u2b05\ufe0f", "[MOVE]",     "yellow"),
        _event_stream_mod.COMMAND_STARTED:   ("\u25b6\ufe0f", "[CMD]",      "yellow"),
        _event_stream_mod.COMMAND_RESULT:    ("\u2714\ufe0f", "[CMD_DONE]", "green"),
        _event_stream_mod.AGENT_STARTED:     ("\U0001f916", "[AGENT]",      "yellow"),
        _event_stream_mod.AGENT_COMPLETED:   ("\U0001f3c6", "[AGENT_DONE]", "green"),
        _event_stream_mod.AGENT_FAILED:      ("\u274c",    "[AGENT_FAIL]", "red"),
        _event_stream_mod.MEMORY_CREATED:    ("\U0001f4be", "[MEM]",       "green"),
        _event_stream_mod.MEMORY_UPDATED:    ("\U0001f504", "[MEM_UPD]",   "yellow"),
        _event_stream_mod.MEMORY_DELETED:    ("\U0001f5d1\ufe0f", "[MEM_DEL]", "red"),
        _event_stream_mod.MEMORY_READ:       ("\U0001f4d6", "[MEM_READ]",  "text-muted"),
        _event_stream_mod.MODEL_RESPONSE:    ("\U0001f4ac", "[RESP]",      "text-muted"),
        _event_stream_mod.TOOL_REQUEST:      ("\U0001f4e1", "[REQ]",       "yellow"),
        _event_stream_mod.SESSION_CLEARED:   ("\U0001f5d1\ufe0f", "[CLEAR]", "red"),
        _event_stream_mod.CONTEXT_SWITCHED:  ("\U0001f504", "[CTX]",       "yellow"),
    }

    _MAX_VISIBLE = 50


    def _fmt_ts(ts):
        """Format a UNIX timestamp into a short human-readable string."""
        try:
            dt = datetime.datetime.fromtimestamp(ts)
            now = datetime.datetime.now()
            if dt.date() == now.date():
                return dt.strftime("%H:%M:%S")
            return dt.strftime("%m-%d %H:%M")
        except Exception:
            return "??:??:??"


    class ActivityStreamPanel(Static):
        """Embedded activity stream widget — mount this inside a
        layout to get a live scrolling feed of event_stream events."""

        CSS = """
        ActivityStreamPanel {
            height: 1fr;
            width: 1fr;
            background: $surface;
            border: round $border;
            padding: 0;
            overflow: hidden;
        }
        #as-header {
            height: 1;
            padding: 0 1;
            border-bottom: solid $border;
            background: $surface-alt;
        }
        #as-header Label {
            text-style: bold;
        }
        #as-body {
            height: 1fr;
            overflow-y: auto;
            padding: 0 1;
        }
        .as-event {
            height: auto;
            min-height: 1;
            padding: 0 0;
            width: 1fr;
        }
        .as-event:hover {
            background: $surface-alt;
        }
        #as-empty {
            height: 3;
            padding: 1 0;
            color: $text-faint;
            text-align: center;
        }
        #as-footer {
            height: 1;
            padding: 0 1;
            border-top: solid $border;
            color: $text-faint;
        }
        """

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self._refresh_timer = None
            self._last_count = 0

        def compose(self):
            with Vertical(id="as-stream-wrap"):
                yield Static(" \U0001f4ca  Activity Stream", id="as-header")
                yield ScrollView(id="as-body")
                yield Static("", id="as-footer")

        def on_mount(self):
            from .. import event_stream
            self._event_stream = event_stream.stream
            self._refresh_timer = self.set_interval(2.0, self.refresh_stream)
            self.refresh_stream()

        def on_unmount(self):
            if self._refresh_timer is not None:
                self._refresh_timer.stop()
                self._refresh_timer = None

        def refresh_stream(self):
            """Poll recent events from event_stream and update the display."""
            try:
                from .. import event_stream
                events = event_stream.stream.get_recent(limit=_MAX_VISIBLE)
            except Exception:
                return

            if not events:
                try:
                    body = self.query_one("#as-body", ScrollView)
                    if not body.children:
                        body.mount(
                            Static("No activity yet.", id="as-empty"))
                except Exception:
                    pass
                return

            if len(events) == self._last_count:
                return
            self._last_count = len(events)

            try:
                body = self.query_one("#as-body", ScrollView)
            except Exception:
                return

            for child in list(body.children):
                child.remove()

            for ev in reversed(events[-_MAX_VISIBLE:]):
                body.mount(Static(self._format_event(ev), classes="as-event"))

            try:
                footer = self.query_one("#as-footer", Static)
                footer.update(f"  {len(events)} event{'s' if len(events) != 1 else ''}")
            except Exception:
                pass

            try:
                body.scroll_end(animate=False)
            except Exception:
                pass

        def _format_event(self, ev):
            """Format a single event as a Rich-markup string."""
            icon_tuple = _EVENT_ICONS.get(
                ev.event_type, ("\u2753", f"[{ev.event_type}]", "text-muted"))
            emoji, label, color = icon_tuple

            ts_str = _fmt_ts(ev.timestamp)

            desc = ev.data.get("description", "")
            if not desc:
                path = ev.data.get("path") or ev.data.get("file", "")
                tool = ev.data.get("tool", "")
                cmd = ev.data.get("command", "")
                agent = ev.data.get("agent", "")
                if path:
                    desc = str(path)
                elif tool:
                    desc = str(tool)
                elif cmd:
                    desc = str(cmd)[:40]
                elif agent:
                    desc = str(agent)
                else:
                    desc = ev.event_type

            try:
                hex_color = theme_css.current_hex(color)
            except Exception:
                hex_color = theme_css.current_hex("text-muted")

            return (
                f"[{hex_color}]{ts_str}[/]  "
                f"[{hex_color}]{emoji}[/]  "
                f"[{hex_color}]{desc}[/]"
            )

        def clear(self):
            """Clear the displayed event list."""
            try:
                body = self.query_one("#as-body", ScrollView)
                for child in list(body.children):
                    child.remove()
                body.mount(Static("Stream cleared.", id="as-empty"))
            except Exception:
                pass
            self._last_count = 0

else:
    ActivityStreamPanel = None
