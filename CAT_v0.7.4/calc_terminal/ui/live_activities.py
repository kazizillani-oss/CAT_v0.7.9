"""
CAT UI — Live Activities inline widget (v0.7.9 Real-Time Live Agent Activity System).

Renders the live activity timeline INSIDE the chat conversation.
Order enforced by ConversationView: USER TASK block -> LIVE ACTIVITIES -> AGENT RESPONSE.

Every activity displayed comes from a REAL backend Activity event (calc_terminal.activity)
— NEVER fake animations or placeholder progress.

Features:
 - Sleek terminal-native timeline with phase headers (DISCOVERY, ANALYSIS, IMPLEMENTATION, VALIDATION, COMPLETE)
 - Active spinner (◐ ◓ ◑ ◒) on currently running items only; clean static symbols (✓, ✕, ⊘) on finished items
 - Left accent border on running/expanded items only — no oversized heavy 3D boxes
 - Parent/child hierarchy grouping for multi-step tools
 - Compact default view + expandable detail area on tap/click/Enter/Space
 - WAITING_PERMISSION interactive inline card
 - Auto-scroll with user scroll pause & '↓ New activity' jump button
 - Respects all CAT themes through Textual CSS variables
 - Hidden completely until real activities exist
"""

from __future__ import annotations

import re
import textwrap
import time
from typing import Optional, Dict, List, Any

TEXTUAL_AVAILABLE = True
try:
    from textual.widgets import Static
    from textual.containers import Vertical, Horizontal
    from textual.binding import Binding
    from textual.message import Message
except Exception:
    TEXTUAL_AVAILABLE = False
    class Message:
        pass
    Static = object
    Vertical = object
    Horizontal = object

