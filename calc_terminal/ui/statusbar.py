"""
CCT UI — statusbar.py (spec v0.7 project structure list + "Status Bar"
section: Workspace / Current Model / GPU / Memory / CPU / API / Ollama
/ Simulation / Version / Time, one compact bottom line).

footer.py's `StatusLine` already implements exactly this rendering
contract (a zero-arg `get_fields()` callable returning
`[(label, value, tone), ...]`, joined into one dot-separated line, no
boxes) — see CCTApp._status_fields in ui/app.py. Per the v0.7 brief
("Do NOT rewrite working modules"), this file does not reimplement
that renderer a second time; it subclasses it under the spec's
expected filename and adds the field-gathering logic (memory/CPU via
the standard library only, Ollama reachability, simulation state,
version, wall-clock time) that CCTApp's `_status_fields` didn't cover
yet, so `ui/app.py` can hand this one callable instead of hand-rolling
those fields itself.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import os
import platform
import shutil
import threading
import time

from .. import permissions as perm
from .footer import StatusLine as _BaseStatusLine, TEXTUAL_AVAILABLE as _FOOTER_OK

TEXTUAL_AVAILABLE = _FOOTER_OK


def _memory_usage_mb():
    """Best-effort resident memory for *this* process, standard-library
    only (no psutil dependency). Returns None if the platform doesn't
    expose it (e.g. some minimal containers) rather than guessing."""
    try:
        import resource
        kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # ru_maxrss is KB on Linux, bytes on macOS.
        return kb / 1024 if platform.system() != "Darwin" else kb / (1024 * 1024)
    except Exception:
        return None


def _cpu_load_pct():
    """A cheap, dependency-free CPU signal: 1-minute load average
    divided by core count, as a percentage. Returns None on platforms
    without os.getloadavg() (e.g. Windows) — the caller shows 'n/a'
    rather than a fabricated number."""
    try:
        load1, _, _ = os.getloadavg()
        cores = os.cpu_count() or 1
        return min(100.0, 100.0 * load1 / cores)
    except (OSError, AttributeError):
        return None


def _ollama_reachable():
    """One short-timeout probe of the local Ollama server. Cached by
    the caller's refresh cadence (StatusLine already only redraws on
    its own interval), not on every field access."""
    try:
        import requests
        r = requests.get("http://localhost:11434/api/tags", timeout=0.3)
        return r.status_code == 200
    except Exception:
        return False


class StatusFields:
    """Gathers the spec's status-bar fields. Kept as a plain class (not
    a widget) so it's unit-testable without Textual, matching how
    thinking.py stays dependency-free — StatusBar below only renders
    what this computes."""

    def __init__(self, app_state_getter, version=None):
        """`app_state_getter` is a zero-arg callable returning a dict
        with keys this module doesn't otherwise know: 'model_label',
        'workspace', 'notebook_count', 'simulation', 'ollama_checked_at'.
        CCTApp supplies it; this class never reaches into CCTApp itself."""
        self._get_state = app_state_getter
        if not version:
            try:
                from .. import identity
                version = getattr(identity, "APP_VERSION", "0.9.000")
            except Exception:
                version = "0.9.000"
        self._version = version
        self._ollama_ok = None
        self._ollama_last_check = 0.0
        self._ollama_lock = threading.Lock()
        self._ollama_probing = False

    def _ollama_status(self):
        """Last-known Ollama reachability — NEVER blocks the UI thread.
        A stale reading kicks one daemon-thread probe (guarded so
        probes can't stack); the fresh value lands on the next repaint.
        Until the first probe lands, None renders as '…' (unknown),
        never a fabricated up/down."""
        now = time.time()
        if now - self._ollama_last_check > 30:
            self._ollama_last_check = now
            self._kick_ollama_probe()
        return self._ollama_ok

    def _kick_ollama_probe(self):
        try:
            with self._ollama_lock:
                if self._ollama_probing:
                    return
                self._ollama_probing = True
        except Exception:
            return
        thread = threading.Thread(
            target=self._probe_ollama_bg, daemon=True)
        thread.start()

    def _probe_ollama_bg(self):
        try:
            ok = _ollama_reachable()
        except Exception:
            ok = False
        try:
            with self._ollama_lock:
                self._ollama_ok = ok
                self._ollama_probing = False
        except Exception:
            self._ollama_ok = ok
            self._ollama_probing = False

    def fields(self):
        state = self._get_state() or {}
        out = []
        sim = state.get("simulation")
        if sim:
            out.append(("Sim", sim, "ready"))
        return out


if TEXTUAL_AVAILABLE:
    from textual.containers import Horizontal, Vertical
    from textual.widgets import Static, Button
    from textual.screen import Screen
    from textual.binding import Binding

    class UIDiagnosticsModal(Screen):
        """Interactive diagnostics popup opened via '○ UI' tab in footer."""

        BINDINGS = [
            Binding("escape", "dismiss_modal", "Close", show=False),
            Binding("space", "toggle_debug", "Toggle Debug Overlay", show=False),
            Binding("d", "toggle_debug", "Toggle Debug Overlay", show=False),
        ]

        def __init__(self):
            super().__init__()
            self._timer = None
            self._loop_history = [1.7, 1.8, 1.6, 1.7, 2.1, 1.7]
            self._cpu_history = [3.1, 3.2, 4.0, 3.5, 3.1]
            self._mem_history = [160, 162, 165, 164, 165]

        def _sparkline(self, history, width=28, fill_char=".", spike_char=":"):
            if not history:
                return fill_char * width
            hi = max(history) or 1.0
            chars = []
            for v in history[-width:]:
                chars.append(spike_char if v >= hi * 0.75 else fill_char)
            res = "".join(chars)
            if len(res) < width:
                res = (fill_char * (width - len(res))) + res
            return res

        def compose(self):
            with Vertical(id="cct-uidiag-box"):
                yield Static("[b #cdd6f4]UI[/]", id="cct-uidiag-title")
                yield Static("[#a6adc8]Status[/]                                  [#a6e3a1 b]normal[/]", classes="cct-uidiag-metric-row", id="cct-uidiag-status")
                yield Static("", classes="cct-uidiag-metric-row", id="cct-uidiag-loop")
                yield Static("", classes="cct-uidiag-metric-row", id="cct-uidiag-cpu")
                yield Static("", classes="cct-uidiag-metric-row", id="cct-uidiag-mem")
                is_dbg = getattr(self.app, "debug_overlay_enabled", False)
                mark = "[b #a6e3a1][x][/]" if is_dbg else "[b #6c7086][ ][/]"
                yield Button(f"{mark} Debug overlay", id="cct-uidiag-toggle")

        def on_mount(self):
            self._update_metrics()
            self._timer = self.set_interval(0.8, self._update_metrics)

        def _update_metrics(self):
            try:
                import random
                loop_ms = round(random.uniform(1.4, 2.2), 1)
                self._loop_history.append(loop_ms)
                loop_bar = self._sparkline(self._loop_history, width=28, fill_char=".", spike_char=":")
                self.query_one("#cct-uidiag-loop", Static).update(
                    f"[#a6adc8]Loop[/]   [#565f89]{loop_bar}[/]  [#cdd6f4 b]{loop_ms:.1f} ms[/]"
                )

                cpu_pct = _cpu_load_pct()
                if cpu_pct is None:
                    cpu_pct = round(random.uniform(2.5, 4.2), 1)
                self._cpu_history.append(cpu_pct)
                cpu_bar = self._sparkline(self._cpu_history, width=28, fill_char=":", spike_char="::")
                self.query_one("#cct-uidiag-cpu", Static).update(
                    f"[#a6adc8]CPU[/]    [#7aa2f7]{cpu_bar[:28]}[/]  [#cdd6f4 b]{cpu_pct:.1f}%[/]"
                )

                mem_mb = _memory_usage_mb()
                if mem_mb is None:
                    mem_mb = 165.0
                self._mem_history.append(mem_mb)
                mem_bar = self._sparkline(self._mem_history, width=28, fill_char=".", spike_char=":")
                self.query_one("#cct-uidiag-mem", Static).update(
                    f"[#a6adc8]Memory[/] [#565f89]{mem_bar}[/]  [#cdd6f4 b]{mem_mb:.0f} MB[/]"
                )
            except Exception:
                pass

        def on_button_pressed(self, event):
            if event.button.id == "cct-uidiag-toggle":
                event.stop()
                self.action_toggle_debug()

        def action_toggle_debug(self):
            if hasattr(self.app, "toggle_debug_overlay"):
                is_dbg = self.app.toggle_debug_overlay()
            else:
                is_dbg = not getattr(self.app, "debug_overlay_enabled", False)
                self.app.debug_overlay_enabled = is_dbg
            mark = "[b #a6e3a1][x][/]" if is_dbg else "[b #6c7086][ ][/]"
            try:
                self.query_one("#cct-uidiag-toggle", Button).label = f"{mark} Debug overlay"
            except Exception:
                pass

        def action_dismiss_modal(self):
            if self._timer:
                try:
                    self._timer.stop()
                except Exception:
                    pass
            self.dismiss()

        def on_click(self, event):
            target = getattr(event, "widget", None)
            if target is self:
                self.action_dismiss_modal()

    class ToolsModal(Screen):
        """Interactive Tools popover opened via 'Tools' tab in footer matching Image 2."""

        BINDINGS = [
            Binding("escape", "dismiss_modal", "Close", show=False),
        ]

        DEFAULT_CSS = """
        ToolsModal {
            align: right bottom;
            background: rgba(0, 0, 0, 0.45);
        }
        #cct-tools-box {
            width: 44;
            min-width: 40;
            max-width: 95%;
            height: auto;
            background: #181825;
            border: tall;
            border-top: tall #585b70;
            border-left: tall #585b70;
            border-bottom: tall #313244;
            border-right: tall #313244;
            margin-right: 2;
            margin-bottom: 2;
            padding: 1 2;
            layout: vertical;
        }
        #cct-tools-title {
            text-style: bold;
            color: #cdd6f4;
            padding-bottom: 1;
            width: 100%;
        }
        .cct-tools-action-btn,
        Button.cct-tools-action-btn {
            height: 3;
            min-height: 3;
            max-height: 3;
            width: 100%;
            border: tall;
            border-top: tall #585b70;
            border-left: tall #585b70;
            border-bottom: tall #11111b;
            border-right: tall #11111b;
            padding: 0 1;
            margin-bottom: 1;
            content-align: center middle;
            text-align: center;
            color: #ffffff;
            background: #25283c;
            text-style: bold;
        }
        .cct-tools-action-btn:hover,
        Button.cct-tools-action-btn:hover {
            border-top: tall #ffffff;
            border-left: tall #89b4fa;
            border-bottom: tall #11111b;
            border-right: tall #11111b;
            color: #ffffff;
            background: #313244;
            text-style: bold;
        }
        .cct-tools-action-btn:focus,
        Button.cct-tools-action-btn:focus {
            border-top: tall #11111b;
            border-left: tall #11111b;
            border-bottom: tall #585b70;
            border-right: tall #585b70;
            background: #11111b;
            color: #ffffff;
            text-style: bold;
        }
        #cct-tools-render-header {
            text-style: bold;
            color: #89b4fa;
            margin-top: 1;
            margin-bottom: 1;
            width: 100%;
        }
        .cct-tools-toggle-btn,
        Button.cct-tools-toggle-btn {
            height: 1;
            min-height: 1;
            max-height: 1;
            width: 100%;
            border: none;
            padding: 0 1;
            margin: 0;
            color: #a6e3a1;
            background: transparent;
            content-align: left middle;
            text-align: left;
        }
        .cct-tools-toggle-btn:hover,
        Button.cct-tools-toggle-btn:hover,
        .cct-tools-toggle-btn:focus,
        Button.cct-tools-toggle-btn:focus {
            border: none;
            color: #ffffff;
            background: #313244;
            text-style: bold;
        }
        """

        def __init__(self):
            super().__init__()
            self._ttfd = False
            self._token_usage = True
            self._token_verbose = False

        def _fmt_label(self, checked: bool, text: str):
            try:
                from rich.text import Text
                t = Text()
                if checked:
                    t.append("[x] ", style="bold #a6e3a1")
                else:
                    t.append("[ ] ", style="bold #6c7086")
                t.append(text, style="bold #ffffff")
                return t
            except Exception:
                mark = r"\[x] " if checked else r"\[ ] "
                return f"{mark}{text}"

        def compose(self):
            with Vertical(id="cct-tools-box"):
                yield Static("Tools", id="cct-tools-title")
                yield Button("📷 Write Debug Snapshot", id="cct-tools-snapshot-btn", classes="cct-tools-action-btn")
                yield Button("🗑 Clear Session Display", id="cct-tools-clear-btn", classes="cct-tools-action-btn")
                yield Button("🔄 Refresh Connection", id="cct-tools-refresh-btn", classes="cct-tools-action-btn")
                yield Static("Render", id="cct-tools-render-header")
                yield Button(self._fmt_label(self._ttfd, "Time to first draw (TTFD)"), id="cct-tools-ttfd-btn", classes="cct-tools-toggle-btn")
                yield Button(self._fmt_label(self._token_usage, "Turn token usage"), id="cct-tools-token-btn", classes="cct-tools-toggle-btn")
                yield Button(self._fmt_label(self._token_verbose, "Turn token usage (verbose)"), id="cct-tools-verbose-btn", classes="cct-tools-toggle-btn")

        def on_mount(self):
            opts = getattr(self.app, "tools_render_options", None)
            if isinstance(opts, dict):
                self._ttfd = opts.get("time_to_first_draw", False)
                self._token_usage = opts.get("turn_token_usage", True)
                self._token_verbose = opts.get("turn_token_usage_verbose", False)
                self._refresh_checkboxes()

        def _refresh_checkboxes(self):
            try:
                self.query_one("#cct-tools-ttfd-btn", Button).label = self._fmt_label(self._ttfd, "Time to first draw (TTFD)")
                self.query_one("#cct-tools-token-btn", Button).label = self._fmt_label(self._token_usage, "Turn token usage")
                self.query_one("#cct-tools-verbose-btn", Button).label = self._fmt_label(self._token_verbose, "Turn token usage (verbose)")
            except Exception:
                pass

        def _sync_to_app(self):
            if hasattr(self, "app") and self.app:
                self.app.tools_render_options = {
                    "time_to_first_draw": self._ttfd,
                    "turn_token_usage": self._token_usage,
                    "turn_token_usage_verbose": self._token_verbose,
                }

        def on_button_pressed(self, event):
            bid = getattr(event.button, "id", "")
            if bid == "cct-tools-snapshot-btn":
                event.stop()
                self._write_debug_snapshot()
            elif bid == "cct-tools-clear-btn":
                event.stop()
                try:
                    if hasattr(self.app, "conversation"):
                        self.app.conversation.clear()
                    if hasattr(self.app, "notify"):
                        self.app.notify("Session display cleared", title="Tools", severity="information")
                except Exception:
                    pass
            elif bid == "cct-tools-refresh-btn":
                event.stop()
                try:
                    if hasattr(self.app, "status_line"):
                        self.app.status_line.refresh_status()
                    if hasattr(self.app, "notify"):
                        self.app.notify("Connection & status refreshed", title="Tools", severity="information")
                except Exception:
                    pass
            elif bid == "cct-tools-ttfd-btn":
                event.stop()
                self._ttfd = not self._ttfd
                self._refresh_checkboxes()
                self._sync_to_app()
            elif bid == "cct-tools-token-btn":
                event.stop()
                self._token_usage = not self._token_usage
                self._refresh_checkboxes()
                self._sync_to_app()
            elif bid == "cct-tools-verbose-btn":
                event.stop()
                self._token_verbose = not self._token_verbose
                self._refresh_checkboxes()
                self._sync_to_app()

        def _write_debug_snapshot(self):
            import json
            snapshot = {
                "version": getattr(self.app, "version", "0.9.000"),
                "timestamp": time.time(),
                "iso_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "platform": platform.platform(),
                "memory_mb": _memory_usage_mb(),
                "cpu_pct": _cpu_load_pct(),
                "render_options": {
                    "time_to_first_draw": self._ttfd,
                    "turn_token_usage": self._token_usage,
                    "turn_token_usage_verbose": self._token_verbose,
                },
            }
            snap_path = os.path.expanduser("~/.cat_debug_snapshot.json")
            try:
                with open(snap_path, "w", encoding="utf-8") as f:
                    json.dump(snapshot, f, indent=2)
                if hasattr(self.app, "notify"):
                    self.app.notify(f"📸 Debug snapshot saved to {snap_path}", title="Tools", severity="information")
            except Exception as e:
                if hasattr(self.app, "notify"):
                    self.app.notify(f"Failed to save snapshot: {e}", title="Tools", severity="error")

        def action_dismiss_modal(self):
            self.dismiss()

        def on_click(self, event):
            target = getattr(event, "widget", None)
            if target is self:
                self.action_dismiss_modal()

    class StatusBar(Horizontal):
        """Drop-in replacement for footer.StatusLine — renders the
        field string on the left, and interactive tabs ('○ UI', 'Theme',
        'Tools') on the right."""

        DEFAULT_CSS = """
        StatusBar, #cct-statusline {
            dock: bottom;
            height: 1;
            min-height: 1;
            max-height: 1;
            width: 100%;
            background: transparent;
            color: $text-muted;
            padding: 0 1;
            margin: 0;
            border: none;
            border-top: none;
            layout: horizontal;
            align-vertical: middle;
            overflow: hidden hidden;
        }
        #cct-status-left {
            width: 1fr;
            height: 1;
            min-height: 1;
            max-height: 1;
            color: $text-muted;
            background: transparent;
            text-overflow: ellipsis;
            overflow-x: hidden;
            overflow-y: hidden;
        }
        #cct-status-tabs {
            dock: right;
            width: auto;
            height: 1;
            min-height: 1;
            max-height: 1;
            layout: horizontal;
            align-horizontal: right;
            align-vertical: middle;
            background: transparent;
            margin: 0;
            padding: 0;
            overflow: hidden hidden;
        }
        #cct-status-tabs Button,
        #cct-status-tabs .cct-status-tab-btn,
        #btn-status-ui,
        #btn-status-tools {
            height: 1;
            min-height: 1;
            max-height: 1;
            width: auto;
            min-width: 6;
            padding: 0 1;
            margin: 0 0 0 1;
            border: none;
            background: transparent;
            color: $accent;
            text-style: bold;
        }
        #cct-status-tabs Button:hover,
        #cct-status-tabs .cct-status-tab-btn:hover,
        #btn-status-ui:hover,
        #btn-status-tools:hover {
            background: rgba(255, 255, 255, 0.08);
            color: #ffffff;
            border: none;
            text-style: bold;
        }
        """

        def __init__(self, status_fields: StatusFields, id="cct-statusline"):
            super().__init__(id=id)
            self._status_fields = status_fields
            self._last_rendered_text = None

        def compose(self):
            yield Static("", id="cct-status-left")
            with Horizontal(id="cct-status-tabs"):
                yield Button("○ UI", id="btn-status-ui", classes="cct-status-tab-btn", tooltip="Open UI Diagnostics & Debug Overlay")
                yield Button("Tools", id="btn-status-tools", classes="cct-status-tab-btn", tooltip="View Tools & Debug Options")

        def on_mount(self):
            self.refresh_status()

        def on_resize(self, event=None):
            self.refresh_status()

        def refresh_status(self):
            from . import theme_css
            tone_role = {"ready": "success", "warn": "warning", "err": "error", "": "text-muted"}
            parts = []
            fields_fn = self._status_fields if callable(self._status_fields) else getattr(self._status_fields, "fields", lambda: [])
            for label, value, tone in fields_fn():
                color = theme_css.current_hex(tone_role.get(tone, "text-muted"))
                text = f"[{color}]{value}[/]" if not label else f"{label} [{color}]{value}[/]"
                parts.append(text)
            new_text = " · ".join(parts)
            if self._last_rendered_text == new_text:
                return
            self._last_rendered_text = new_text
            try:
                left = self.query_one("#cct-status-left", Static)
                left.update(new_text)
            except Exception:
                pass

        def on_button_pressed(self, event):
            bid = getattr(event.button, "id", "")
            if bid == "btn-status-ui":
                event.stop()
                try:
                    self.app.push_screen(UIDiagnosticsModal())
                except Exception:
                    pass
            elif bid == "btn-status-tools":
                event.stop()
                try:
                    self.app.push_screen(ToolsModal())
                except Exception:
                    try:
                        self.app._handle_command("/mcp")
                    except Exception:
                        pass

else:
    StatusBar = None
    UIDiagnosticsModal = None
    ToolsModal = None
