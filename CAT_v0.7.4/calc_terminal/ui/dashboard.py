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
from .events import FolderOpened, FileOpenRequested, CommandExecuted

TEXTUAL_AVAILABLE = True
try:
    from textual.containers import Vertical, Horizontal, Center
    from textual.widgets import Static, Button
    from . import theme_css
except Exception:
    TEXTUAL_AVAILABLE = False


if TEXTUAL_AVAILABLE:

    class _QuickAction(Button):
        """v0.7.9.6: Quick-action button on the dashboard — picks up the
        full 3D-skeuomorphic system (tall bevel borders, real lift on
        hover, real press on activation) so it reads as a hardware key
        rather than a flat label."""
        def __init__(self, label, action_id):
            super().__init__(label, id=action_id,
                             classes="cct-dash-action cct-btn-3d-skeu")

    class WelcomeDashboard(Vertical):
        """spec v0.7 Welcome Dashboard — v0.7.9.0: THE PRIMARY STARTUP
        SCREEN. Every application launch lands here (right after the
        animated Welcome modal), as does /clear and New Chat Session:
        the composition opens with the large CAT block-art hero +
        identity/ready lines (the branded centerpiece), then quick
        actions, then the real-data columns.

        State inputs handed in by CCTApp (this widget never reads
        app/session state directly, same convention as BrandHeader/
        StatusLine): logo_lines / version / model_label / notebook_count.
        `workspace_root`, added for the v0.7.2 roadmap's Project &
        Workspace Dashboard, is the one exception — real filesystem/git
        stats need a real path.

        v0.7.9.0 additions (spec: 'Dashboard and Welcome Screen always
        available'):
          * CAT ASCII hero replaces the old one-line text hero.
          * Mode-aware ready line (set_mode) — always names the ACTUAL
            persona.
          * Live AI STATUS block (update_ai_status): Initializing /
            Working… / Ready / Not configured. Model starts/reloads
            NEVER open another dashboard — the existing one is updated
            in place (requirement: prevent duplicate windows).
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

        # ----------------------------------------------------- artwork --
        def _art_lines(self):
            """Pick the largest CAT word-art variant that fits the LIVE
            dashboard width — full block letters, semi, compact half-block,
            or one of the mini cat faces on a narrow pane. Never overflows.

            v0.7.9.6: this used to be a private 3-rung ladder (text < 22,
            compact < 34, else full) that bypassed the empty-state's own
            ladder — so the two screens disagreed about what "narrow"
            means and every face variant added over there had to be
            hand-copied here. It now delegates to the shared, pure
            `empty_state._pick_art_variant()`, which means the whole
            face family (mini/tiny/micro/nano) lights up on the dashboard
            too, and the height-aware short-pane downgrade comes along
            for free.

            Returns None when the pane is too narrow for any art (caller
            renders a text wordmark instead)."""
            try:
                from .empty_state import (
                    _COMPACT_ART, _MINI_CAT_ART, _MINI_CAT_ART_2ROW,
                    _MICRO_CAT_ART, _NANO_CAT_ART, _SEMI_ART,
                    _TINY_CAT_ART, _full_art, _pick_art_variant)
                try:
                    size = self.size
                    w = size.width or 0
                    h = size.height or 0
                except Exception:
                    w = h = 0
                variant = _pick_art_variant(w, h)
                if variant == "text":
                    return None                      # text-only wordmark
                face = {
                    "nanoface": _NANO_CAT_ART,
                    "microface": _MICRO_CAT_ART,
                    "tinyface": _TINY_CAT_ART,
                    "miniface": _MINI_CAT_ART,
                    "miniface2": _MINI_CAT_ART_2ROW,
                    "compact": _COMPACT_ART,
                    "semi": _SEMI_ART,
                }.get(variant)
                if face is not None:
                    return list(face)
                return [line.rstrip() for line in
                        (self._logo_lines or _full_art())]
            except Exception:
                return ["CAT"]

        def _art_markup(self):
            """Large CAT word art with a restrained top-to-bottom mode-
            gradient tint (blended toward black in LIGHT mode so it stays
            readable on white). Rendered as plain styled text inside a
            Static — no input widget underneath, so it can never inherit
            a selection/highlight background."""
            try:
                from .empty_state import _lerp_hex, _darken
                from .. import theme as _theme
                g_start, g_end = theme_css.gradient_hex()
                if _theme.is_light():
                    g_start = _darken(g_start, 0.25)
                    g_end = _darken(g_end, 0.25)
                art = self._art_lines()
                if not art:
                    return f"[b]{g_start}CAT[/]"
                n = max(1, len(art) - 1)
                lines = []
                for i, line in enumerate(art):
                    color = _lerp_hex(g_start, g_end, i / n)
                    lines.append(f"[{color} b]{line}[/]")
                return "\n".join(lines)
            except Exception:
                return "[b]CAT[/]"

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

            # --- CAT hero: block art + identity + ready (branded) ------
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

            with Horizontal(id="cct-dash-actions"):
                yield _QuickAction("\U0001f4c1 Open Folder", "dash-open-folder")
                yield _QuickAction("\U0001f4dd New Chat", "dash-new-chat")
                yield _QuickAction("\u2699 Settings", "dash-settings")
                yield _QuickAction("\U0001f4d6 Documentation", "dash-docs")

            with Horizontal(id="cct-dash-columns"):
                with Vertical(classes="cct-dash-col cct-dash-card-3d"):
                    yield Static("[b]Recent Projects[/b]", classes="cct-dash-col-title")
                    try:
                        recent = projects.recent()[:6]
                    except Exception:
                        recent = []
                    if recent:
                        for p in recent:
                            yield Static(f"  \U0001f4c1 {os.path.basename(p.rstrip(os.sep)) or p}",
                                         classes="cct-dash-row")
                    else:
                        yield Static(f"[{faint}]No projects opened yet.[/]", classes="cct-dash-row")

                with Vertical(classes="cct-dash-col cct-dash-card-3d"):
                    yield Static("[b]Session Notebooks[/b]", classes="cct-dash-col-title")
                    yield Static(f"  {self._notebook_count} solved this session", classes="cct-dash-row")
                    # v0.7.9.0 fix: workspace data collection is guarded —
                    # a read-only/protected root (e.g. launching `cat`
                    # from C:\WINDOWS\System32) must degrade to an honest
                    # 'unavailable' line, never PermissionError the whole
                    # startup compose.
                    try:
                        summary = cct_workspace.summary()
                    except Exception:
                        summary = []
                    if summary:
                        for cat, count, newest, when in summary[:5]:
                            yield Static(f"  \U0001f4c4 {cat}: {count} ({newest}, {when})",
                                         classes="cct-dash-row")
                    else:
                        yield Static(f"[{faint}]No generated files yet.[/]", classes="cct-dash-row")

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
            """The whole Project & Workspace column body as one markup
            string, shared by compose() and refresh_stats() so the two
            can never drift into showing different formatting for the
            same numbers. (compose() wraps this in its own guard — a
            failing scan degrades to an 'unavailable' line.)"""
            from . import theme_css
            faint = theme_css.current_hex("text-faint")
            root = self._workspace_root
            stats = project_stats.scan_workspace(root)
            branch = project_stats.git_branch(root)
            deps = project_stats.dependencies(root)
            mem = project_stats.memory_usage_mb()
            cpu = project_stats.cpu_percent()
            config = aicore.load_config()
            frac, done, total = todos.progress(root)
            recent_events = timeline.events()[:5]

            lines = [
                f"  {os.path.basename(root.rstrip(os.sep)) or root}",
                f"  [{faint}]{root}[/]",
                f"  {project_stats.human_size(stats['total_size'])}"
                f"{'+' if stats['truncated'] else ''}  \u00b7  "
                f"{stats['total_files'] if stats['total_files'] is not None else '\u2014'} files",
            ]
            if stats["languages"]:
                langs = ", ".join(f"{lang} ({n})" for lang, n in stats["languages"].items())
                lines.append(f"  [{faint}]Languages:[/] {langs}")
            lines.append(f"  [{faint}]Git branch:[/] {branch or '\u2014 (not a git repo)'}")
            if deps:
                lines.append(f"  [{faint}]Dependencies:[/] {', '.join(deps[:6])}"
                              + (f" +{len(deps) - 6} more" if len(deps) > 6 else ""))
            lines.append(f"  [{faint}]Last modified:[/] {project_stats.human_age(stats['last_modified'])}")
            lines.append(f"  [{faint}]AI:[/] {config.get('provider', '\u2014')} "
                          f"({config.get('model', '\u2014')})")
            lines.append(f"  [{faint}]Memory:[/] "
                          f"{f'{mem:.0f} MB' if mem is not None else 'unavailable on this platform'}"
                          f"   [{faint}]CPU:[/] {f'{cpu:.0f}%' if cpu is not None else 'unavailable'}")
            if total:
                lines.append(f"  [{faint}]Todos:[/] {done}/{total} complete")
            if recent_events:
                lines.append(f"  [b]Recent Activity[/b]")
                for ev in recent_events:
                    lines.append(f"    {ev.line()}")
            return "\n".join(lines)

        def refresh_stats(self):
            """Called from ui/app.py after an eventbus publish (file
            saved, AI reply finished, workspace opened/closed, todo
            changed) — recomputes and repaints just the stats column,
            not the whole dashboard. No-op if this dashboard has no
            workspace column (nothing to refresh) or isn't mounted
            (e.g. a chat has since started and the dashboard was
            already torn down — see conversation.py's hide_welcome)."""
            if not self._workspace_root:
                return
            try:
                self.query_one("#cct-dash-stats-body", Static).update(self._stats_markup())
            except Exception:
                pass

        # ------------------------------------- v0.7.9.0 live state APIs --
        # Duck-typed by ConversationView.update_empty_state_mode /
        # repaint_empty_state_theme / update_ai_status, so whichever
        # welcome-slot widget is visible (this dashboard or the bare
        # empty-state centerpiece) reacts to the same calls.

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
            """Live model-state line inside THIS dashboard (spec: model
            starts/reloads must never open another dashboard). `state`
            is e.g. 'Initializing', 'Loading model', 'Working\u2026',
            'Ready'; pass None to recompute from config."""
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
            if bid == "dash-open-folder":
                self.post_message(FileOpenRequested("__open_folder_prompt__"))
            elif bid == "dash-new-chat":
                self.post_message(CommandExecuted("/clear"))
            elif bid == "dash-settings":
                self.post_message(CommandExecuted("/settings"))
            elif bid == "dash-docs":
                self.post_message(CommandExecuted("/help"))

        def on_resize(self, event):
            """Terminal / pane resized: re-pick art + make actions responsive
            (Horizontal → Vertical stack when chat gets narrow from editor stretch).

            v0.7.9.6 stability pass:
            * Guards on `is_attached` so a resize event arriving during
              teardown or screen swap is a cheap no-op.
            * Width-change guard: when the width is unchanged (the common
              case — a height-only resize, or the app's own debounced
              cascade firing after the event already landed) this returns
              immediately instead of rebuilding the art markup and running
              two widget queries for nothing.
            * Coalesces stacked-class add/remove into one decision per
              pass — the previous code could add and remove the same
              class back-to-back if width hovered at the 72-col boundary.
            * The `#cct-empty-art` lookup is captured from the SIZE rather
              than re-derived, so a mid-drag resize can't observe a stale
              width."""
            if not self.is_attached:
                return
            size = getattr(event, "size", None)
            if size is not None:
                w = size.width
                h = size.height
            else:
                w = h = None
            if not w:
                try:
                    w = self.size.width or 0
                    h = self.size.height or 0
                except Exception:
                    w = h = 0
            if not w:
                return
            # Cheap early-out: re-fit only on a REAL layout change. The
            # v0.7.9.6 art ladder is height-aware (short panes drop to the
            # 2-row cat), so the key is the (width, height) pair — keying on
            # width alone would miss a height-only drag and leave a 3-row
            # face clipped in a short pane.
            key = (w, h)
            if key == getattr(self, "_last_resize_w", None):
                return
            self._last_resize_w = key
            try:
                self.query_one("#cct-empty-art", Static).update(
                    self._art_markup())
            except Exception:
                pass
            try:
                # Stack quick actions & columns when dashboard narrows
                # below ~72 cols (editor stretched or sidebar open).
                # Both containers move together, so decide once.
                stack_now = w < 72
                actions = self.query_one("#cct-dash-actions")
                columns = self.query_one("#cct-dash-columns")
                if stack_now:
                    if not actions.has_class("stacked"):
                        actions.add_class("stacked")
                    if not columns.has_class("stacked"):
                        columns.add_class("stacked")
                else:
                    if actions.has_class("stacked"):
                        actions.remove_class("stacked")
                    if columns.has_class("stacked"):
                        columns.remove_class("stacked")
            except Exception:
                pass

else:
    WelcomeDashboard = None