if TEXTUAL_AVAILABLE:
    from .. import activity as act_mod
    from . import theme_css

    # ── helpers ──────────────────────────────────────────────────────────
    def _fmt_duration(ms: int) -> str:
        if ms < 1000:
            return f"{ms}ms"
        s = ms / 1000.0
        if s < 60:
            return f"{s:.1f}s"
        m = int(s // 60)
        r = s % 60
        return f"{m}m {r:.0f}s"

    def _hex_for_status(status: str) -> str:
        try:
            vars_ = theme_css.css_variables()
        except Exception:
            vars_ = {}
        mapping = {
            act_mod.STATUS_RUNNING: vars_.get("accent", "#38bdf8"),
            act_mod.STATUS_STARTED: vars_.get("accent", "#38bdf8"),
            act_mod.STATUS_PENDING: vars_.get("text-faint", "#888888"),
            act_mod.STATUS_COMPLETED: vars_.get("success", "#22c55e"),
            act_mod.STATUS_FAILED: vars_.get("error", "#ef4444"),
            act_mod.STATUS_CANCELLED: vars_.get("text-faint", "#888888"),
            act_mod.STATUS_PAUSED: vars_.get("warning", "#eab308"),
            act_mod.STATUS_WAITING: vars_.get("warning", "#eab308"),
            act_mod.STATUS_WAITING_PERMISSION: vars_.get("warning", "#eab308"),
            act_mod.STATUS_WARNING: vars_.get("warning", "#eab308"),
        }
        return mapping.get(status, vars_.get("text-muted", "#cccccc"))

    # ── spinner frames per spec: ◐ ◓ ◑ ◒ ─────────────────────────────
    _SPINNER_FRAMES = ["◐", "◓", "◑", "◒"]

    def _spinner_for_tick(tick: int) -> str:
        return _SPINNER_FRAMES[tick % len(_SPINNER_FRAMES)]

    def _status_label(status: str) -> str:
        labels = {
            act_mod.STATUS_PENDING: "pending",
            act_mod.STATUS_STARTED: "started",
            act_mod.STATUS_RUNNING: "running",
            act_mod.STATUS_COMPLETED: "completed",
            act_mod.STATUS_FAILED: "failed",
            act_mod.STATUS_CANCELLED: "cancelled",
            act_mod.STATUS_PAUSED: "paused",
            act_mod.STATUS_WAITING: "waiting",
            act_mod.STATUS_WAITING_PERMISSION: "permission required",
            act_mod.STATUS_WARNING: "warning",
        }
        return labels.get(status, status)

    # ── Phase Header widget ──────────────────────────────────────────────
    class PhaseHeader(Static):
        """Clean visual divider between workflow phases."""
        def __init__(self, phase_name: str, **kwargs):
            self.phase_name = phase_name
            self.can_focus = False
            super().__init__(self._build_header(), classes="live-phase-header", **kwargs)

        def on_mount(self):
            self.update(self._build_header())

        def _build_header(self) -> str:
            icon = act_mod.PHASE_ICONS.get(self.phase_name, "●")
            faint = theme_css.current_hex("text-faint") if hasattr(theme_css, "current_hex") else "#666666"
            accent = theme_css.current_hex("accent") if hasattr(theme_css, "current_hex") else "#38bdf8"
            return f"[{accent} bold]{icon} {self.phase_name}[/] [{faint}]" + "─" * 28 + "[/]"

        def _render_header(self):
            self.update(self._build_header())

    # ── single activity row ──────────────────────────────────────────────
    class ActivityRow(Static):
        """
        One activity line: status icon + category/tool + target/query + duration/result.
        Expandable on click, tap, or Enter/Space.
        Keyboard accessible, touch-friendly.
        """

        def __init__(self, activity: act_mod.Activity, **kwargs):
            self.activity_id = activity.id
            self._activity = activity
            self._expanded = False
            self.can_focus = True
            sanitized_id = "act-" + re.sub(r"[^a-zA-Z0-9_-]", "_", str(activity.id))
            super().__init__(self._build_markup(), id=sanitized_id, classes="live-activity-row", **kwargs)

        def update_activity(self, activity: act_mod.Activity):
            self._activity = activity
            self._update_classes()
            self.update(self._build_markup())

        def _update_classes(self):
            st = self._activity.status
            if st in (act_mod.STATUS_RUNNING, act_mod.STATUS_STARTED):
                self.add_class("-running")
            else:
                self.remove_class("-running")
            if self._expanded:
                self.add_class("expanded")
            else:
                self.remove_class("expanded")

        def toggle_expand(self):
            self._expanded = not self._expanded
            self._update_classes()
            self.update(self._build_markup())

        def _build_markup(self) -> str:
            a = self._activity
            color = _hex_for_status(a.status)
            faint = theme_css.current_hex("text-faint") if hasattr(theme_css, "current_hex") else "#777777"
            muted = theme_css.current_hex("text-muted") if hasattr(theme_css, "current_hex") else "#aaaaaa"
            accent = theme_css.current_hex("accent") if hasattr(theme_css, "current_hex") else "#38bdf8"
            raw_details = (a.details or a.stdout or "").strip()
            is_model_metadata_only = raw_details.startswith("Model:") or raw_details.startswith("provider:")
            has_real_thoughts = bool(
                raw_details
                and not is_model_metadata_only
                and ("<think>" in raw_details or len(raw_details) > 30 or a.action == "thinking")
            )
            is_thinking = (
                a.action == "thinking"
                or a.title == "Reasoning & Thinking"
                or (has_real_thoughts and a.action != "generate")
            )

            # 1. Status Icon: rotating spinner for running, static for terminal states
            if a.status in (act_mod.STATUS_RUNNING, act_mod.STATUS_STARTED):
                tick = int(time.time() * 6) % len(_SPINNER_FRAMES)
                if is_thinking:
                    icon = f"[{accent}]🧠 {_spinner_for_tick(tick)}[/]"
                else:
                    icon = f"[{color}]{_spinner_for_tick(tick)}[/]"
            elif a.status == act_mod.STATUS_COMPLETED:
                if is_thinking:
                    icon = f"[{color}]🧠 ✓[/]"
                else:
                    icon = f"[{color}]✓[/]"
            elif a.status == act_mod.STATUS_FAILED:
                icon = f"[{color}]✕[/]"
            elif a.status == act_mod.STATUS_CANCELLED:
                icon = f"[{faint}]⊘[/]"
            elif a.status == act_mod.STATUS_WAITING_PERMISSION:
                icon = f"[{color} bold]⚠[/]"
            elif a.status == act_mod.STATUS_WAITING:
                icon = f"[{color}]?[/]"
            else:
                icon = f"[{color}]{act_mod.STATUS_ICONS.get(a.status, '·')}[/]"

            # 2. Hierarchy tree connectors if child
            if a.parent_id or a.parent_event_id:
                prefix = "  ├─ " if getattr(self, "_is_intermediate_child", False) else "  └─ "
            else:
                prefix = ""

            # 3. Handle interactive WAITING_PERMISSION state
            if a.status == act_mod.STATUS_WAITING_PERMISSION or (a.status == act_mod.STATUS_WAITING and a.type == act_mod.TYPE_PERMISSION):
                lines = [
                    f"{prefix}{icon} [{color} bold]Permission Required:[/] {a.title}",
                ]
                target = a.target_path or a.command or a.file or a.details
                if target:
                    lines.append(f"    [{faint}]Target:[/] {target[:70]}")
                lines.append(f"    [{accent} bold][A] Allow[/]   [{color} bold][D] Deny[/]  [{faint}](tap or press A/D)[/]")
                return "\n".join(lines)

            # 4. Standard Title & Summary
            title = a.title or a.action or a.tool or "Activity"
            if len(title) > 75:
                title = title[:72] + "..."

            # Real determinate progress only (no fake percentages)
            progress_txt = ""
            if a.progress is not None:
                try:
                    pct = int(float(a.progress) * 100)
                    progress_txt = f" [{accent}][{pct}%][/]"
                except Exception:
                    pass

            # Duration formatting
            duration_txt = ""
            if a.status in (act_mod.STATUS_COMPLETED, act_mod.STATUS_FAILED, act_mod.STATUS_CANCELLED, act_mod.STATUS_WARNING):
                if a.duration_ms:
                    duration_txt = f" [{faint}]{_fmt_duration(a.duration_ms)}[/]"
            elif a.status in (act_mod.STATUS_RUNNING, act_mod.STATUS_STARTED):
                elapsed = a.elapsed_ms
                duration_txt = f" [{faint}]{_fmt_duration(elapsed)}[/]"

            # Result tail on main line
            result_txt = ""
            if a.result:
                short_res = a.result.strip().splitlines()[0][:50]
                if a.status == act_mod.STATUS_COMPLETED:
                    result_txt = f" [{faint}]— {short_res}[/]"
                elif a.status == act_mod.STATUS_FAILED:
                    result_txt = f" [{color}]— {short_res}[/]"

            # Compact primary line
            status_badge = f" [{faint}]({_status_label(a.status)})[/]" if a.status in (act_mod.STATUS_WAITING, act_mod.STATUS_PAUSED) else ""
            text_color = theme_css.current_hex("text") if hasattr(theme_css, "current_hex") else "#ffffff"
            line = f"{prefix}{icon} [{text_color} bold]{title}[/]{status_badge}{progress_txt}{duration_txt}{result_txt}"

            if not self._expanded:
                if is_thinking and a.status in (act_mod.STATUS_RUNNING, act_mod.STATUS_STARTED):
                    thought_preview = (a.details or a.stdout or "").strip()
                    if thought_preview:
                        plines = [l.strip() for l in thought_preview.splitlines() if l.strip()]
                        if plines:
                            line += f"\n    [{faint} italic]💭 {plines[-1][:75]}[/]"
                    return line
                if is_thinking and a.status == act_mod.STATUS_COMPLETED:
                    line += f" [{accent}]› tap to view thoughts[/]"
                    return line
                has_details = bool(a.file or a.command or a.query or a.stdout or a.stderr or a.output_lines or a.error or a.diff_summary or a.lines_added or a.lines_removed or (a.details and len(a.details) > 30))
                if has_details:
                    line += f" [{accent}]›[/]"
                return line

            # 5. Expanded Detail View (100% authentic event metadata)
            lines = [line, ""]
            if is_thinking and (a.details or a.stdout):
                full_thought = (a.details or a.stdout or "").strip()
                dur_str = _fmt_duration(a.duration_ms or a.elapsed_ms)
                lines.append(f"  [{accent} bold]╭─ 💭 Thinking Process ({dur_str}) ──────────────────────────────────[/]")
                wrap_w = 82
                for paragraph in full_thought.splitlines():
                    cleaned_p = paragraph.strip()
                    if not cleaned_p:
                        lines.append(f"  [{accent}]│[/]")
                    else:
                        wrapped = textwrap.wrap(cleaned_p, width=wrap_w, break_long_words=True, replace_whitespace=False)
                        for w_line in wrapped:
                            lines.append(f"  [{accent}]│[/]  [{faint} italic]{w_line}[/]")
                lines.append(f"  [{accent} bold]╰───────────────────────────────────────────────────────────────────[/]")
                lines.append("")
            if a.event_id or a.id:
                lines.append(f"  [{faint}]Event ID:[/] [{accent}]{a.event_id or a.id}[/]")
            if a.event_type:
                lines.append(f"  [{faint}]Event Type:[/] [{text_color}]{a.event_type}[/]")
            if a.phase:
                lines.append(f"  [{faint}]Phase:[/] [{text_color}]{a.phase}[/]")
            if a.category:
                lines.append(f"  [{faint}]Category:[/] [{text_color}]{a.category}[/]")
            if a.query:
                lines.append(f"  [{faint}]Query:[/] [{text_color}]\"{a.query}\"[/]")
            if a.match_count is not None:
                lines.append(f"  [{faint}]Matches:[/] [{text_color}]{a.match_count}[/]")
            target_file = a.target_path or a.file
            if target_file:
                lines.append(f"  [{faint}]File:[/] [{text_color}]{target_file}[/]")
            if a.lines_added > 0 or a.lines_removed > 0:
                lines.append(f"  [{faint}]Diff Lines:[/] [green]+{a.lines_added}[/] [red]-{a.lines_removed}[/]")
            elif a.line_count is not None:
                lines.append(f"  [{faint}]Lines:[/] [{text_color}]{a.line_count}[/]")
            if a.diff_summary:
                lines.append(f"  [{faint}]Diff:[/] [{text_color}]{a.diff_summary}[/]")
            if a.command:
                cmd_txt = a.command[:120] + ("..." if len(a.command) > 120 else "")
                lines.append(f"  [{faint}]Command:[/] [{text_color}]{cmd_txt}[/]")
            if a.pid is not None:
                lines.append(f"  [{faint}]Process ID:[/] [{text_color}]{a.pid}[/]")
            if a.exit_code is not None:
                code_style = "green" if a.exit_code == 0 else "red"
                lines.append(f"  [{faint}]Exit Code:[/] [{code_style}]{a.exit_code}[/]")
            if a.error:
                lines.append(f"  [{color} bold]Error:[/] [{color}]{a.error[:300]}[/]")
            elif a.details and a.details != a.title and not (is_thinking and (a.details or a.stdout)):
                lines.append(f"  [{faint}]Details:[/] [{text_color}]{a.details[:200]}[/]")

            # Stderr or stdout tails
            if a.stderr:
                lines.append(f"  [{color}]Stderr:[/]")
                for l in a.stderr.strip().splitlines()[-6:]:
                    lines.append(f"    [{color}]{l[:120]}[/]")

            # Real output lines tail (max 8 lines)
            out_lines = a.output_lines or (a.stdout.strip().splitlines() if a.stdout else [])
            if out_lines:
                lines.append(f"  [{faint}]Output:[/]")
                for l in out_lines[-8:]:
                    lines.append(f"    [{muted}]{l[:120]}[/]")

            dur_display = _fmt_duration(a.duration_ms or a.elapsed_ms)
            lines.append(f"  [{faint}]Status:[/] [{color}]{a.status}[/]  [{faint}]Duration:[/] {dur_display}")
            lines.append(f"  [{faint} italic]tap to collapse (or Enter/Space)[/]")
            return "\n".join(lines)

        def on_click(self, event):
            # Check for permission action clicks
            if self._activity.status == act_mod.STATUS_WAITING_PERMISSION:
                self._handle_permission_decision("allow")
                event.stop()
                return
            self.toggle_expand()
            event.stop()

        def _handle_permission_decision(self, decision: str):
            req = self._activity.permission_req or {}
            cb = req.get("callback")
            if cb:
                try:
                    cb(decision)
                except Exception:
                    pass
            new_status = act_mod.STATUS_COMPLETED if decision == "allow" else act_mod.STATUS_FAILED
            act_mod.manager.update(self._activity.id, status=new_status, result=f"Permission {decision}ed")

        def on_key(self, event):
            if self._activity.status == act_mod.STATUS_WAITING_PERMISSION:
                if event.key in ("a", "A", "y", "Y"):
                    self._handle_permission_decision("allow")
                    event.stop()
                    return
                elif event.key in ("d", "D", "n", "N"):
                    self._handle_permission_decision("deny")
                    event.stop()
                    return
            if event.key in ("enter", "space"):
                self.toggle_expand()
                event.stop()

        def on_mount(self):
            self._update_classes()
            self.update(self._build_markup())


    # ── question activity: special waiting state with options ─────────────
    class QuestionActivityRow(ActivityRow):
        """Extends ActivityRow for question WAITING state with selectable options."""

        def __init__(self, activity: act_mod.Activity, options: Optional[List[Dict[str, Any]]] = None, callback=None, **kwargs):
            self._options = options or []
            self._callback = callback
            super().__init__(activity, **kwargs)

        def _build_markup(self) -> str:
            base = super()._build_markup()
            if self._activity.status == act_mod.STATUS_WAITING and self._options:
                faint = theme_css.current_hex("text-faint") if hasattr(theme_css, "current_hex") else "#888888"
                lines = [base, ""]
                lines.append(f"  [{faint}]Select Option:[/]")
                for idx, opt in enumerate(self._options, 1):
                    label = opt.get("label", opt.get("name", f"Option {idx}"))
                    lines.append(f"    [{faint}]{idx}.[/] {label}")
                lines.append(f"  [{faint}](press 1-{len(self._options)} or tap)[/]")
                return "\n".join(lines)
            return base

        def select_option(self, idx: int):
            if 0 <= idx < len(self._options):
                opt = self._options[idx]
                if self._callback:
                    try:
                        self._callback(opt, self._activity)
                    except Exception:
                        pass
                act_mod.manager.update(self._activity.id, status=act_mod.STATUS_COMPLETED, result=f"Selected: {opt.get('label', idx)}")

        def on_key(self, event):
            if self._activity.status == act_mod.STATUS_WAITING and event.key in [str(i) for i in range(1, 10)]:
                idx = int(event.key) - 1
                if idx < len(self._options):
                    self.select_option(idx)
                    event.stop()
                    return
            super().on_key(event)


    # ── container for a turn's activities ─────────────────────────────────
    class LiveActivitiesBlock(Vertical):
        """
        Inline Live Activities container.
        Subscribes to act_mod.manager for this turn_id.
        Lightweight, transparent, terminal-first timeline.
        Starts HIDDEN (self.display = False); only displays when real activities arrive.
        """

        DEFAULT_CSS = """
        LiveActivitiesBlock {
            width: 100%;
            height: auto;
            max-height: 28;
            background: $surface;
            border-top: tall $border;
            border-left: tall $border;
            border-bottom: tall $border;
            border-right: tall $border;
            padding: 0 1;
            margin: 0 0 1 0;
            overflow-x: hidden;
            overflow-y: hidden;
        }
        LiveActivitiesBlock.collapsed {
            height: auto;
            max-height: 4;
            min-height: 1;
            padding: 0 1;
            background: $surface;
            border-top: tall $border;
            border-left: tall $border;
            border-bottom: tall $border;
            border-right: tall $border;
            overflow: hidden;
        }
        LiveActivitiesBlock.collapsed #live-header {
            border-bottom: none;
        }
        LiveActivitiesBlock.collapsed #live-resource-bar {
            display: none;
        }
        #live-header {
            height: auto;
            min-height: 1;
            color: $text;
            text-style: bold;
            padding: 0 0;
            margin-bottom: 0;
            background: transparent;
            border-bottom: solid $border;
        }
        #live-header:hover {
            color: $accent;
            background: $surface-active;
        }
        #live-resource-bar {
            height: 1;
            min-height: 1;
            color: $text-muted;
            padding: 0 0;
            margin-bottom: 0;
            background: transparent;
            border-bottom: solid $border;
        }
        #live-body {
            height: auto;
            max-height: 26;
            padding: 0;
            overflow-y: auto;
            overflow-x: hidden;
            scrollbar-size-vertical: 0;
            scrollbar-size-horizontal: 0;
            scrollbar-gutter: auto;
            background: transparent;
        }
        .live-phase-header {
            height: 1;
            padding: 0 0;
            margin-top: 0;
            margin-bottom: 0;
            color: $accent;
            background: transparent;
        }
        .live-activity-row {
            height: auto;
            min-height: 1;
            width: 100%;
            padding: 0 1;
            margin: 0 0 0 0;
            color: $text;
            background: transparent;
            border: none;
            transition: background 100ms;
        }
        .live-activity-row:hover {
            background: $surface-active;
        }
        .live-activity-row.-running {
            background: $surface;
            border-left: wide $accent;
            padding-left: 1;
        }
        .live-activity-row.expanded {
            background: transparent;
            border-left: none;
            padding: 0 1 1 1;
            margin: 0 0 1 0;
        }
        #live-summary-card {
            display: none;
            height: auto;
            padding: 0 1;
            margin: 0 0 1 0;
            background: $surface;
            border-left: wide $success;
        }
        #live-summary-card.visible {
            display: block;
        }
        #live-scroll-btn {
            dock: bottom;
            width: auto;
            height: 1;
            margin: 0 1;
            padding: 0 2;
            background: $accent;
            color: $text;
            text-style: bold;
            display: none;
        }
        """

        def __init__(self, turn_id: str, title: str = "LIVE ACTIVITIES", collapsed: bool = False, **kwargs):
            sanitized_id = "live-" + re.sub(r"[^a-zA-Z0-9_-]", "_", str(turn_id))
            super().__init__(id=sanitized_id, classes="live-activities-block" + (" collapsed" if collapsed else ""), **kwargs)
            self.turn_id = turn_id
            self._title = title
            self._collapsed = collapsed
            self._rows: Dict[str, ActivityRow] = {}
            self._phases: Dict[str, PhaseHeader] = {}
            self._start_ts = time.time()
            self._completed = False
            self._auto_scroll_paused = False
            self._last_res_update = 0.0
            self.can_focus = True

        def compose(self):
            yield Static(self._title, id="live-header")
            yield Static(self._build_resource_markup(), id="live-resource-bar")
            yield Vertical(id="live-body")
            yield Static("", id="live-summary-card")
            yield Static("↓ New activity", id="live-scroll-btn")

        def _build_resource_markup(self) -> str:
            sample = act_mod.manager.get_resource_sample()
            accent = theme_css.current_hex("accent") if hasattr(theme_css, "current_hex") else "#38bdf8"
            faint = theme_css.current_hex("text-faint") if hasattr(theme_css, "current_hex") else "#888888"
            text_col = theme_css.current_hex("text") if hasattr(theme_css, "current_hex") else "#ffffff"
            warning_col = theme_css.current_hex("warning") if hasattr(theme_css, "current_hex") else "#eab308"

            # Genuine, non-simulated resource measurements
            ram_part = f"[{accent}]RAM:[/] [{text_col}]{sample.system_ram_used_gb:.1f}/{sample.system_ram_total_gb:.1f} GB ({sample.system_ram_percent:.0f}%)[/]"
            cat_part = f"[{accent}]CAT RSS:[/] [{text_col}]{sample.process_ram_mb:.0f} MB[/]"
            cpu_part = f"[{accent}]CPU:[/] [{text_col}]{sample.cpu_percent:.0f}%[/]"

            parts = [ram_part, cat_part, cpu_part]
            if sample.gpu_name:
                gpu_part = f"[{accent}]GPU:[/] [{text_col}]{sample.gpu_name[:16]}"
                if sample.gpu_vram_used_gb is not None and sample.gpu_vram_total_gb is not None:
                    gpu_part += f" ({sample.gpu_vram_used_gb:.1f}/{sample.gpu_vram_total_gb:.1f} GB)"
                gpu_part += "[/]"
                parts.append(gpu_part)
            else:
                parts.append(f"[{faint}]GPU: N/A[/]")

            if sample.warning_level in ("high", "critical"):
                parts.append(f"[{warning_col} bold]⚠ RAM {sample.warning_level.upper()}[/]")

            sep = f" [{faint}]│[/] "
            return sep.join(parts)

        def _build_summary_markup(self, summary: Dict[str, Any]) -> str:
            accent = theme_css.current_hex("accent") if hasattr(theme_css, "current_hex") else "#38bdf8"
            success = theme_css.current_hex("success") if hasattr(theme_css, "current_hex") else "#22c55e"
            error = theme_css.current_hex("error") if hasattr(theme_css, "current_hex") else "#ef4444"
            faint = theme_css.current_hex("text-faint") if hasattr(theme_css, "current_hex") else "#888888"
            text_col = theme_css.current_hex("text") if hasattr(theme_css, "current_hex") else "#ffffff"

            dur = summary.get('duration_str', '0s')
            completed_cnt = summary.get('completed', 0)
            failed_cnt = summary.get('failed', 0)
            total_cnt = summary.get('total_events', 0)

            lines = [
                f"[{success} bold]✓ SESSION SUMMARY[/] [{faint}]({dur})[/]  [{text_col}]{completed_cnt}/{total_cnt} completed[/]" + (f" [{error}]({failed_cnt} failed)[/]" if failed_cnt else ""),
            ]
            if summary.get("files_modified"):
                mods = ", ".join(summary["files_modified"][:3])
                if len(summary["files_modified"]) > 3:
                    mods += f" (+{len(summary['files_modified']) - 3} more)"
                lines.append(f"  [{faint}]Modified:[/] [{accent}]{mods}[/]")
            if summary.get("commands_executed"):
                lines.append(f"  [{faint}]Commands:[/] [{text_col}]{len(summary['commands_executed'])} executed[/]")
            if summary.get("tools_used"):
                lines.append(f"  [{faint}]Tools:[/] [{text_col}]{', '.join(summary['tools_used'][:4])}[/]")

            lines.append(f"  [{faint}]RAM Footprint:[/] [{text_col}]{summary.get('ram_used_gb', 0):.1f}/{summary.get('ram_total_gb', 0):.1f} GB ({summary.get('ram_percent', 0):.0f}%) | CAT RSS: {summary.get('process_ram_mb', 0):.0f} MB[/]")
            return "\n".join(lines)

        def on_mount(self):
            # Display immediately when mounted for a turn so real-time RAM & timeline are visible
            try:
                self.display = True
            except Exception:
                pass

            # Subscribe to activity manager
            try:
                self._sub = act_mod.manager.subscribe(self._on_activity_event)
            except Exception:
                self._sub = None

            # Check if activities already exist for this turn
            try:
                existing_acts = act_mod.manager.get_for_turn(self.turn_id)
                for act in existing_acts:
                    self._ensure_row(act, notify=False)
            except Exception:
                pass

            self._refresh_header()

            if self._collapsed:
                self._apply_collapsed(True)

            # Smooth spinner timer (120ms tick)
            try:
                self._anim_timer = self.set_interval(0.12, self._tick_animations)
            except Exception:
                self._anim_timer = None

        def on_unmount(self):
            if getattr(self, "_sub", None) is not None:
                try:
                    act_mod.manager.unsubscribe(self._sub)
                except Exception:
                    pass
                self._sub = None
            if getattr(self, "_anim_timer", None) is not None:
                try:
                    self._anim_timer.stop()
                except Exception:
                    pass
                self._anim_timer = None

        def _tick_animations(self):
            """Tick rotating spinners and live duration on running items, plus RAM resource monitor."""
            try:
                has_running = False
                for row in list(self._rows.values()):
                    if row._activity.status in (act_mod.STATUS_RUNNING, act_mod.STATUS_STARTED):
                        has_running = True
                        row.update_activity(row._activity)
                if has_running:
                    self._refresh_header()

                now = time.time()
                if now - getattr(self, "_last_res_update", 0.0) >= 1.0:
                    self._last_res_update = now
                    try:
                        res_bar = self.query_one("#live-resource-bar", Static)
                        res_bar.update(self._build_resource_markup())
                    except Exception:
                        pass
            except Exception:
                pass

        def _on_activity_event(self, activity: act_mod.Activity, change: str):
            if activity.turn_id != self.turn_id:
                return

            def _do_update():
                try:
                    self._ensure_row(activity, notify=True)
                    self._refresh_header()
                    self._auto_scroll_if_needed()
                except Exception:
                    pass

            try:
                self.app.call_from_thread(_do_update)
            except Exception:
                try:
                    _do_update()
                except Exception:
                    pass

        def _ensure_row(self, activity: act_mod.Activity, notify: bool = True):
            # Must be a REAL activity with title
            if not activity.title or not activity.title.strip():
                return

            try:
                body = self.query_one("#live-body", Vertical)
            except Exception:
                return

            existing = self._rows.get(activity.id)
            if existing is not None:
                # Update existing row in place
                try:
                    existing.update_activity(activity)
                except Exception:
                    pass
                return

            # Show container now that a real activity exists
            try:
                self.display = True
            except Exception:
                pass

            # Check phase header
            phase = activity.phase or act_mod.PHASE_IMPLEMENTATION
            if phase not in self._phases:
                header = PhaseHeader(phase)
                self._phases[phase] = header
                try:
                    body.mount(header)
                except Exception:
                    pass

            # Mount new row
            row = ActivityRow(activity)
            self._rows[activity.id] = row
            try:
                body.mount(row)
            except Exception:
                pass

            # Auto-expand if previously collapsed and new activity arrives
            if self._collapsed and not self._completed:
                self._apply_collapsed(False)

        def _refresh_header(self):
            try:
                hdr = self.query_one("#live-header", Static)
                count = len(self._rows)
                summary = act_mod.manager.turn_summary(self.turn_id)
                has_running = summary.get("running", 0) > 0 or summary.get("waiting", 0) > 0

                if self._completed and count == 0 and not has_running:
                    self.display = False
                    return
                else:
                    self.display = True

                accent = theme_css.current_hex("accent") if hasattr(theme_css, "current_hex") else "#38bdf8"
                faint = theme_css.current_hex("text-faint") if hasattr(theme_css, "current_hex") else "#888888"
                text_col = theme_css.current_hex("text") if hasattr(theme_css, "current_hex") else "#ffffff"
                success = theme_css.current_hex("success") if hasattr(theme_css, "current_hex") else "#22c55e"

                dur = _fmt_duration(summary.get("duration_ms", int((time.time() - self._start_ts) * 1000)))

                if self._collapsed:
                    hdr.update(f"[{accent} bold]▸ LIVE ACTIVITIES[/] [{success} bold]✓[/] [{text_col}]{count} {'step' if count == 1 else 'steps'}[/] [{faint}]· {dur} — click to expand[/]")
                else:
                    if has_running:
                        hdr.update(f"[{accent} bold]⚡ LIVE ACTIVITIES[/] [{accent} bold]● RUNNING[/] [{faint}]·[/] [{text_col}]{count} {'step' if count == 1 else 'steps'}[/] [{faint}]· {dur} (click to collapse)[/]")
                    else:
                        hdr.update(f"[{accent} bold]⚡ LIVE ACTIVITIES[/] [{success} bold]✓ COMPLETED[/] [{faint}]·[/] [{text_col}]{count} {'step' if count == 1 else 'steps'}[/] [{faint}]· {dur} (click to collapse)[/]")
            except Exception:
                pass

        def mark_completed(self):
            self._completed = True
            count = len(self._rows)
            summary = act_mod.manager.get_session_summary(self.turn_id)
            has_running = summary.get("running", 0) > 0 or summary.get("waiting", 0) > 0

            # Render authentic session summary card
            try:
                card = self.query_one("#live-summary-card", Static)
                card.update(self._build_summary_markup(summary))
                card.add_class("visible")
            except Exception:
                pass

            if count == 0 and not has_running:
                self.display = False
            else:
                self._apply_collapsed(True)

        def _apply_collapsed(self, collapsed: bool):
            self._collapsed = collapsed
            try:
                body = self.query_one("#live-body", Vertical)
                if collapsed:
                    self.add_class("collapsed")
                    body.display = False
                else:
                    self.remove_class("collapsed")
                    body.display = True
                self._refresh_header()
            except Exception:
                pass

        def _auto_scroll_if_needed(self):
            if self._auto_scroll_paused:
                return
            try:
                body = self.query_one("#live-body", Vertical)
                max_y = getattr(body, "max_scroll_y", 0)
                cur_y = getattr(body, "scroll_y", 0)
                if max_y - cur_y <= 2:
                    body.scroll_end(animate=False)
                    self._hide_scroll_btn()
                else:
                    self._show_scroll_btn()
            except Exception:
                pass

        def _show_scroll_btn(self):
            try:
                btn = self.query_one("#live-scroll-btn", Static)
                btn.display = True
            except Exception:
                pass

        def _hide_scroll_btn(self):
            try:
                btn = self.query_one("#live-scroll-btn", Static)
                btn.display = False
            except Exception:
                pass

        def on_click(self, event):
            target = getattr(event, "widget", None)
            target_id = getattr(target, "id", "")
            if target_id == "live-scroll-btn":
                self._auto_scroll_paused = False
                self._hide_scroll_btn()
                try:
                    body = self.query_one("#live-body", Vertical)
                    body.scroll_end(animate=True)
                except Exception:
                    pass
                event.stop()
                return

            # Header click toggles collapse
            if target_id == "live-header" or target is self:
                self._apply_collapsed(not self._collapsed)
                event.stop()

        def on_key(self, event):
            if event.key in ("enter", "space"):
                self._apply_collapsed(not self._collapsed)
                event.stop()

        def retheme(self):
            """Theme switch: re-render all rows & phase headers."""
            for ph in list(self._phases.values()):
                try:
                    ph._render_header()
                except Exception:
                    pass
            for row in list(self._rows.values()):
                try:
                    row.update_activity(row._activity)
                except Exception:
                    pass
            self._refresh_header()

        def clear(self):
            for row in list(self._rows.values()):
                try:
                    row.remove()
                except Exception:
                    pass
            for ph in list(self._phases.values()):
                try:
                    ph.remove()
                except Exception:
                    pass
            self._rows.clear()
            self._phases.clear()
            self._refresh_header()

        def activity_count(self) -> int:
            return len(self._rows)

else:
    LiveActivitiesBlock = None
    ActivityRow = None
    PhaseHeader = None
    QuestionActivityRow = None
