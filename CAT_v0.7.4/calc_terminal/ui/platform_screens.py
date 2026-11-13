"""
CAT Platform Screens (v0.7.9 Complete Platform Expansion)

Textual modal screens and dashboards for Security Center, Database Studio,
AI Cost Manager, Deployment Center, Code Intelligence, and Workflows.
"""

from typing import Optional, List, Dict, Any

TEXTUAL_AVAILABLE = True
try:
    from textual.screen import Screen
    from textual.containers import Vertical, Horizontal, VerticalScroll
    from textual.widgets import Static, Button, Input, DataTable
    from textual.binding import Binding
except Exception:
    TEXTUAL_AVAILABLE = False

if TEXTUAL_AVAILABLE:
    class SecurityCenterScreen(Screen):
        """Interactive Security Center Modal."""
        CSS = """
        SecurityCenterScreen { align: center middle; background: rgba(0, 0, 0, 0.75); }
        #sec-box {
            width: 82; max-width: 96%; height: auto; max-height: 85%;
            background: $surface; border: round $accent; padding: 0;
            layout: vertical; overflow: hidden;
        }
        #sec-titlebar {
            height: 5; min-height: 5; padding: 0 2;
            border-bottom: solid $border; layout: horizontal; align: center middle;
            background: $surface-darken-1;
        }
        #sec-title { width: 1fr; text-style: bold; color: $text; }
        #sec-body { height: 1fr; overflow-y: auto; padding: 1 2; }
        .sec-stat-card {
            background: $surface-darken-2; border: round $border;
            padding: 1 2; margin-bottom: 1; height: auto;
        }
        .sec-score { text-style: bold; color: $accent; }
        .sec-finding-row { padding: 0 1; margin-bottom: 1; border-left: thick $warning; }
        #sec-actions {
            height: 4; min-height: 4; padding: 0 2;
            border-top: solid $border; background: $surface-darken-1;
            layout: horizontal; align: right middle;
        }
        #sec-actions Button { margin-left: 1; min-width: 12; height: 3; }
        """
        BINDINGS = [Binding("escape", "dismiss_modal", "Close")]

        def compose(self):
            with Vertical(id="sec-box"):
                with Horizontal(id="sec-titlebar"):
                    yield Static("🛡️  CAT Security & Compliance Center", id="sec-title")
                    yield Button("✕", id="sec-close", classes="cct-modal-close-btn")
                with Vertical(id="sec-body"):
                    from ..security_center import get_security_center
                    from .. import workspace as _ws
                    import os
                    root = _ws.root_dir() if hasattr(_ws, 'root_dir') else os.getcwd()
                    audit = get_security_center().run_full_security_audit(root)

                    score = audit.get("security_score", 100)
                    status = audit.get("status", "GOOD")
                    perm_label = audit.get("permission_label", "Ask Every Time")

                    with Vertical(classes="sec-stat-card"):
                        yield Static(f"Security Posture Score: [b]{score}/100[/] ({status})", markup=True)
                        yield Static(f"Active Permission Guard: [b]{perm_label}[/]", markup=True)
                        yield Static(f"Scanned Files: {audit['secrets']['scanned_files']} | Secret Findings: {audit['secrets']['findings_count']} | Code Hazards: {audit['code_safety']['hazards_count']}")

                    yield Static("Remediation Actions:", classes="cct-modal-section-title")
                    rems = audit.get("remediations", [])
                    if rems:
                        for r in rems:
                            yield Static(f"• {r}")
                    else:
                        yield Static("✓ No critical vulnerabilities detected in current workspace.")
                with Horizontal(id="sec-actions"):
                    yield Button("Close", id="sec-close-btn", variant="primary")

        def on_button_pressed(self, event):
            if event.button.id in ("sec-close", "sec-close-btn"):
                self.dismiss(None)

        def action_dismiss_modal(self):
            self.dismiss(None)


    class DatabaseStudioScreen(Screen):
        """Interactive Database Studio Modal."""
        CSS = """
        DatabaseStudioScreen { align: center middle; background: rgba(0, 0, 0, 0.75); }
        #db-box {
            width: 86; max-width: 96%; height: auto; max-height: 85%;
            background: $surface; border: round $accent; padding: 0;
            layout: vertical; overflow: hidden;
        }
        #db-titlebar {
            height: 5; min-height: 5; padding: 0 2;
            border-bottom: solid $border; layout: horizontal; align: center middle;
            background: $surface-darken-1;
        }
        #db-title { width: 1fr; text-style: bold; color: $text; }
        #db-body { height: 1fr; overflow-y: auto; padding: 1 2; }
        #db-query-input { width: 100%; height: 3; margin: 1 0; }
        #db-actions {
            height: 4; min-height: 4; padding: 0 2;
            border-top: solid $border; background: $surface-darken-1;
            layout: horizontal; align: right middle;
        }
        #db-actions Button { margin-left: 1; min-width: 12; height: 3; }
        """
        BINDINGS = [Binding("escape", "dismiss_modal", "Close")]

        def compose(self):
            with Vertical(id="db-box"):
                with Horizontal(id="db-titlebar"):
                    yield Static("🗄️  CAT Database Studio", id="db-title")
                    yield Button("✕", id="db-close", classes="cct-modal-close-btn")
                with Vertical(id="db-body"):
                    from ..db_studio import get_db_studio
                    studio = get_db_studio()
                    tables = studio.get_tables()
                    yield Static("Connected Database: SQLite (:memory: / workspace)", classes="cct-modal-section-title")
                    if tables:
                        t_str = ", ".join(f"{t['name']} ({t['row_count']} rows)" for t in tables)
                        yield Static(f"Tables: {t_str}")
                    else:
                        yield Static("No user tables found in database. Run a CREATE TABLE or connect a file.")
                    yield Input(placeholder="SELECT * FROM table LIMIT 10", id="db-query-input")
                    yield Static("Tip: Use `/db connect <path>` to attach a SQLite database file.", classes="cct-modal-meta")
                with Horizontal(id="db-actions"):
                    yield Button("Run Query", id="db-run-btn", variant="primary")
                    yield Button("Close", id="db-close-btn")

        def on_button_pressed(self, event):
            if event.button.id in ("db-close", "db-close-btn"):
                self.dismiss(None)
            elif event.button.id == "db-run-btn":
                inp = self.query_one("#db-query-input", Input)
                q = inp.value.strip()
                if q:
                    from ..db_studio import get_db_studio
                    res = get_db_studio().execute_query(q)
                    self.app._system_note(f"DB Query executed: {res.get('row_count', res.get('rows_affected', 0))} records in {res.get('duration_ms', 0)}ms")
                self.dismiss(None)

        def action_dismiss_modal(self):
            self.dismiss(None)


    class AICostManagerScreen(Screen):
        """Interactive AI Cost & Usage Modal."""
        CSS = """
        AICostManagerScreen { align: center middle; background: rgba(0, 0, 0, 0.75); }
        #cost-box {
            width: 80; max-width: 96%; height: auto; max-height: 85%;
            background: $surface; border: round $accent; padding: 0;
            layout: vertical; overflow: hidden;
        }
        #cost-titlebar {
            height: 5; min-height: 5; padding: 0 2;
            border-bottom: solid $border; layout: horizontal; align: center middle;
            background: $surface-darken-1;
        }
        #cost-title { width: 1fr; text-style: bold; color: $text; }
        #cost-body { height: 1fr; overflow-y: auto; padding: 1 2; }
        .cost-card {
            background: $surface-darken-2; border: round $border;
            padding: 1 2; margin-bottom: 1; height: auto;
        }
        #cost-actions {
            height: 4; min-height: 4; padding: 0 2;
            border-top: solid $border; background: $surface-darken-1;
            layout: horizontal; align: right middle;
        }
        #cost-actions Button { margin-left: 1; min-width: 12; height: 3; }
        """
        BINDINGS = [Binding("escape", "dismiss_modal", "Close")]

        def compose(self):
            with Vertical(id="cost-box"):
                with Horizontal(id="cost-titlebar"):
                    yield Static("💰  CAT AI Usage & Cost Manager", id="cost-title")
                    yield Button("✕", id="cost-close", classes="cct-modal-close-btn")
                with Vertical(id="cost-body"):
                    from ..ai_cost_manager import get_ai_cost_manager
                    mgr = get_ai_cost_manager()
                    summary = mgr.get_summary()

                    with Vertical(classes="cost-card"):
                        yield Static(f"Total AI Calls: [b]{summary['total_calls']}[/]", markup=True)
                        yield Static(f"Total Tokens: [b]{summary['total_tokens']:,}[/] (In: {summary['prompt_tokens']:,} / Out: {summary['completion_tokens']:,})", markup=True)
                        yield Static(f"Estimated Spend: [b]${summary['total_cost_usd']:.4f}[/] / Budget: ${summary['budget_limit_usd']:.2f} ({summary['budget_used_percent']}% used)", markup=True)

                    yield Static("Breakdown by Model:", classes="cct-modal-section-title")
                    models = summary.get("by_model", {})
                    if models:
                        for m, data in models.items():
                            yield Static(f"• {m}: {data['calls']} calls, {data['tokens']:,} tokens, ${data['cost_usd']:.4f}")
                    else:
                        yield Static("No API calls recorded in current billing window.")
                with Horizontal(id="cost-actions"):
                    yield Button("Reset Usage", id="cost-reset-btn")
                    yield Button("Close", id="cost-close-btn", variant="primary")

        def on_button_pressed(self, event):
            if event.button.id in ("cost-close", "cost-close-btn"):
                self.dismiss(None)
            elif event.button.id == "cost-reset-btn":
                from ..ai_cost_manager import get_ai_cost_manager
                get_ai_cost_manager().reset_usage()
                self.app._system_note("AI usage counters reset.")
                self.dismiss(None)

        def action_dismiss_modal(self):
            self.dismiss(None)


    class DeploymentCenterScreen(Screen):
        """Interactive Deployment Center Modal."""
        CSS = """
        DeploymentCenterScreen { align: center middle; background: rgba(0, 0, 0, 0.75); }
        #dep-box {
            width: 82; max-width: 96%; height: auto; max-height: 85%;
            background: $surface; border: round $accent; padding: 0;
            layout: vertical; overflow: hidden;
        }
        #dep-titlebar {
            height: 5; min-height: 5; padding: 0 2;
            border-bottom: solid $border; layout: horizontal; align: center middle;
            background: $surface-darken-1;
        }
        #dep-title { width: 1fr; text-style: bold; color: $text; }
        #dep-body { height: 1fr; overflow-y: auto; padding: 1 2; }
        .dep-card {
            background: $surface-darken-2; border: round $border;
            padding: 1 2; margin-bottom: 1; height: auto;
        }
        #dep-actions {
            height: 4; min-height: 4; padding: 0 2;
            border-top: solid $border; background: $surface-darken-1;
            layout: horizontal; align: right middle;
        }
        #dep-actions Button { margin-left: 1; min-width: 12; height: 3; }
        """
        BINDINGS = [Binding("escape", "dismiss_modal", "Close")]

        def compose(self):
            with Vertical(id="dep-box"):
                with Horizontal(id="dep-titlebar"):
                    yield Static("🚀  CAT Deployment Center", id="dep-title")
                    yield Button("✕", id="dep-close", classes="cct-modal-close-btn")
                with Vertical(id="dep-body"):
                    from ..deployment_center import get_deployment_center
                    from .. import workspace as _ws
                    import os
                    root = _ws.root_dir() if hasattr(_ws, 'root_dir') else os.getcwd()
                    center = get_deployment_center()
                    proj = center.detect_project_type(root)

                    with Vertical(classes="dep-card"):
                        yield Static(f"Detected Project: [b]{proj['project_type']}[/]", markup=True)
                        yield Static(f"Build Command: [b]{proj.get('build_command') or 'None'}[/]", markup=True)
                        yield Static(f"Recommended Targets: {', '.join(proj['recommended_targets'])}")

                    yield Static("Recent Deployments:", classes="cct-modal-section-title")
                    history = center.get_history()
                    if history:
                        for h in history[:5]:
                            yield Static(f"• [{h['target'].upper()}] {h['status']} - {h['log_summary']} ({h.get('url') or 'local'})")
                    else:
                        yield Static("No previous deployment records found.")
                with Horizontal(id="dep-actions"):
                    yield Button("Dry-Run Deploy", id="dep-dry-btn", variant="primary")
                    yield Button("Close", id="dep-close-btn")

        def on_button_pressed(self, event):
            if event.button.id in ("dep-close", "dep-close-btn"):
                self.dismiss(None)
            elif event.button.id == "dep-dry-btn":
                from ..deployment_center import get_deployment_center
                from .. import workspace as _ws
                import os
                root = _ws.root_dir() if hasattr(_ws, 'root_dir') else os.getcwd()
                rec = get_deployment_center().deploy("local_build", root, dry_run=True)
                self.app._system_note(f"Dry-run deployment succeeded: {rec.url}")
                self.dismiss(None)

        def action_dismiss_modal(self):
            self.dismiss(None)


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
            background: $surface-light; color: $text;
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

                    yield Static("\nRecent Distributed Traces:", classes="cct-modal-section-title")
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
            background: $surface-light; color: $text;
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

                    yield Static("\nRecent Recovery Checkpoints:", classes="cct-modal-section-title")
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
            background: $surface-light; color: $text;
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

                    yield Static("\nRegistered Workspaces:", classes="cct-modal-section-title")
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
