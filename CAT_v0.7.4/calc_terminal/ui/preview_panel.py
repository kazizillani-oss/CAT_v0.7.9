"""
CAT UI — ui/preview_panel.py: the Web Preview pane.

Lives in the right workspace pane, switchable with the Code Editor
(never mounted/unmounted — only `display` flips, so navigation history,
URL bar text and scroll survive Code↔Preview switches):

    ┌──────────────────────────────────────────────────────────┐
    │ ← → ⟳ [ http://127.0.0.1:5173/  ] 🖥 💻 📟 📱 ◫ ⏻ ⿻      │   BrowserBar
    ├──────────────────────────────────────────────────────────┤
    │ [👁 Preview]  [📋 Console]  [⚠ Problems (0)]             │   DevToolsBar
    ├──────────────────────────────────────────────────────────┤
    │  ● Writing style.css                                     │   activity strip
    │  ✓ Preview synchronized                                  │
    ├──────────────────────────────────────────────────────────┤
    │  # CAT Live                    ← LIVE DOM outline /      │   viewport
    │    js-ran                      real Chromium / Console   │
    └──────────────────────────────────────────────────────────┘

Terminal-first contract: the page itself renders in genuine Chromium
(browser/engine.py); this panel shows its structured snapshot — title,
headings, links, buttons, images, console errors — plus dev server & console.
No external browser window is ever opened.

All colors are `$variables` resolved by CCTApp.get_css_variables(), so
the panel follows every theme automatically.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import os
import re
from typing import List, Optional

TEXTUAL_AVAILABLE = True
try:
    from textual.containers import Horizontal, Vertical, VerticalScroll
    from textual.widgets import Button, Input, Static
except Exception:
    TEXTUAL_AVAILABLE = False

MAX_ACTIVITY_LINES = 6
MAX_CONSOLE_LINES = 100


def _outline_markup(snapshot):
    """PreviewSnapshot -> Rich markup for the DOM viewport."""
    lines = []
    if snapshot.title:
        lines.append(f"[b]{snapshot.title}[/b]")
        lines.append("")
    for raw in snapshot.outline_lines[:200]:
        line = str(raw)
        esc = line.replace("[", "\\[")
        if esc.startswith("#"):
            lines.append(f"[b {chr(36)}accent]{esc}[/]")
        elif esc.lstrip().startswith("↗"):
            lines.append(f"[{chr(36)}text-muted]{esc}[/]")
        elif "✗" in esc:
            lines.append(f"[{chr(36)}error]{esc}[/]")
        else:
            lines.append(f"[{chr(36)}text]{esc}[/]")
    return "\n".join(lines)


if TEXTUAL_AVAILABLE:

    class BrowserBar(Horizontal):
        """Navigation, URL input, viewport presets, and window controls."""

        def __init__(self):
            super().__init__(id="cct-browser-bar")

        def compose(self):
            yield Button("←", id="cct-bv-back", classes="cct-bv-btn", tooltip="Back")
            yield Button("→", id="cct-bv-fwd", classes="cct-bv-btn", tooltip="Forward")
            yield Button("⟳", id="cct-bv-reload", classes="cct-bv-btn", tooltip="Reload")
            yield Input(value="", placeholder="http://127.0.0.1:<port>/",
                        id="cct-bv-url")
            # Viewport presets
            yield Button("🖥", id="cct-bv-vp-desktop", classes="cct-bv-btn -vp-active", tooltip="Desktop (100%)")
            yield Button("💻", id="cct-bv-vp-laptop", classes="cct-bv-btn", tooltip="Laptop (1024px)")
            yield Button("📟", id="cct-bv-vp-tablet", classes="cct-bv-btn", tooltip="Tablet (768px)")
            yield Button("📱", id="cct-bv-vp-mobile", classes="cct-bv-btn", tooltip="Mobile (375px)")
            # Window / Layout controls
            yield Button("◫", id="cct-bv-split", classes="cct-bv-btn", tooltip="Split editor / preview")
            yield Button("⏻", id="cct-bv-close", classes="cct-bv-btn cct-bv-danger", tooltip="Stop preview")
            yield Button("⿻", id="cct-bv-fullscreen", classes="cct-bv-btn", tooltip="Fullscreen")

    class DevToolsBar(Horizontal):
        """Developer Tools sub-navigation: Preview | Console | Problems."""

        def __init__(self):
            super().__init__(id="cct-devtools-bar")

        def compose(self):
            yield Button("👁 Preview", id="cct-dev-tab-preview", classes="cct-dev-tab -tab-active")
            yield Button("📋 Console", id="cct-dev-tab-console", classes="cct-dev-tab")
            yield Button("⚠ Problems", id="cct-dev-tab-problems", classes="cct-dev-tab")

    class PreviewPanel(Vertical):
        """The WEB PREVIEW half of the right pane with developer tools and responsive viewports."""

        def __init__(self, **kwargs):
            super().__init__(id="cct-preview", **kwargs)
            self._activity_lines = []
            self._console_lines = []
            self._status = ""
            self._last_click_time = 0
            self._last_click_target = None
            self._active_tab = "preview"  # "preview" | "console" | "problems"
            self._active_viewport = "desktop"  # "desktop" | "laptop" | "tablet" | "mobile"
            self._last_snapshot = None

        def compose(self):
            yield BrowserBar()
            yield DevToolsBar()
            yield Static("", id="cct-bv-status")
            with VerticalScroll(id="cct-bv-scroll"):
                yield Static("", id="cct-bv-viewport")
                yield Static("", id="cct-bv-console")
                yield Static("", id="cct-bv-problems")
            yield Static("", id="cct-bv-activity")

        def on_mount(self):
            self.show_status("Preview stopped — click ▷ on an HTML file or run dev server.")
            self._switch_dev_tab("preview")

        # ------------------------------------------------------ status --
        def show_status(self, text, error=False):
            try:
                status = self.query_one("#cct-bv-status", Static)
                status.update(text)
                status.set_class(bool(error), "-error")
            except Exception:
                pass

        def set_url(self, url):
            try:
                self.query_one("#cct-bv-url", Input).value = url or ""
            except Exception:
                pass

        # ---------------------------------------------------- tabs & viewport --
        def _switch_dev_tab(self, tab_name: str):
            """Switch between Preview, Console, and Problems."""
            self._active_tab = tab_name
            for name in ("preview", "console", "problems"):
                btn = self.query_one(f"#cct-dev-tab-{name}", Button)
                btn.set_class(name == tab_name, "-tab-active")

            vp = self.query_one("#cct-bv-viewport", Static)
            con = self.query_one("#cct-bv-console", Static)
            prob = self.query_one("#cct-bv-problems", Static)

            vp.display = (tab_name == "preview")
            con.display = (tab_name == "console")
            prob.display = (tab_name == "problems")

            if tab_name == "console":
                self._render_console()
            elif tab_name == "problems":
                self._render_problems()

        def _switch_viewport(self, vp_name: str):
            """Set responsive viewport preset."""
            self._active_viewport = vp_name
            for name in ("desktop", "laptop", "tablet", "mobile"):
                try:
                    btn = self.query_one(f"#cct-bv-vp-{name}", Button)
                    btn.set_class(name == vp_name, "-vp-active")
                except Exception:
                    pass

            # Apply width styling to the viewport scroll container
            try:
                scroll = self.query_one("#cct-bv-scroll", VerticalScroll)
                widths = {
                    "desktop": "100%",
                    "laptop": "1024",
                    "tablet": "768",
                    "mobile": "375",
                }
                w = widths.get(vp_name, "100%")
                if w == "100%":
                    scroll.styles.width = "100%"
                    scroll.styles.max_width = None
                else:
                    scroll.styles.max_width = int(w)
                self.show_status(f"Viewport set to {vp_name.capitalize()} ({w}px)")
            except Exception:
                pass

        # ---------------------------------------------------- console & problems --
        def add_console_log(self, text: str, is_error: bool = False):
            """Log a line from browser runtime or local dev server."""
            prefix = "[error]✗[/]" if is_error else "[info]ℹ[/]"
            self._console_lines.append(f"{prefix} {text}")
            if len(self._console_lines) > MAX_CONSOLE_LINES:
                del self._console_lines[:-MAX_CONSOLE_LINES]
            if self._active_tab == "console":
                self._render_console()

        def _render_console(self):
            try:
                con = self.query_one("#cct-bv-console", Static)
                if not self._console_lines:
                    con.update("[dim]No console output captured yet.[/dim]")
                else:
                    con.update("\n".join(self._console_lines))
            except Exception:
                pass

        def _render_problems(self):
            """Render problems from DiagnosticsManager with clickable jump links."""
            try:
                prob = self.query_one("#cct-bv-problems", Static)
                from ..preview.diagnostics import get_diagnostics_manager
                diags = get_diagnostics_manager().list_diagnostics()

                # Update the tab label with error count
                err_count = len([d for d in diags if d.severity == "error"])
                prob_btn = self.query_one("#cct-dev-tab-problems", Button)
                prob_btn.label = f"⚠ Problems ({err_count})" if err_count else "⚠ Problems"

                if not diags:
                    prob.update("[dim]✓ No problems detected in preview or workspace.[/dim]")
                    return

                lines = [f"[b]Diagnostics ({len(diags)} items):[/b]\n"]
                for i, d in enumerate(diags):
                    color = "red" if d.severity == "error" else ("yellow" if d.severity == "warning" else "cyan")
                    loc = ""
                    if d.file:
                        fn = os.path.basename(d.file)
                        pos = f":{d.line}" if d.line is not None else ""
                        if d.column is not None:
                            pos += f":{d.column}"
                        loc = f" [{color}][{fn}{pos}][/]"
                    lines.append(f"[bold {color}][{d.severity.upper()}][/] {d.message}{loc}")
                    if d.file and d.line:
                        lines.append(f"   [dim cyan]→ Press or click to jump: {d.file}:{d.line}[/dim cyan]")
                    lines.append("")

                prob.update("\n".join(lines))
            except Exception:
                pass

        # ---------------------------------------------------- viewport --
        def show_snapshot(self, snapshot):
            self._last_snapshot = snapshot
            try:
                viewport = self.query_one("#cct-bv-viewport", Static)
                scroll = self.query_one("#cct-bv-scroll", VerticalScroll)
            except Exception:
                return
            if snapshot is None:
                return
            self.set_url(snapshot.url)

            # Ingest JS errors into diagnostics and console
            if snapshot.js_errors:
                from ..preview.diagnostics import get_diagnostics_manager
                dm = get_diagnostics_manager()
                for err in snapshot.js_errors:
                    err_str = str(err)
                    self.add_console_log(err_str, is_error=True)
                    dm.add(severity="error", message=err_str, source="browser")
                self._render_problems()

            if not snapshot.ok and snapshot.error:
                self.show_status(f"WEB PREVIEW ERROR — {snapshot.error}",
                                 error=True)
                err_lines = list(snapshot.js_errors[-4:]) or \
                    ["The site failed to load. Check the URL or files."]
                body = "\n".join(str(e) for e in err_lines)
                viewport.update(
                    f"[b {chr(36)}error]WEB PREVIEW ERROR[/]\n\n{body}\n\n"
                    f"[{chr(36)}text-faint]Chat / Files / Editor / AI remain "
                    f"unaffected.[/]")
            else:
                js_err = ""
                if snapshot.js_errors:
                    last = str(snapshot.js_errors[-1])[:120]
                    js_err = f"\n[{chr(36)}warning]PREVIEW CONSOLE  {last}[/]"
                self.show_status(
                    f"● Live — {snapshot.summary_line}{js_err}")
                viewport.update(_outline_markup(snapshot))

            if self._active_tab == "preview":
                scroll.scroll_home(animate=False)

        def show_unavailable(self, detail):
            try:
                viewport = self.query_one("#cct-bv-viewport", Static)
            except Exception:
                return
            self.show_status("Browser engine unavailable.", error=True)
            viewport.update(
                f"[b {chr(36)}warning]BROWSER ENGINE UNAVAILABLE[/]\n\n"
                f"{detail}\n\n"
                f"[{chr(36)}text-faint]Everything else in CAT keeps working: "
                f"chat, files, editor and the AI agent are unaffected.[/]")

        # ----------------------------------------------------- activity --
        def push_activity(self, text, done=False):
            """One line of CAT BUILD ACTIVITY (spec section 15). Kept in
            a bounded ring so rapid AI writes can't flood the pane."""
            mark = "✓" if done else "●"
            self._activity_lines.append(f"{mark} {text}")
            del self._activity_lines[:-MAX_ACTIVITY_LINES:]
            try:
                widget = self.query_one("#cct-bv-activity", Static)
                body = "\n".join(self._activity_lines)
                widget.update(body)
                widget.set_class(True, "-has-lines") if body else None
            except Exception:
                pass

        def clear_activity(self):
            self._activity_lines = []
            try:
                self.query_one("#cct-bv-activity", Static).update("")
            except Exception:
                pass

        # ------------------------------------------------------- events --
        def on_button_pressed(self, event):
            bid = event.button.id
            app = getattr(self, "app", None)
            if app is None:
                return
            event.stop()

            # DevTools tabs
            if bid == "cct-dev-tab-preview":
                self._switch_dev_tab("preview")
                return
            elif bid == "cct-dev-tab-console":
                self._switch_dev_tab("console")
                return
            elif bid == "cct-dev-tab-problems":
                self._switch_dev_tab("problems")
                return

            # Viewport presets
            if bid == "cct-bv-vp-desktop":
                self._switch_viewport("desktop")
                return
            elif bid == "cct-bv-vp-laptop":
                self._switch_viewport("laptop")
                return
            elif bid == "cct-bv-vp-tablet":
                self._switch_viewport("tablet")
                return
            elif bid == "cct-bv-vp-mobile":
                self._switch_viewport("mobile")
                return

            # Navigation & Window controls
            if bid == "cct-bv-back":
                app.action_preview_back()
            elif bid == "cct-bv-fwd":
                app.action_preview_forward()
            elif bid == "cct-bv-reload":
                app.action_preview_reload()
            elif bid == "cct-bv-split":
                try:
                    from ..browser import WorkspaceMode
                    shell = app.query_one("#cct-workspace")
                    if shell.mode is WorkspaceMode.SPLIT:
                        shell.set_right_mode(WorkspaceMode.PREVIEW)
                    else:
                        shell.set_right_mode(WorkspaceMode.SPLIT)
                except Exception:
                    pass
            elif bid == "cct-bv-close":
                app.action_preview_close()
            elif bid == "cct-bv-fullscreen":
                app.action_toggle_right_pane_fullscreen()

        def on_input_submitted(self, event):
            """Enter in the URL bar navigates (local-first resolution)."""
            app = getattr(self, "app", None)
            if app is None:
                return
            event.stop()
            app.preview_navigate_user(event.value)

        def on_click(self, event):
            """Gestures & jumping to source from problems list."""
            import time as _t
            try:
                widget = event.widget
                widget_id = getattr(widget, "id", "")

                # Check if clicking inside Problems to jump to error
                if self._active_tab == "problems":
                    from ..preview.diagnostics import get_diagnostics_manager
                    diags = [d for d in get_diagnostics_manager().list_diagnostics() if d.file]
                    if diags and hasattr(self.app, "open_file_at"):
                        # Jump to the first diagnostic location with a line number
                        first_loc = next((d for d in diags if d.file and d.line), None)
                        if first_loc:
                            self.app.open_file_at(first_loc.file, first_loc.line, first_loc.column or 1)
                            event.stop()
                            return

                # Don't interfere with button clicks
                if widget_id and widget_id.startswith("cct-bv-") or widget_id.startswith("cct-dev-"):
                    return

                now = _t.time()
                if now - self._last_click_time < 0.35 and self._last_click_target == "preview":
                    self._last_click_time = 0
                    self._last_click_target = None
                    try:
                        from ..gestures.manager import handle_gesture
                        if handle_gesture("double_click", "preview", app=getattr(self, "app", None), context={}):
                            event.stop()
                            return
                    except Exception:
                        pass
                    try:
                        self.app.action_toggle_right_pane_fullscreen()
                        event.stop()
                    except Exception:
                        pass
                else:
                    self._last_click_time = now
                    self._last_click_target = "preview"
            except Exception:
                pass

else:
    PreviewPanel = None
    BrowserBar = None
    DevToolsBar = None
