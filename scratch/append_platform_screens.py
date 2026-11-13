"""
Append ObservabilityScreen, RecoveryManagerScreen, MultiWorkspaceScreen, and DeveloperSDKScreen
to calc_terminal/ui/platform_screens.py.
"""

new_screens = '''

    class ObservabilityScreen(Screen):
        """Interactive Observability Center Modal."""
        CSS = """
        ObservabilityScreen { align: center middle; background: rgba(0, 0, 0, 0.75); }
        #obs-box {
            width: 86; max-width: 96%; height: auto; max-height: 85%;
            background: $surface; border: round $accent; padding: 0;
            layout: vertical; overflow: hidden;
        }
        #obs-titlebar {
            height: 5; min-height: 5; padding: 0 2;
            background: $surface-lighten-1; color: $text;
            align: left middle; border-bottom: round $border;
        }
        #obs-title { text-style: bold; width: 1fr; }
        #obs-body { padding: 1 2; height: auto; max-height: 24; }
        #obs-actions { height: 3; align: right middle; padding: 0 2; background: $surface-darken-1; }
        """
        BINDINGS = [Binding("escape", "dismiss_modal", "Close", show=False)]

        def compose(self):
            with Vertical(id="obs-box"):
                with Horizontal(id="obs-titlebar"):
                    yield Static("🔍  CAT Observability Center", id="obs-title")
                    yield Button("✕", id="obs-close", classes="cct-modal-close-btn")
                with Vertical(id="obs-body"):
                    from ..observability import observability_center
                    hlth = observability_center.get_health_status()
                    m = hlth["metrics"]

                    yield Static(f"Health Status: [b green]{hlth['status'].upper()}[/]", markup=True)
                    yield Static(f"Provider Calls: {m['total_provider_calls']} · Latency: avg {m['avg_latency_ms']}ms (p95 {m['p95_latency_ms']}ms)")
                    yield Static(f"Tokens / Cost: {m['total_tokens']} tokens · ${m['estimated_cost_usd']:.4f} USD")
                    yield Static(f"Tool Executions: {m['tool_executions']} (Success Rate: {m['tool_success_rate_percent']}%)")
                    yield Static(f"Extension / MCP Errors: {m['extension_errors']} / {m['mcp_errors']}")

                    yield Static("\\nRecent Distributed Traces:", classes="cct-modal-section-title")
                    traces = observability_center.list_recent_traces(4)
                    if traces:
                        for tr in traces:
                            yield Static(f"• [{tr['component'].upper()}] {tr['name']} - {tr['duration_ms']:.1f}ms ({tr['status']})")
                    else:
                        yield Static("No execution traces recorded yet.")
                with Horizontal(id="obs-actions"):
                    yield Button("Export Logs", id="obs-export-btn", variant="primary")
                    yield Button("Close", id="obs-close-btn")

        def on_button_pressed(self, event):
            if event.button.id in ("obs-close", "obs-close-btn"):
                self.dismiss(None)
            elif event.button.id == "obs-export-btn":
                from ..observability import observability_center
                p = observability_center.export_logs()
                self.app._system_note(f"Observability logs exported to: {p}")
                self.dismiss(None)

        def action_dismiss_modal(self):
            self.dismiss(None)


    class RecoveryManagerScreen(Screen):
        """Interactive Recovery & Rollback Engine Modal."""
        CSS = """
        RecoveryManagerScreen { align: center middle; background: rgba(0, 0, 0, 0.75); }
        #rec-box {
            width: 86; max-width: 96%; height: auto; max-height: 85%;
            background: $surface; border: round $accent; padding: 0;
            layout: vertical; overflow: hidden;
        }
        #rec-titlebar {
            height: 5; min-height: 5; padding: 0 2;
            background: $surface-lighten-1; color: $text;
            align: left middle; border-bottom: round $border;
        }
        #rec-title { text-style: bold; width: 1fr; }
        #rec-body { padding: 1 2; height: auto; max-height: 24; }
        #rec-actions { height: 3; align: right middle; padding: 0 2; background: $surface-darken-1; }
        """
        BINDINGS = [Binding("escape", "dismiss_modal", "Close", show=False)]

        def compose(self):
            with Vertical(id="rec-box"):
                with Horizontal(id="rec-titlebar"):
                    yield Static("🛡️  CAT Recovery & Rollback Engine", id="rec-title")
                    yield Button("✕", id="rec-close", classes="cct-modal-close-btn")
                with Vertical(id="rec-body"):
                    from ..core.recovery_engine import recovery_engine
                    st = recovery_engine.get_status()

                    yield Static(f"Total Snapshots: [b]{st['total_checkpoints']}[/]", markup=True)
                    yield Static(f"Undo Available: {'Yes' if st['undo_available'] else 'No'} · Redo Available: {'Yes' if st['redo_available'] else 'No'}")
                    yield Static(f"Active Transaction: {st['active_transaction'] or 'None'}")

                    yield Static("\\nRecent Recovery Checkpoints:", classes="cct-modal-section-title")
                    hist = recovery_engine.get_history(5)
                    if hist:
                        for h in hist:
                            yield Static(f"• [{h['id']}] {h['description']} ({h['files_count']} files)")
                    else:
                        yield Static("No checkpoints recorded yet.")
                with Horizontal(id="rec-actions"):
                    yield Button("Undo Last", id="rec-undo-btn", variant="warning")
                    yield Button("Close", id="rec-close-btn")

        def on_button_pressed(self, event):
            if event.button.id in ("rec-close", "rec-close-btn"):
                self.dismiss(None)
            elif event.button.id == "rec-undo-btn":
                from ..core.recovery_engine import recovery_engine
                ok, msg = recovery_engine.undo()
                self.app._system_note(msg)
                self.dismiss(None)

        def action_dismiss_modal(self):
            self.dismiss(None)


    class MultiWorkspaceScreen(Screen):
        """Interactive Multi-Workspace Manager Modal."""
        CSS = """
        MultiWorkspaceScreen { align: center middle; background: rgba(0, 0, 0, 0.75); }
        #mws-box {
            width: 86; max-width: 96%; height: auto; max-height: 85%;
            background: $surface; border: round $accent; padding: 0;
            layout: vertical; overflow: hidden;
        }
        #mws-titlebar {
            height: 5; min-height: 5; padding: 0 2;
            background: $surface-lighten-1; color: $text;
            align: left middle; border-bottom: round $border;
        }
        #mws-title { text-style: bold; width: 1fr; }
        #mws-body { padding: 1 2; height: auto; max-height: 24; }
        #mws-actions { height: 3; align: right middle; padding: 0 2; background: $surface-darken-1; }
        """
        BINDINGS = [Binding("escape", "dismiss_modal", "Close", show=False)]

        def compose(self):
            with Vertical(id="mws-box"):
                with Horizontal(id="mws-titlebar"):
                    yield Static("📂  CAT Multi-Workspace Manager", id="mws-title")
                    yield Button("✕", id="mws-close", classes="cct-modal-close-btn")
                with Vertical(id="mws-body"):
                    from ..multi_workspace import multi_workspace
                    st = multi_workspace.get_status()
                    active = st.get("active_workspace") or {}

                    yield Static(f"Active Workspace: [b green]{active.get('name', 'None')}[/]", markup=True)
                    yield Static(f"Project Path: `{active.get('path', 'None')}`")
                    yield Static(f"Detected Languages: {', '.join(active.get('languages', [])) or 'None'}")

                    yield Static("\\nRegistered Workspaces:", classes="cct-modal-section-title")
                    for w in st.get("all_workspaces", [])[:5]:
                        is_cur = " (Active)" if w["id"] == active.get("id") else ""
                        yield Static(f"• [b]{w['name']}[/]{is_cur} — `{w['path']}`", markup=True)
                with Horizontal(id="mws-actions"):
                    yield Button("Close", id="mws-close-btn")

        def on_button_pressed(self, event):
            if event.button.id in ("mws-close", "mws-close-btn"):
                self.dismiss(None)

        def action_dismiss_modal(self):
            self.dismiss(None)
'''

with open('calc_terminal/ui/platform_screens.py', 'r', encoding='utf-8') as f:
    orig = f.read()

with open('calc_terminal/ui/platform_screens.py', 'w', encoding='utf-8') as f:
    f.write(orig + new_screens)

print("SUCCESS: Appended new screens to platform_screens.py")

