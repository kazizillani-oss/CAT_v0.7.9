"""
CCT UI — McpServersPanel (v0.7.8.1 full redesign).

Professional management screen for the Model Context Protocol (MCP)
client in calc_terminal/mcp.py:

  - Card rows list every saved server with a live connection status:
    🟢 Connected / 🔴 Offline / 🟡 Connecting, plus transport, version,
    latency, tools exposed and last sync time.
  - Minimal action set: one primary "+ Add Server"; a contextual row
    (Edit / Connect·Disconnect / Delete) appears only when servers
    exist and acts on the selected card; Save / Cancel close the page.
  - Connect/Disconnect drives calc_terminal.mcp sessions in a
    background thread so the UI never blocks on a hanging server.
  - The Add/Edit popup is centered with a fade + slide animation and
    offers HTTP / STDIO transports, URL, headers, authentication, and a
    live Test Connection button.

The app routes the Main Menu's "MCP Servers" item to this screen.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import threading
import time

TEXTUAL_AVAILABLE = True
try:
    from textual.screen import Screen
    from textual.containers import Vertical, Horizontal, ScrollableContainer
    from textual.widgets import Static, Button, Input
    from textual.binding import Binding
except Exception:
    TEXTUAL_AVAILABLE = False

if TEXTUAL_AVAILABLE:
    from .. import mcp
    from . import theme_css

    _STATUS_GLYPH = {
        "connected": "\U0001f7e2",    # 🟢
        "connecting": "\U0001f7e1",   # 🟡
        "disconnected": "\U0001f534",  # 🔴
        "failed": "\U0001f534",        # 🔴
    }

    _STATUS_LABEL = {
        "connected": "Connected",
        "connecting": "Connecting",
        "disconnected": "Offline",
        "failed": "Offline",
    }

    def _status_tone(status_key):
        return {
            "connected": "success",
            "connecting": "warning",
            "disconnected": "text-faint",
            "failed": "error",
        }.get(status_key, "text-faint")

    def _last_sync_text(server):
        ts = server.get("last_connected") or 0
        if not ts:
            return "never"
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))


    class _ServerCard(Static):
        """One server card: name + live status on line 1, transport ·
        version · latency · tools · last sync on line 2."""

        def __init__(self, index, server, selected=False):
            self.index = index
            self.server = server
            super().__init__("", classes="mcp-card" + (" mcp-card-sel" if selected else ""))
            self._redraw()

        def _redraw(self):
            name = self.server.get("name") or self.server.get("id") or "?"
            status_key = self.server.get("status") or "disconnected"
            glyph = _STATUS_GLYPH.get(status_key, "\U0001f534")
            tone = theme_css.current_hex(_status_tone(status_key))
            label = _STATUS_LABEL.get(status_key, "Offline")
            kind = "local" if self.server.get("kind") == "local" else "remote"
            version = self.server.get("version") or ""
            latency = self.server.get("latency_ms")
            lat_txt = f"{latency}ms" if latency is not None else "\u2014"
            tools = self.server.get("tools") or []
            tools_txt = f"{len(tools)} tools"
            sync_txt = _last_sync_text(self.server)
            sel = " \u25b8" if "mcp-card-sel" in self.classes else ""
            line1 = (f"  {glyph} [{theme_css.current_hex('text')} b]{name}[/] "
                     f"[{tone}]{label}[/]  [{theme_css.current_hex('text-faint')}]"
                     f"({kind})[/]{sel}")
            line2 = (f"      [{theme_css.current_hex('text-faint')}]"
                     f"transport {kind}  \u00b7  v{version if version else '-'}"
                     f"  \u00b7  {lat_txt}  \u00b7  {tools_txt}"
                     f"  \u00b7  sync {sync_txt}[/]")
            self.update(f"{line1}\n{line2}")

        def set_selected(self, selected):
            self.set_class(selected, "mcp-card-sel")
            self._redraw()


    class McpServersPanel(Screen):
        """Manage MCP servers: add, edit, remove, connect, disconnect,
        persist."""

        CSS = """
        McpServersPanel { align: center middle; background: $app-background 70%; }
        #mcp-box {
            width: 92; max-width: 100%; height: auto; max-height: 92%;
            background: $surface; border: round $border; padding: 0;
            opacity: 0; offset-y: 1;
            transition: opacity 150ms, offset 180ms;
        }
        #mcp-box.open { opacity: 1; offset-y: 0; }
        #mcp-titlebar {
            height: 3; padding: 1 2 0 2;
            border-bottom: solid $border;
        }
        #mcp-title { text-style: bold; width: 1fr; }
        #mcp-subtitle { color: $text-faint; height: 2; padding: 0 2; }
        #mcp-list { height: auto; min-height: 4; padding: 1 2; overflow-y: auto; scrollbar-gutter: stable; }
        .mcp-card {
            height: 3; margin-bottom: 1;
            background: $app-background; border: round $border;
            padding: 0 1;
        }
        .mcp-card-sel { border: round $border-active; }
        .mcp-empty { color: $text-faint; padding: 2 1; }
        #mcp-add-row { height: 4; padding: 0 2 1 2; }
        #mcp-add-row Button { margin-right: 1; }
        #mcp-ctx-actions { height: 4; padding: 0 2 1 2; }
        #mcp-ctx-actions Button { margin-right: 1; width: 1fr; min-width: 10; }
        #mcp-actions { height: 5; padding: 0 2 1 2; border-top: solid $border; }
        #mcp-actions Button { margin-right: 1; }
        #mcp-box.cct-compact #mcp-subtitle { display: none; }
        """

        BINDINGS = [
            Binding("escape", "cancel", "Cancel"),
            Binding("down", "move_down_sel", "Next row"),
            Binding("up", "move_up_sel", "Previous row"),
        ]

        def __init__(self):
            super().__init__()
            self._servers = mcp.load_servers()
            self._selected = 0

        def compose(self):
            with Vertical(id="mcp-box"):
                with Horizontal(id="mcp-titlebar"):
                    yield Static("\U0001f310  MCP Servers", id="mcp-title")
                    yield Button("\u2715", id="mcp-close", classes="cct-popup-close")
                yield Static(
                    "Model Context Protocol servers used by CAT.",
                    id="mcp-subtitle")
                with ScrollableContainer(id="mcp-list"):
                    yield from self._rows()
                with Horizontal(id="mcp-add-row"):
                    yield Button("+ Add Server", id="mcp-add", variant="primary",
                                 classes="cct-btn")
                with Horizontal(id="mcp-ctx-actions"):
                    yield Button("Edit", id="mcp-edit", classes="cct-btn")
                    yield Button("Connect", id="mcp-connect", classes="cct-btn")
                    yield Button("Delete", id="mcp-remove", classes="cct-btn")
                with Horizontal(id="mcp-actions"):
                    yield Button("Save", id="mcp-save", variant="primary", classes="cct-btn")
                    yield Button("Cancel", id="mcp-cancel", classes="cct-btn")

        def _rows(self):
            if not self._servers:
                yield Static("No MCP servers configured.", classes="mcp-empty")
                yield Static("Add an MCP server to expose its tools to CAT.",
                             classes="mcp-empty")
                return
            for i, server in enumerate(self._servers):
                yield _ServerCard(i, server, selected=(i == self._selected))

        def _rebuild_list(self):
            try:
                self.query_one("#mcp-list", ScrollableContainer).remove_children()
                for row in self._rows():
                    self.query_one("#mcp-list", ScrollableContainer).mount(row)
                self._refresh_actions()
                self._fit()
            except Exception:
                pass

        def _refresh_actions(self):
            """Contextual actions row appears only when servers exist;
            the Connect button flips to Disconnect for a connected
            server. Only what's relevant is ever on screen."""
            has = bool(self._servers)
            try:
                self.query_one("#mcp-ctx-actions").display = has
            except Exception:
                pass
            if not has:
                return
            server = self._current()
            connected = bool(server and server.get("status") == "connected")
            try:
                btn = self.query_one("#mcp-connect", Button)
                btn.label = "Disconnect" if connected else "Connect"
                btn.variant = "error" if connected else "default"
            except Exception:
                pass

        def _fit(self):
            """Re-fit after content changes: content_size is only valid
            after the next layout pass, so always defer one frame."""
            try:
                self.call_after_refresh(
                    lambda: theme_css.fit_dialog(self, "mcp-box", "mcp-list"))
            except Exception:
                pass

        def _refresh_status(self):
            """Legacy no-op kept for callers outside this class."""
            return

        def on_mount(self):
            self.call_after_refresh(lambda: self.query_one("#mcp-box").add_class("open"))
            self.call_after_refresh(self._fit)
            self._refresh_actions()

        def on_resize(self, event):
            self._fit()

        def on_click(self, event):
            widget = getattr(event, "widget", None)
            if isinstance(widget, _ServerCard):
                if self._servers and widget.index < len(self._servers):
                    self._selected = widget.index
                    self._rebuild_list()
                return
            if widget in (self, None):
                self.dismiss(None)

        def on_key(self, event):
            if event.key == "escape":
                self.dismiss(None)

        def action_cancel(self):
            self.dismiss(None)

        def action_move_down_sel(self):
            if self._servers:
                self._selected = min(self._selected + 1, len(self._servers) - 1)
                self._rebuild_list()

        def action_move_up_sel(self):
            if self._servers:
                self._selected = max(self._selected - 1, 0)
                self._rebuild_list()
        def _current(self):
            if not self._servers:
                return None
            return self._servers[min(self._selected, len(self._servers) - 1)]

        def on_button_pressed(self, event):
            eid = event.button.id
            if eid in ("mcp-cancel", "mcp-close"):
                self.dismiss(None)
            elif eid == "mcp-add":
                self.app.push_screen(_AddMcpForm(), self._on_saved)
            elif eid == "mcp-edit":
                server = self._current()
                if server:
                    self.app.push_screen(_AddMcpForm(server), self._on_saved)
            elif eid == "mcp-remove":
                server = self._current()
                if server:
                    mcp.remove_server(server.get("id", ""))
                    self._servers = mcp.load_servers()
                    self._selected = min(self._selected, max(0, len(self._servers) - 1))
                    self._rebuild_list()
            elif eid == "mcp-connect":
                self._toggle_connect()
            elif eid == "mcp-save":
                mcp.save_servers(self._servers)
                try:
                    self.app._system_note(
                        f"\u2713 MCP servers saved \u2014 {len(self._servers)} configured.")
                except Exception:
                    pass
                self.dismiss(None)

        def _toggle_connect(self):
            """One contextual Connect/Disconnect action: disconnects a
            connected server, connects a disconnected one."""
            server = self._current()
            if not server:
                return
            if server.get("status") == "connected":
                mcp.disconnect_server(server.get("id", ""))
                server["status"] = "disconnected"
                server["version"] = ""
                server["latency_ms"] = None
                server["tools"] = []
                self._rebuild_list()
                return
            server["status"] = "connecting"
            self._rebuild_list()

            def _run():
                ok, msg = mcp.connect_server(server)
                live = mcp.server_status(server)
                server["status"] = "connected" if ok else "failed"
                server["version"] = live["version"]
                server["latency_ms"] = live["latency_ms"]
                server["tools"] = list(live["tools"])
                if ok:
                    server["last_connected"] = int(time.time())
                self.app.call_from_thread(self._rebuild_list)
                try:
                    if self.app._system_note:
                        self.app._system_note(f"MCP '{server.get('name', '?')}': {msg}")
                except Exception:
                    pass

            threading.Thread(target=_run, daemon=True).start()

        def _on_saved(self, server):
            if not server:
                return
            mcp.add_server(server)
            self._servers = mcp.load_servers()
            self._selected = len(self._servers) - 1
            self._rebuild_list()


    class _AddMcpForm(Screen):
        """Add/Edit MCP server popup (v0.7.8.1 redesign): centered,
        animated, equal-width buttons, HTTP / STDIO toggle, URL,
        headers, authentication, and a live Test Connection button.
        Pass an existing server record to edit it in place."""

        CSS = """
        _AddMcpForm { align: center middle; background: $app-background 70%; }
        #amf-box {
            width: 66; height: auto; max-height: 92%; background: $surface;
            border: round $border; padding: 0;
            opacity: 0; offset-y: 1;
            transition: opacity 150ms, offset 180ms;
        }
        #amf-box.open { opacity: 1; offset-y: 0; }
        #amf-titlebar { height: 3; padding: 1 2 0 2; border-bottom: solid $border; }
        #amf-title { text-style: bold; width: 1fr; }
        #amf-body { padding: 1 2; overflow-y: auto; scrollbar-gutter: stable; }
        #amf-kind { height: 4; padding: 1 2 0 2; }
        #amf-kind Button { margin-right: 1; }
        #amf-status { color: $text-faint; height: 1; padding-top: 1; }
        #amf-actions { height: 5; padding: 0 2 1 2; border-top: solid $border; }
        #amf-actions Button { margin-right: 1; width: 1fr; min-width: 10; }
        .amf-hint { color: $text-faint; padding: 0 2 1 2; }
        #amf-box.cct-compact .amf-hint { display: none; }
        """

        BINDINGS = [Binding("escape", "cancel", "Cancel")]

        def __init__(self, server=None):
            super().__init__()
            self._server = server or {}
            self._kind = self._server.get("kind", "remote")
            self._tested_ok = False

        def compose(self):
            with Vertical(id="amf-box"):
                with Horizontal(id="amf-titlebar"):
                    yield Static("Add MCP Server" if not self._server else "Edit MCP Server",
                                 id="amf-title")
                    yield Button("\u2715", id="amf-close", classes="cct-popup-close")
                with Vertical(id="amf-body"):
                    yield Static("Server Name", classes="cct-field-label")
                    yield Input(placeholder="My Tool Server", id="amf-name",
                                value=self._server.get("name", ""))
                    yield Static("Connection Type", classes="cct-field-label")
                    with Horizontal(id="amf-kind"):
                        yield Button("HTTP", id="amf-kind-remote",
                                     variant="primary" if self._kind == "remote" else "default",
                                     classes="cct-btn cct-btn-sm")
                        yield Button("STDIO", id="amf-kind-local",
                                     variant="primary" if self._kind == "local" else "default",
                                     classes="cct-btn cct-btn-sm")
                    yield Static("Endpoint URL (HTTP only \u2014 must end in /mcp or /jsonrpc)",
                                 classes="cct-field-label amf-remote-field")
                    yield Input(placeholder="http://localhost:3000/mcp", id="amf-url",
                                value=self._server.get("url", ""),
                                classes="amf-remote-field on")
                    yield Static("Command (STDIO only \u2014 e.g. npx -y server, argument per word)",
                                 classes="cct-field-label amf-local-field")
                    yield Input(placeholder="npx -y my-mcp-server", id="amf-command",
                                value=self._server.get("command", ""),
                                classes="amf-local-field")
                    yield Static("Extra headers (optional, format: Key: Value)",
                                 classes="cct-field-label amf-remote-field")
                    yield Input(placeholder="Authorization: Bearer abc", id="amf-header",
                                value=_headers_to_str(self._server.get("headers") or {}),
                                classes="amf-remote-field")
                    yield Static("Authentication token (optional \u2014 sent as a Bearer header)",
                                 classes="cct-field-label amf-remote-field")
                    yield Input(placeholder="sk-...", id="amf-auth",
                                value=self._server.get("auth_token", ""),
                                password=True, classes="amf-remote-field")
                    yield Static("", id="amf-status")
                with Horizontal(id="amf-actions"):
                    yield Button("  \u2699 Test Connection  ", id="amf-test", classes="cct-btn")
                    yield Button("Add", id="amf-add", variant="primary", classes="cct-btn")
                    yield Button("Cancel", id="amf-cancel", classes="cct-btn")
                yield Static("Enter to confirm  \u00b7  Esc to cancel", classes="amf-hint")

        def _apply_kind(self):
            kind = self._kind
            for name in ("command", "url", "header", "auth"):
                try:
                    field = self.query_one(f"#amf-{name}", Input)
                except Exception:
                    continue
                show_field = (name == "command" and kind == "local") or \
                             (name in ("url", "header", "auth") and kind == "remote")
                field.display = show_field
            for cls in ("amf-remote-field", "amf-local-field"):
                for w in self.query(f".{cls}"):
                    shown = (cls == "amf-local-field" and kind == "local") or \
                            (cls == "amf-remote-field" and kind == "remote")
                    w.display = shown
            self.query_one("#amf-kind-remote", Button).variant = \
                "primary" if kind == "remote" else "default"
            self.query_one("#amf-kind-local", Button).variant = \
                "primary" if kind == "local" else "default"
            self._fit()

        def on_mount(self):
            self._apply_kind()
            self.call_after_refresh(lambda: self.query_one("#amf-box").add_class("open"))
            self.call_after_refresh(self._fit)
            try:
                self.query_one("#amf-name", Input).focus()
            except Exception:
                pass

        def on_resize(self, event):
            self._fit()

        def _fit(self):
            try:
                self.call_after_refresh(
                    lambda: theme_css.fit_dialog(self, "amf-box", "amf-body"))
            except Exception:
                pass

        def action_cancel(self):
            self.dismiss(None)

        def on_click(self, event):
            wid = getattr(event.widget, "id", None) if getattr(event, "widget", None) else None
            if wid == "amf-kind-remote":
                self._kind = "remote"
                self._apply_kind()
            elif wid == "amf-kind-local":
                self._kind = "local"
                self._apply_kind()
            elif getattr(event, "widget", None) in (self, None):
                self.dismiss(None)

        def on_key(self, event):
            if event.key == "escape":
                self.dismiss(None)

        def on_button_pressed(self, event):
            eid = event.button.id
            if eid == "amf-add":
                self._submit()
            elif eid == "amf-cancel" or eid == "amf-close":
                self.dismiss(None)
            elif eid == "amf-test":
                self._test_connection()
            else:
                self.on_click(type("e", (), {"widget": event.button})())

        def on_input_submitted(self, event):
            if event.input.id == "amf-name":
                self._submit()

        def _build_record(self):
            server = dict(self._server)
            name = self.query_one("#amf-name", Input).value.strip()
            server["name"] = name
            server["kind"] = self._kind
            if self._kind == "local":
                server["command"] = self.query_one("#amf-command", Input).value.strip()
            else:
                url = self.query_one("#amf-url", Input).value.strip()
                if url:
                    server["url"] = url
                header = self.query_one("#amf-header", Input).value.strip()
                headers = {}
                if header and ":" in header:
                    k, _, v = header.partition(":")
                    headers[k.strip()] = v.strip()
                auth = self.query_one("#amf-auth", Input).value.strip()
                if auth:
                    headers["Authorization"] = f"Bearer {auth}"
                server["headers"] = headers
            server.setdefault("enabled", True)
            server.setdefault("status", "disconnected")
            server.setdefault("version", "")
            server.setdefault("latency_ms", None)
            server.setdefault("tools", [])
            return server

        def _submit(self):
            server = self._build_record()
            if not server.get("name"):
                self.query_one("#amf-status", Static).update(
                    f"[{theme_css.current_hex('error')}]\u2717 Name is required[/]")
                return
            if self._kind == "local" and not server.get("command"):
                self.query_one("#amf-status", Static).update(
                    f"[{theme_css.current_hex('error')}]\u2717 Command is required for STDIO[/]")
                return
            if self._kind == "remote" and not str(server.get("url", "")).startswith("http"):
                self.query_one("#amf-status", Static).update(
                    f"[{theme_css.current_hex('error')}]\u2717 A valid HTTP endpoint URL is required[/]")
                return
            self.dismiss(server)

        def _test_connection(self):
            server = self._build_record()
            if not server.get("name"):
                self.query_one("#amf-status", Static).update(
                    f"[{theme_css.current_hex('error')}]\u2717 Name is required before testing[/]")
                return
            status = self.query_one("#amf-status", Static)
            status.update(
                f"[{theme_css.current_hex('warning')}]\U0001f7e1 Testing connection\u2026[/]")
            test_server = dict(server)
            test_server["id"] = f"test-{int(time.time())}"
            test_server["status"] = "connecting"

            def _run():
                try:
                    ok, msg = mcp.connect_server(test_server)
                except Exception as e:
                    ok, msg = False, str(e)
                self.app.call_from_thread(
                    lambda: status.update(
                        f"[{theme_css.current_hex('success' if ok else 'error')}]"
                        f"{'\u2713' if ok else '\u2717'} {msg}[/]"))

            threading.Thread(target=_run, daemon=True).start()


    def _headers_to_str(headers):
        if not headers:
            return ""
        return ", ".join(f"{k}: {v}" for k, v in headers.items())

else:
    McpServersPanel = None
    _AddMcpForm = None
