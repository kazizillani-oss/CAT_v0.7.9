"""
CCT UI — dashboard.py (spec v0.7 Welcome Dashboard section): shown
"When no workspace exists" — large logo, version/GPU/model line, quick
actions, and recent-items lists, all centered.

Mounted via ConversationView.show_dashboard() (see conversation.py) in
place of the plain WelcomeBanner, so everything WelcomeBanner already
did (removed the instant a real turn arrives) still happens; this
widget is a richer replacement, not a parallel system.

Honest scope: "Recent Simulations", "Recent Calculations", "Pinned
Notes", and "Recent Quantum Projects" from the spec's list would each
need their own dedicated history store, and none of those exist yet
(only calc_terminal/workspace.py's generated-file categories and
calc_terminal/projects.py's recent-folders list are real, queryable
data today). Rather than inventing numbers, this dashboard shows the
sections it can back with real data (Recent Projects, Recent Files via
workspace.py, Session Notebooks via the existing history list,
Workspace/API/Ollama status) and a plain "Documentation" quick action;
it does not fabricate placeholder content for the rest.

v0.7.2 roadmap addition: when a workspace is open (`workspace_root`
given), a third "Project & Workspace" column shows real, computed
stats — see calc_terminal/project_stats.py for exactly what's real vs.
honestly reported as unavailable (CPU%, "Indexed Status" — this
codebase has no separate file index). refresh_stats() updates that
column in place (no full recompose) so ui/app.py can call it from an
eventbus subscription without re-rendering the whole dashboard.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import os
import platform
import shutil

from .. import projects
from .. import workspace as cct_workspace
from .. import project_stats
from .. import timeline
from .. import todos
from .. import aicore
from .events import FolderOpened, FileOpenRequested, CommandExecuted, MessageSubmitted

TEXTUAL_AVAILABLE = True
try:
    from textual.containers import Vertical, Horizontal, Center
    from textual.widgets import Static, Button
    from . import theme_css
    from .design_system import (
        RESPONSIVE_LOGOS,
        select_logo,
        wordmark_markup,
        breakpoint_for,
        CATResponsiveBreakpoints,
        BP_LARGE,
        BP_NORMAL,
        BP_MEDIUM,
        BP_SMALL,
        BP_VERY_SMALL,
        CATBorders,
        CATSpacing,
    )
except Exception:
    TEXTUAL_AVAILABLE = False


# ─── 45 RESPONSIVE LAYOUT VARIANTS OF THE CAT WORDMARK LOGO ───────────────────
RESPONSIVE_LOGO_TIERS = [
    {"id": f"tier{i+1}", "name": meta["name"], "rows": meta["rows"], "art": meta["lines"], "key": key}
    for i, (key, meta) in enumerate(RESPONSIVE_LOGOS.items())
]


if TEXTUAL_AVAILABLE:

    class _QuickAction(Button):
        """Clean, sleek horizontal quick-action button matching the favorite terminal UI."""
        def __init__(self, label, action_id):
            super().__init__(label, id=action_id, classes="cct-dash-action")

    class WelcomeDashboard(Vertical):
        """spec v0.7 Welcome Dashboard — v0.7.9.0: THE PRIMARY STARTUP
        SCREEN. Every application launch lands here (right after the
        animated Welcome modal), as does /clear and New Chat Session:
        the composition opens with the large CAT block-art hero +
        identity/ready lines (the branded centerpiece), then quick
        actions, then the real-data columns.
        """

        def __init__(self, logo_lines, version, model_label, notebook_count,
                     workspace_root=None, mode_key=None):
            super().__init__(classes="cct-dashboard")
            self._logo_lines = logo_lines
            self._version = version
            self._model_label = model_label
            self._notebook_count = notebook_count
            self._workspace_root = workspace_root
            self._mode_key = mode_key
            self._ai_state = None   # live state text pushed by CCTApp
            self._last_resize_w = None  # (width, height) of last handled resize
            self._manual_override_tier = None

        def _get_viewport_size(self):
            p = getattr(self, "parent", None)
            w = 0
            h = 0
            if p is not None:
                p_reg = getattr(p, "region", None)
                p_sz = getattr(p, "size", None)
                h = (p_reg.height if p_reg and p_reg.height > 0 else 0) or (p_sz.height if p_sz and p_sz.height > 0 else 0)
                w = (p_reg.width if p_reg and p_reg.width > 0 else 0) or (p_sz.width if p_sz and p_sz.width > 0 else 0)
                try:
                    chat_col = p.parent
                    if chat_col is not None and getattr(chat_col, "region", None) and chat_col.region.height > 0:
                        comp = chat_col.query_one("#cct-composer")
                        comp_h = getattr(comp, "_explicit_height", None) or (comp.region.height if getattr(comp, "region", None) and comp.region.height > 0 else 5)
                        avail_h = max(10, chat_col.region.height - comp_h - 2)
                        h = min(h, avail_h) if h > 0 else avail_h
                        if getattr(chat_col, "region", None) and chat_col.region.width > 0:
                            w = min(w, chat_col.region.width) if w > 0 else chat_col.region.width
                except Exception:
                    pass

            if not w or not h:
                if hasattr(self, "app") and self.app and getattr(self.app, "size", None):
                    w = w or self.app.size.width
                    h = h or max(1, self.app.size.height - 8)

            return (max(20, int(w or 80)), max(10, int(h or 24)))

        # ----------------------------------------------------- artwork --
        def _art_lines(self):
            """Pick one of the 15 responsive layout variants of the CAT wordmark logo
            that perfectly matches the live viewport width and height. Never overflows."""
            if self._manual_override_tier is not None:
                idx = max(0, min(len(RESPONSIVE_LOGO_TIERS) - 1, self._manual_override_tier))
                return list(RESPONSIVE_LOGO_TIERS[idx]["art"])

            w, h = self._get_viewport_size()
            _key, lines = select_logo(w, h)
            return lines

        def _art_markup(self):
            """Large CAT word art with a restrained top-to-bottom mode-
            gradient tint (blended toward black in LIGHT mode so it stays
            readable on white). Rendered as plain styled text inside a
            Static — no input widget underneath, so it can never inherit
            a selection/highlight background."""
            w, h = self._get_viewport_size()
            override_key = None
            if self._manual_override_tier is not None:
                idx = max(0, min(len(RESPONSIVE_LOGO_TIERS) - 1, self._manual_override_tier))
                override_key = RESPONSIVE_LOGO_TIERS[idx].get("key")
            return wordmark_markup(w, h, variant_override=override_key)

        def set_logo_variant(self, idx):
            """Manually override responsive tier (0-4), or pass None to return to auto."""
            if idx is None:
                self._manual_override_tier = None
            else:
                self._manual_override_tier = max(0, min(len(RESPONSIVE_LOGO_TIERS) - 1, int(idx)))
            try:
                self.query_one("#cct-empty-art", Static).update(self._art_markup())
            except Exception:
                pass

        def cycle_logo_variant(self):
            """Cycle through responsive layout tiers."""
            curr = self._manual_override_tier if self._manual_override_tier is not None else 0
            next_idx = (curr + 1) % len(RESPONSIVE_LOGO_TIERS)
            self.set_logo_variant(next_idx)

        def on_click(self, event):
            """Click on ASCII art cycles manual override tiers."""
            target = getattr(event, "target", None)
            target_id = getattr(target, "id", None)
            if target_id == "cct-empty-art" or getattr(getattr(target, "parent", None), "id", None) == "cct-empty-art":
                self.cycle_logo_variant()

        def _ready_markup(self):
            faint = theme_css.current_hex("text-faint")
            muted = theme_css.current_hex("text-muted")
            success = theme_css.current_hex("success")
            try:
                from .cat_agent import mode_label_for
                from .. import ai_modes as _am
                label = mode_label_for(self._mode_key or _am.current_mode())
            except Exception:
                label = "CAT Agent"
            return (f"[{success}]\u25cf[/] [{muted} b]{label}[/] "
                    f"[{faint}]ready \u00b7 type to start, / for commands[/]")

        def _ai_status_markup(self):
            """The live AI runtime line INSIDE the dashboard (spec #5):
            model initialization/reload updates this line — the dashboard
            itself is never duplicated."""
            faint = theme_css.current_hex("text-faint")
            success = theme_css.current_hex("success")
            warning = theme_css.current_hex("warning")
            try:
                from .. import aicore as _aicore
                cfg = _aicore.load_config() or {}
            except Exception:
                cfg = {}
            provider = cfg.get("provider")
            model = cfg.get("model") or ""
            if not provider:
                return (f"[{warning}]\u25cb[/] [{faint}]AI STATUS "
                        f"\u2014 not configured \u00b7 run /model[/]")
            state = self._ai_state or "Ready"
            return (f"[{success}]\u25cf[/] [{faint}]AI STATUS \u2014 [/]"
                    f"[{theme_css.current_hex('text')}]{provider} "
                    f"{model}[/][{faint}] \u00b7 {state}[/]")

        def compose(self):
            faint = theme_css.current_hex("text-faint")
            muted = theme_css.current_hex("text-muted")

            # --- CAT hero: responsive wordmark logo + identity + ready (centered) ---
            yield Static(self._art_markup(), id="cct-empty-art")
            yield Static(f"[{muted} b]CAT v{self._version}[/]",
                         id="cct-empty-version", classes="cct-dash-line")
            yield Static(
                f"[{faint}]Chemistry \u2022 Coding \u2022 Intelligence[/]",
                id="cct-empty-tagline", classes="cct-dash-line")
            yield Static(self._ready_markup(), id="cct-empty-ready",
                         classes="cct-dash-line")
            yield Static(
                f"[{faint}]Create \u00b7 Analyze \u00b7 Build \u00b7 Debug "
                f"\u00b7 Research[/]",
                id="cct-empty-suggest", classes="cct-dash-line")

            # --- live AI runtime status --------------------------------
            yield Static(self._ai_status_markup(), id="cct-dash-ai-status",
                         classes="cct-dash-line")

            # --- Centered Quick Action Buttons -------------------------
            with Center():
                with Horizontal(id="cct-dash-actions"):
                    yield _QuickAction("\U0001f4c1 Open", "dash-open-folder")
                    yield _QuickAction("\U0001f4dd New Chat", "dash-new-chat")
                    yield _QuickAction("\u2699  Settings", "dash-settings")
                    yield _QuickAction("\U0001f4d6 Docs", "dash-docs")

            # --- Centered 3-Column Responsive Dashboard Cards ----------
            with Center():
                with Horizontal(id="cct-dash-columns"):
                    with Vertical(classes="cct-dash-col cct-dash-card-3d"):
                        yield Static("[b]Recent Projects[/b]", classes="cct-dash-col-title")
                        try:
                            recent = projects.recent()[:5]
                        except Exception:
                            recent = []
                        if recent:
                            for p in recent:
                                yield Static(f"  \U0001f4c1 {os.path.basename(p.rstrip(os.sep)) or p}",
                                             classes="cct-dash-row")
                        else:
                            yield Static(f"[{faint}]No projects opened yet.[/]", classes="cct-dash-row")

                    with Vertical(classes="cct-dash-col cct-dash-card-3d", id="cct-dash-col-notebooks"):
                        yield Static("[b]Session Notebooks[/b]", classes="cct-dash-col-title")
                        solved_count = self._notebook_count or 0
                        if hasattr(self, "app") and hasattr(self.app, "_history"):
                            solved_count = max(solved_count, len(self.app._history))
                        try:
                            summary = cct_workspace.summary()
                        except Exception:
                            summary = []
                        if summary:
                            first_cat, first_count, _newest, _when = summary[0]
                            yield Static(f"  \u26a1 [b]{solved_count}[/b] solved  \u00b7  \U0001f4c4 {first_cat}: {first_count}", classes="cct-dash-row")
                        else:
                            yield Static(f"  \u26a1 [b]{solved_count}[/b] solved  \u00b7  [{faint}]No exports yet[/]", classes="cct-dash-row")

                        # Working Quick-Solve Notebook Launchers (compact 2-row chips)
                        yield Static("  [b]Quick Solve & Derive:[/b]", classes="cct-dash-nb-subtitle")
                        with Horizontal(classes="cct-dash-nb-chips"):
                            yield Button("\u26a1 Kinetics", id="dash-solve-kinetics", classes="cct-nb-chip")
                            yield Button("\u26a1 Arrhenius", id="dash-solve-arrhenius", classes="cct-nb-chip")
                        with Horizontal(classes="cct-dash-nb-chips"):
                            yield Button("\u26a1 Nernst", id="dash-solve-nernst", classes="cct-nb-chip")
                            yield Button("\u26a1 Gibbs", id="dash-solve-gibbs", classes="cct-nb-chip")

                    if self._workspace_root:
                        with Vertical(classes="cct-dash-col cct-dash-card-3d"):
                            yield Static("[b]Project & Workspace[/b]", classes="cct-dash-col-title")
                            try:
                                stats_markup = self._stats_markup()
                            except Exception as e:
                                stats_markup = (
                                    f"  [{theme_css.current_hex('text-faint')}]"
                                    f"Workspace stats unavailable: "
                                    f"{type(e).__name__}[/]")
                            yield Static(stats_markup, id="cct-dash-stats-body")

        def _stats_markup(self):
            """The whole Project & Workspace column body as one concise markup
            string, formatted cleanly with responsive path shortening and
            compact line budgeting so content is never cut off or overflows."""
            from . import theme_css
            faint = theme_css.current_hex("text-faint")
            root = self._workspace_root
            stats = project_stats.scan_workspace(root)
            branch = project_stats.git_branch(root)
            mem = project_stats.memory_usage_mb()
            cpu = project_stats.cpu_percent()
            config = aicore.load_config()

            def _truncate_path(p: str, max_chars: int = 24) -> str:
                if not p or len(p) <= max_chars:
                    return p
                norm = p.replace("\\", "/")
                parts = [part for part in norm.split("/") if part]
                if len(parts) >= 2:
                    cand = f"{parts[0]}/.../{parts[-1]}"
                    if len(cand) <= max_chars:
                        return cand
                return "..." + p[-(max_chars - 3):]

            folder_name = os.path.basename(root.rstrip(os.sep)) or root
            short_root = _truncate_path(root, 22)
            lines = [
                f"  \U0001f4c1 [b]{folder_name}[/]  [{faint}]({short_root})[/]",
                f"  {project_stats.human_size(stats['total_size'])}{'+' if stats['truncated'] else ''}  \u00b7  {stats['total_files'] if stats['total_files'] is not None else '\u2014'} files",
            ]
            if stats.get("languages"):
                top_langs = list(stats["languages"].items())[:2]
                langs = ", ".join(f"{lang} ({n})" for lang, n in top_langs)
                if len(stats["languages"]) > 2:
                    langs += f" +{len(stats['languages']) - 2}"
                lines.append(f"  [{faint}]Lang:[/] {langs}")
            lines.append(f"  [{faint}]Git:[/] {branch or '\u2014'}  \u00b7  [{faint}]Mod:[/] {project_stats.human_age(stats['last_modified'])}")
            provider = config.get('provider', '\u2014')
            model = config.get('model', '\u2014')
            lines.append(f"  [{faint}]AI:[/] {provider} ({model})")
            mem_str = f"{mem:.0f}MB" if mem is not None else "\u2014"
            cpu_str = f"{cpu:.0f}%" if cpu is not None else "\u2014"
            lines.append(f"  [{faint}]Sys:[/] Mem: {mem_str}  \u00b7  CPU: {cpu_str}")
            return "\n".join(lines)

        def refresh_stats(self):
            """Called from ui/app.py after an eventbus publish (file
            saved, AI reply finished, workspace opened/closed, todo
            changed) — recomputes and repaints just the stats column,
            not the whole dashboard."""
            if not self._workspace_root:
                return
            try:
                self.query_one("#cct-dash-stats-body", Static).update(self._stats_markup())
            except Exception:
                pass

        # ------------------------------------- v0.7.9.0 live state APIs --
        def set_mode(self, mode_key):
            """The ACTUAL active AI mode changed: repaint the ready line
            and the hero art tint (mode gradient) in place."""
            self._mode_key = mode_key
            try:
                self.query_one("#cct-empty-art", Static).update(
                    self._art_markup())
                self.query_one("#cct-empty-ready", Static).update(
                    self._ready_markup())
            except Exception:
                pass

        def repaint_theme(self):
            """Theme switched: re-read every color in place (light/dark
            safe — markup is rebuilt from the current palette)."""
            try:
                self.query_one("#cct-empty-art", Static).update(
                    self._art_markup())
                self.query_one("#cct-empty-version", Static).update(
                    f"[{theme_css.current_hex('text-muted')} b]CAT v"
                    f"{self._version}[/]")
                self.query_one("#cct-empty-tagline", Static).update(
                    f"[{theme_css.current_hex('text-faint')}]Chemistry "
                    f"\u2022 Coding \u2022 Intelligence[/]")
                self.query_one("#cct-empty-ready", Static).update(
                    self._ready_markup())
                self.query_one("#cct-dash-ai-status", Static).update(
                    self._ai_status_markup())
            except Exception:
                pass

        def update_ai_status(self, state=None, model_label=None):
            """Live model-state line inside THIS dashboard."""
            if state is not None:
                self._ai_state = state
            if model_label is not None:
                self._model_label = model_label
            try:
                self.query_one("#cct-dash-ai-status", Static).update(
                    self._ai_status_markup())
            except Exception:
                pass

        def on_button_pressed(self, event: Button.Pressed):
            bid = event.button.id
            if not bid:
                return
            if bid == "dash-open-folder":
                self.post_message(FileOpenRequested("__open_folder_prompt__"))
            elif bid == "dash-new-chat":
                self.post_message(CommandExecuted("/clear"))
            elif bid == "dash-settings":
                self.post_message(CommandExecuted("/settings"))
            elif bid == "dash-docs":
                self.post_message(CommandExecuted("/help"))
            elif bid == "dash-solve-kinetics":
                self.post_message(MessageSubmitted("derive the first order rate law step by step"))
            elif bid == "dash-solve-arrhenius":
                self.post_message(MessageSubmitted("derive arrhenius equation step by step"))
            elif bid == "dash-solve-nernst":
                self.post_message(MessageSubmitted("derive nernst equation step by step"))
            elif bid == "dash-solve-gibbs":
                self.post_message(MessageSubmitted("derive gibbs free energy equation step by step"))

        def fit_to_viewport(self):
            """Immediately re-evaluates live viewport height/width and adapts layout,
            ensuring zero overflow, zero card clipping, and smooth logo scaling."""
            self._last_resize_w = None  # Clear cache to force fresh re-evaluation
            self.on_resize(event=None)

        def on_resize(self, event=None):
            """Terminal / pane resized: re-pick art + make actions and cards responsive
            (Horizontal → Vertical stack when chat gets narrow or short).
            """
            if not self.is_attached:
                return

            w, h = self._get_viewport_size()
            key = (w, h)
            if key == getattr(self, "_last_resize_w", None) and event is not None:
                return
            self._last_resize_w = key

            bp = breakpoint_for(w, h)

            # 1. Update logo dynamically & deterministically across all 45 variants
            try:
                self.query_one("#cct-empty-art", Static).update(self._art_markup())
            except Exception:
                pass

            # 2. Adjust vertical breathing room based on available height
            try:
                # Progressive height compression ensures cards never get cut off
                self.query_one("#cct-empty-suggest", Static).display = (h >= 32)
                self.query_one("#cct-empty-tagline", Static).display = (h >= 26)
                self.query_one("#cct-dash-ai-status", Static).display = (h >= 22)
                self.query_one("#cct-empty-version", Static).display = (h >= 18)
            except Exception:
                pass

            # 3. Responsive Button System
            try:
                actions = self.query_one("#cct-dash-actions")
                btn_open = self.query_one("#dash-open-folder", Button)
                btn_chat = self.query_one("#dash-new-chat", Button)
                btn_settings = self.query_one("#dash-settings", Button)
                btn_docs = self.query_one("#dash-docs", Button)

                if bp in (BP_LARGE, BP_NORMAL):
                    btn_open.label = "\U0001f4c1 Open"
                    btn_chat.label = "\U0001f4dd New Chat"
                    btn_settings.label = "\u2699 Settings"
                    btn_docs.label = "\U0001f4d6 Docs"
                    if actions.has_class("stacked"):
                        actions.remove_class("stacked")
                elif bp == BP_MEDIUM:
                    btn_open.label = "Open"
                    btn_chat.label = "Chat"
                    btn_settings.label = "Settings"
                    btn_docs.label = "Docs"
                    if actions.has_class("stacked"):
                        actions.remove_class("stacked")
                else:  # BP_SMALL or BP_VERY_SMALL
                    btn_open.label = "Open"
                    btn_chat.label = "Chat"
                    btn_settings.label = "Settings"
                    btn_docs.label = "Docs"
                    if not actions.has_class("stacked"):
                        actions.add_class("stacked")
            except Exception:
                pass

            # 4. Responsive Card System: 3 columns -> 2+1 columns -> 1 column stack
            try:
                columns = self.query_one("#cct-dash-columns")
                if bp in (BP_LARGE, BP_NORMAL):
                    if columns.has_class("stacked"):
                        columns.remove_class("stacked")
                else:  # BP_MEDIUM, BP_SMALL, BP_VERY_SMALL
                    if not columns.has_class("stacked"):
                        columns.add_class("stacked")
            except Exception:
                pass

else:
    WelcomeDashboard = None
