"""
CCT UI — ActivityPanel (v0.7.8.1 Live Thinking panel).

A small live popup (Ctrl+T) showing the state of the turn currently
in flight — the "live thinking" surface the spec asks for:

  spinner + stage ......... live (thinking.detect_stage, same engine
                            as the composer's status bar)
  elapsed timer ........... live
  tokens streamed ......... live chunk counter from the worker
  files touched ........... agent/pipeline tool steps with a path
  last tool step .......... most recent agent tool (name + target)
  provider / model ........ from aicore config
  session usage ........... requests + total tokens (aicore)

It never pokes widget internals: CCTApp._activity is a plain dict of
counters the workers bump (see _stream_worker / _pipeline_worker),
and the stage/timer recomputation reads the composer's streaming
state through tiny defensive getters. When nothing is running it
reports "idle" honestly instead of faking activity.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import time

TEXTUAL_AVAILABLE = True
try:
    from textual.screen import Screen
    from textual.containers import Vertical, Horizontal
    from textual.widgets import Static, Button
    from textual.binding import Binding
except Exception:
    TEXTUAL_AVAILABLE = False

if TEXTUAL_AVAILABLE:
    from . import thinking
    from . import theme_css


    class ActivityPanel(Screen):
        """Live activity popup for the in-flight turn (Ctrl+T)."""

        CSS = """
        ActivityPanel { align: center middle; background: $app-background 70%; }
        #act-box {
            width: 62; height: auto; max-height: 90%;
            background: $surface; border: round $border; padding: 0;
            opacity: 0; offset-y: 1;
            transition: opacity 150ms, offset 180ms;
        }
        #act-box.open { opacity: 1; offset-y: 0; }
        #act-titlebar { height: 3; padding: 1 2 0 2; border-bottom: solid $border; }
        #act-title { text-style: bold; width: 1fr; }
        #act-body { padding: 1 2; overflow-y: auto; }
        #act-stage { height: 1; }
        #act-stats { height: 8; padding-top: 1; color: $text-muted; }
        #act-usage { height: 2; padding-top: 1; color: $text-faint; }
        #act-actions { height: 5; padding: 0 2 1 2; border-top: solid $border; }
        #act-actions Button { margin-right: 1; }
        .act-hint { color: $text-faint; padding: 0 2 1 2; }
        """

        BINDINGS = [Binding("escape", "cancel", "Cancel")]

        def __init__(self):
            super().__init__()
            self._spin_tick = 0

        def compose(self):
            with Vertical(id="act-box"):
                with Horizontal(id="act-titlebar"):
                    yield Static("\U0001f9e0  Live Activity", id="act-title")
                    yield Button("\u2715", id="act-close", classes="cct-popup-close")
                with Vertical(id="act-body"):
                    yield Static("", id="act-stage")
                    yield Static("", id="act-stats")
                    yield Static("", id="act-usage")
                with Horizontal(id="act-actions"):
                    yield Button("\u23f9 Stop", id="act-stop", variant="error", classes="cct-btn")
                    yield Button("Close", id="act-close-btn", classes="cct-btn")
                yield Static("Esc to close", classes="act-hint")

        def on_mount(self):
            self.call_after_refresh(lambda: self.query_one("#act-box").add_class("open"))
            self.call_after_refresh(self._fit)
            # Cache the activity module once at mount, not every 100ms tick
            try:
                from .. import activity as _act_mod
                self._act_mod = _act_mod
            except Exception:
                self._act_mod = None
            self._timer = self.set_interval(0.1, self._refresh)

        def on_unmount(self):
            # Mirror ActivityStreamPanel: the 100ms refresh ticker is
            # owned by this screen and must stop when it closes.
            try:
                if getattr(self, "_timer", None) is not None:
                    self._timer.stop()
            except Exception:
                pass
            self._timer = None

        def on_resize(self, event):
            self._fit()

        def _fit(self):
            try:
                self.call_after_refresh(
                    lambda: theme_css.fit_dialog(self, "act-box", "act-body"))
            except Exception:
                pass

        def _refresh(self):
            try:
                self._spin_tick += 1
                app = self.app
                streaming = bool(getattr(app, "_is_streaming", False))
                # ── REAL activity: single source of truth ──
                _act = self._act_mod
                if _act is not None:
                    tid = getattr(app, "_streaming_turn_id", None) or getattr(app.composer, "_stream_turn_id", None)
                    acts = _act.manager.get_for_turn(tid) if tid else []
                    running = [a for a in acts if a.status in (_act.RUNNING, _act.PENDING, _act.WAITING)]
                    target = running[-1] if running else (acts[-1] if acts else None)
                    if target:
                        # real data
                        elapsed = target.elapsed_time
                        # spinner by status
                        if target.status == _act.RUNNING:
                            spin = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"][self._spin_tick % 10]
                            color = theme_css.current_hex("accent")
                        elif target.status == _act.WAITING:
                            spin = "?"
                            color = theme_css.current_hex("warning")
                        elif target.status == _act.FAILED:
                            spin = "✕"
                            color = theme_css.current_hex("error")
                        elif target.status == _act.COMPLETED:
                            spin = "✓"
                            color = theme_css.current_hex("success")
                        else:
                            spin = "●"
                            color = theme_css.current_hex("text-faint")
                        title = target.title or target.current_step or "Working"
                        prov = f"{target.provider} {target.model}".strip() or f"{target.provider or ''} {target.model or ''}".strip()
                        if not prov:
                            try:
                                from .. import aicore as _ac
                                cfg = _ac.load_config()
                                prov = f"{(cfg.get('provider') or '').upper()} {cfg.get('model') or ''}".strip()
                            except Exception:
                                prov = "—"
                        stage_box = self.query_one("#act-stage", Static)
                        stage_box.update(f"[{color}]{spin}[/] [{color}]{title}[/]  ·  [{color}]{target.status}[/]  ·  {target.elapsed_time:.1f}s")
                        # stats from real activity
                        lines = [
                            f"  [{theme_css.current_hex('text-faint')}]elapsed[/]      {target.elapsed_time:.1f}s",
                            f"  [{theme_css.current_hex('text-faint')}]status[/]       {target.status}",
                            f"  [{theme_css.current_hex('text-faint')}]provider[/]    {prov or '—'}",
                            f"  [{theme_css.current_hex('text-faint')}]progress[/]    {int((target.progress or 0)*100)}%" if target.progress is not None else f"  [{theme_css.current_hex('text-faint')}]progress[/]    —",
                            f"  [{theme_css.current_hex('text-faint')}]workspace[/]   {target.workspace or '—'}",
                        ]
                        if target.file:
                            lines.append(f"  [{theme_css.current_hex('text-faint')}]file[/]         {target.file}")
                        if target.command:
                            lines.append(f"  [{theme_css.current_hex('text-faint')}]command[/]      {target.command[:40]}")
                        if target.error:
                            lines.append(f"  [{theme_css.current_hex('text-faint')}]error[/]        {target.error[:60]}")
                        stats_box = self.query_one("#act-stats", Static)
                        stats_box.update("\n".join(lines))
                        # usage
                        try:
                            from .. import aicore
                            usage = aicore.get_session_usage()
                        except Exception:
                            usage = {}
                        usage_box = self.query_one("#act-usage", Static)
                        if isinstance(usage, dict):
                            usage_box.update(
                                "  session: "
                                f"{usage.get('requests', 0)} requests · "
                                f"{usage.get('prompt_tokens', 0)} prompt · "
                                f"{usage.get('completion_tokens', 0)} completion · "
                                f"{usage.get('total_tokens', 0)} total")
                        stop_btn = self.query_one("#act-stop", Button)
                        stop_btn.display = streaming and target.cancellable
                        return
                # fallback: no real activity -> idle (never fake)
                stage_box = self.query_one("#act-stage", Static)
                stats_box = self.query_one("#act-stats", Static)
                usage_box = self.query_one("#act-usage", Static)
                stop_btn = self.query_one("#act-stop", Button)
                stop_btn.display = streaming
                if not streaming:
                    stage_box.update(f"[{theme_css.current_hex('text-faint')}]⎺ Idle — no turn in flight[/]")
                    stats_box.update(f"  [{theme_css.current_hex('text-faint')}]No active tasks[/]\n  start a message to watch it live.")
                    usage_box.update("")
                else:
                    # streaming but no activity yet -> minimal real spinner
                    spin = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"][self._spin_tick % 10]
                    color = theme_css.current_hex("accent")
                    stage_box.update(f"[{color}]{spin}[/] [{color}]Working…[/]  ·  {time.time() - (getattr(app, '_activity', {}).get('start') or time.time()):.1f}s")
                    stats_box.update("  preparing real activity…")
                    usage_box.update("")
            except Exception:
                pass

        def action_cancel(self):
            self.dismiss(None)

        def on_button_pressed(self, event):
            eid = event.button.id
            if eid in ("act-close", "act-close-btn"):
                self.dismiss(None)
            elif eid == "act-stop":
                try:
                    self.app.action_cancel_streaming()
                except Exception:
                    pass

        def on_key(self, event):
            if event.key == "escape":
                self.dismiss(None)

else:
    ActivityPanel = None
