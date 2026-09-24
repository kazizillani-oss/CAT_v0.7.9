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
except Exception:
    TEXTUAL_AVAILABLE = False


# ─── 5 RESPONSIVE ASCII WORDMARK LOGO VARIANTS ───────────────────────────────
_ACTIVE_LOGO_VARIANT = 0

LOGO_VARIANTS = [
    {
        "id": "cyber3d",
        "name": "3D ANSI Block",
        "art": [
            " ██████╗  █████╗ ████████╗",
            "██╔════╝ ██╔══██╗╚══██╔══╝",
            "██║      ███████║   ██║   ",
            "██║      ██╔══██║   ██║   ",
            "╚██████╗ ██║  ██║   ██║   ",
            " ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ",
        ],
        "compact": [
            "█▀▀▀ █▀▀█ ▀█▀",
            "█    █▄▄█  █ ",
            "▀▀▀▀ ▀  ▀  ▀ ",
        ],
    },
    {
        "id": "retro",
        "name": "Classic Retro BBS",
        "art": [
            "   ____    ___   ______",
            "  / __/   / _ | /_  __/",
            " / /__   / __ |  / /   ",
            " \\___/  /_/ |_| /_/    ",
        ],
        "compact": [
            " / _/ / _ | /_  _/",
            "/ /_ / __ |  / /  ",
            "\\__/ /_/ |_| /_/  ",
        ],
    },
    {
        "id": "matrix",
        "name": "Matrix Glitch",
        "art": [
            " ▄████▄   ▄▄▄     ▄▄▄█████▓",
            "▒██▀ ▀█  ▒████▄   ▓  ██▒ ▓▒",
            "▒▓█    ▄ ▒██  ▀█▄ ▒ ▓██░ ▒░",
            "▒▓▓▄ ▄██▒░██▄▄▄▄██░ ▓██▓ ░ ",
            "▒ ▓███▀ ░ ▓█   ▓██▒ ▒██▒ ░ ",
        ],
        "compact": [
            "▄██▄ ▄▄▄  ███",
            "█    █  █  █ ",
            "▀██▀ ▀  ▀  ▀ ",
        ],
    },
    {
        "id": "synthwave",
        "name": "Isometric Synthwave",
        "art": [
            "  ______   ___   ______ ",
            " / ____/  /   | /_  __/ ",
            "/ /      / /| |  / /    ",
            "/ /___  / ___ | / /     ",
            "\\____/ /_/  |_|/_/      ",
        ],
        "compact": [
            "/ ___/ /   | /_  _/",
            "/ /__ / /| |  / /  ",
            "\\___/ /_/ |_| /_/  ",
        ],
    },
    {
        "id": "pixel",
        "name": "Compact Pixel Mini",
        "art": [
            "┌─┐┌─┐┌┬┐",
            "│  ├─┤ │ ",
            "└─┘┴ ┴ ┴ ",
        ],
        "compact": [
            "┌─┐┌─┐┌┬┐",
            "│  ├─┤ │ ",
            "└─┘┴ ┴ ┴ ",
        ],
    },
]


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
            self._logo_variant_idx = _ACTIVE_LOGO_VARIANT

        # ----------------------------------------------------- artwork --
        def _art_lines(self):
            """Pick the largest CAT word-art variant that fits the LIVE
            dashboard width — respecting the selected LOGO_VARIANT, or
            falling back through compact / cat faces when narrow. Never overflows."""
            try:
                from .empty_state import (
                    _COMPACT_ART, _MINI_CAT_ART, _MINI_CAT_ART_2ROW,
                    _MICRO_CAT_ART, _NANO_CAT_ART, _SEMI_ART,
                    _TINY_CAT_ART, _COMBO_CAT_ART, _full_art, _pick_art_variant)
                try:
                    w = None
                    h = None
                    last_rw = getattr(self, "_last_resize_w", None)
                    if last_rw and last_rw[0] and last_rw[1]:
                        w, h = last_rw
                    if not w or not h:
                        size = self.size
                        w = w or size.width or 0
                        p = getattr(self, "parent", None)
                        p_h = getattr(getattr(p, "size", None), "height", 0) or getattr(getattr(p, "region", None), "height", 0) or 0
                        if p_h > 0:
                            h = p_h
                        else:
                            h = h or size.height or 0
                    if not w or not h:
                        if hasattr(self, "app") and self.app and self.app.size:
                            w = w or self.app.size.width
                            h = h or max(1, self.app.size.height - 7)
                except Exception:
                    w = h = 0
                is_split = False
                if hasattr(self, "app") and self.app and self.app.size:
                    app_w = self.app.size.width
                    if app_w and w and w < (app_w - 5):
                        is_split = True
                if h is not None and h < 24:
                    is_split = True

                variant = _pick_art_variant(w, h, prefer_combo=is_split)
                if h is not None and h < 8 and variant in ("full", "combo", "semi", "compact", "miniface", "tinyface"):
                    variant = "miniface2"
                if variant == "text":
                    return None

                active_var = LOGO_VARIANTS[self._logo_variant_idx]
                if variant == "full":
                    return list(active_var["art"])
                if variant in ("semi", "compact"):
                    return list(active_var.get("compact") or _SEMI_ART)
                if variant == "combo":
                    if w and w >= 36:
                        return list(_COMBO_CAT_ART)
                    return list(active_var.get("compact") or _COMPACT_ART)

                face = {
                    "nanoface": _NANO_CAT_ART,
                    "microface": _MICRO_CAT_ART,
                    "tinyface": _TINY_CAT_ART,
                    "miniface": _MINI_CAT_ART,
                    "miniface2": _MINI_CAT_ART_2ROW,
                }.get(variant)
                if face is not None:
                    return list(face)
                return list(active_var["art"])
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

        def set_logo_variant(self, idx: int):
            """Switch to one of the 5 responsive ASCII logo variants."""
            global _ACTIVE_LOGO_VARIANT
            self._logo_variant_idx = max(0, min(len(LOGO_VARIANTS) - 1, int(idx)))
            _ACTIVE_LOGO_VARIANT = self._logo_variant_idx
            try:
                self.query_one("#cct-empty-art", Static).update(self._art_markup())
                for i in range(len(LOGO_VARIANTS)):
                    try:
                        btn = self.query_one(f"#dash-logo-{i}", Button)
                        if i == self._logo_variant_idx:
                            btn.add_class("active")
                        else:
                            btn.remove_class("active")
                    except Exception:
                        pass
            except Exception:
                pass

        def cycle_logo_variant(self):
            """Cycle to next ASCII logo variant."""
            next_idx = (self._logo_variant_idx + 1) % len(LOGO_VARIANTS)
            self.set_logo_variant(next_idx)

        def on_click(self, event):
            """Click on ASCII art cycles through the 5 logo styles."""
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

            # --- CAT hero: block art + selector pills + identity + ready (centered) ---
            yield Static(self._art_markup(), id="cct-empty-art")
            with Horizontal(id="cct-dash-logo-bar"):
                for idx, v in enumerate(LOGO_VARIANTS):
                    cls = "cct-logo-pill active" if idx == self._logo_variant_idx else "cct-logo-pill"
                    yield Button(f"{idx+1}:{v['name'].split()[0]}", id=f"dash-logo-{idx}", classes=cls)
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
            with Horizontal(id="cct-dash-actions"):
                yield _QuickAction("\U0001f4c1 Open", "dash-open-folder")
                yield _QuickAction("\U0001f4dd New Chat", "dash-new-chat")
                yield _QuickAction("\u2699 Settings", "dash-settings")
                yield _QuickAction("\U0001f4d6 Docs", "dash-docs")

            # --- 3-Column Responsive Dashboard Cards -------------------
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

                with Vertical(classes="cct-dash-col cct-dash-card-3d", id="cct-dash-col-notebooks"):
                    yield Static("[b]Session Notebooks[/b]", classes="cct-dash-col-title")
                    solved_count = self._notebook_count or 0
                    if hasattr(self, "app") and hasattr(self.app, "_history"):
                        solved_count = max(solved_count, len(self.app._history))
                    yield Static(f"  \u26a1 [b]{solved_count}[/b] solved this session", classes="cct-dash-row")
                    try:
                        summary = cct_workspace.summary()
                    except Exception:
                        summary = []
                    if summary:
                        for cat, count, newest, when in summary[:3]:
                            yield Static(f"  \U0001f4c4 {cat}: {count} ({newest})",
                                         classes="cct-dash-row")
                    else:
                        yield Static(f"  [{faint}]No generated exports yet.[/]", classes="cct-dash-row")

                    # Working Quick-Solve Notebook Launchers
                    yield Static("  [b]Quick Solve & Derive:[/b]", classes="cct-dash-nb-subtitle")
                    with Horizontal(classes="cct-dash-nb-actions"):
                        yield Button("\u26a1 Kinetics", id="dash-solve-kinetics", classes="cct-nb-chip-btn")
                        yield Button("\u26a1 Arrhenius", id="dash-solve-arrhenius", classes="cct-nb-chip-btn")
                    with Horizontal(classes="cct-dash-nb-actions"):
                        yield Button("\u26a1 Nernst", id="dash-solve-nernst", classes="cct-nb-chip-btn")
                        yield Button("\u26a1 Gibbs", id="dash-solve-gibbs", classes="cct-nb-chip-btn")

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
            string, formatted cleanly with responsive path shortening and
            separate lines for Memory and CPU so content is never cut off."""
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
            recent_events = timeline.events()[:3]

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
                f"  [b]{folder_name}[/]  [{faint}]({short_root})[/]",
                f"  {project_stats.human_size(stats['total_size'])}{'+' if stats['truncated'] else ''}  \u00b7  {stats['total_files'] if stats['total_files'] is not None else '\u2014'} files",
            ]
            if stats["languages"]:
                top_langs = list(stats["languages"].items())[:2]
                langs = ", ".join(f"{lang} ({n})" for lang, n in top_langs)
                if len(stats["languages"]) > 2:
                    langs += f" +{len(stats['languages']) - 2}"
                lines.append(f"  [{faint}]Languages:[/] {langs}")
            lines.append(f"  [{faint}]Git branch:[/] {branch or '\u2014 (not a repo)'}")
            if deps:
                dep_str = ", ".join(deps[:3])
                if len(deps) > 3:
                    dep_str += f" +{len(deps) - 3}"
                lines.append(f"  [{faint}]Dependencies:[/] {dep_str}")
            lines.append(f"  [{faint}]Last modified:[/] {project_stats.human_age(stats['last_modified'])}")
            provider = config.get('provider', '\u2014')
            model = config.get('model', '\u2014')
            lines.append(f"  [{faint}]AI:[/] {provider} ({model})")
            mem_str = f"{mem:.0f} MB" if mem is not None else "unavailable"
            cpu_str = f"{cpu:.0f}%" if cpu is not None else "unavailable"
            lines.append(f"  [{faint}]Memory:[/] {mem_str}")
            lines.append(f"  [{faint}]CPU:[/]    {cpu_str}")
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
            if bid.startswith("dash-logo-"):
                try:
                    idx = int(bid.replace("dash-logo-", ""))
                    self.set_logo_variant(idx)
                except Exception:
                    pass
            elif bid == "dash-open-folder":
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

        def on_resize(self, event):
            """Terminal / pane resized: re-pick art + make actions and cards responsive
            (Horizontal → Vertical stack when chat gets narrow or short).
            """
            if not self.is_attached:
                return
            size = getattr(event, "size", None)
            if size is not None:
                w = size.width
                h = size.height
            else:
                w = h = None
            p = getattr(self, "parent", None)
            if p is not None:
                p_h = getattr(getattr(p, "size", None), "height", 0) or getattr(getattr(p, "region", None), "height", 0) or 0
                p_w = getattr(getattr(p, "size", None), "width", 0) or getattr(getattr(p, "region", None), "width", 0) or 0
                if p_h > 0:
                    h = p_h
                if p_w > 0:
                    w = w or p_w
            if not w:
                try:
                    w = self.size.width or 0
                except Exception:
                    w = 0
            if not h:
                try:
                    h = self.size.height or 0
                except Exception:
                    h = 0
            if (not w or not h) and hasattr(self, "app") and self.app and self.app.size:
                w = w or self.app.size.width
                h = h or max(1, self.app.size.height - 7)
            if not w:
                return

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
                # On compact vertical layouts, hide tagline & suggestion lines
                # so quick actions and cards never get pushed off screen or cut off
                compact_vert = (h is not None and h < 24)
                for line_id in ("#cct-empty-tagline", "#cct-empty-suggest", "#cct-dash-logo-bar"):
                    try:
                        self.query_one(line_id).display = not compact_vert
                    except Exception:
                        pass
            except Exception:
                pass

            try:
                # Responsive stacking: stack cards and buttons whenever width < 96
                # or height is short (< 26 rows). At 80-92 cols, stacking guarantees
                # all cards have full width and content is never cut off.
                stack_now = (w < 96) or (h is not None and h < 26)
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
