"""
CAT UI — AgentModeMenu: Fast 1-click AI Agent & Mode Switcher Popup.

Anchors above the composer's `#badge-notebook` mode button. Displays all
standard and custom AI agent personas (Qala, Sage, Mira, Aria, Dex, Nova,
Automator, plus any user-created Kitties) with their live icons, names, and specialties.
Clicking any agent or pressing Enter instantly switches persona, theme accent,
and system prompt with zero latency.
"""

from textual.screen import Screen
from textual.containers import Vertical, Horizontal, VerticalScroll
from textual.widgets import Static, Button
from textual.binding import Binding

from .. import ai_modes
from . import theme_css


class _AgentMenuRow(Static):
    """One row in the agent mode switcher popup: icon + label + purpose."""

    def __init__(self, mode_key, meta, is_active, index):
        active_cls = " cct-agentmenu-row-active" if is_active else ""
        super().__init__("", classes=f"cct-agentmenu-row cct-agentmenu-row-{mode_key}{active_cls}")
        self.mode_key = mode_key
        self.meta = meta
        self.is_active = is_active
        self.index = index

    def on_mount(self):
        self.redraw()

    def redraw(self):
        accent = ai_modes.accent_hex(self.mode_key) if hasattr(ai_modes, "accent_hex") else "#7aa2f7"
        faint = theme_css.current_hex("text-faint") if theme_css else "#565f89"
        icon = self.meta.get("icon", "🐱")
        label = self.meta.get("label", self.mode_key.title())
        role = self.meta.get("role", self.meta.get("full_label", label))
        purpose = self.meta.get("purpose", "")[:70]
        try:
            sw = getattr(self.app.size, "width", 80)
        except Exception:
            sw = 80

        if sw < 72:
            if self.is_active:
                btn_pill = f" [#12131d on {accent} b] ACTIVE \u2713 [/]"
            else:
                btn_pill = f" [{accent} on #1c2035 b] Switch \u21b5 [/]"
            purpose = purpose[:38]
            self.update(
                f"[{accent} b]{icon} {label}[/]{btn_pill}\n"
                f"  [{faint}]{purpose}[/]"
            )
        else:
            if self.is_active:
                btn_pill = f" [#12131d on {accent} b] ACTIVE \u2713 [/]"
            else:
                btn_pill = f" [{accent} on #1c2035 b] 1-Click Switch \u21b5 [/]"
            self.update(
                f"[{accent} b]{icon} {label}[/] [{faint}]· {role}[/]{btn_pill}\n"
                f"  [{faint}]{purpose}[/]"
            )

        if self.mode_key not in ("notebook", "research", "plan", "build", "debugger", "agent"):
            try:
                self.styles.border_top = ("tall", "#cdd6f4")
                self.styles.border_left = ("tall", accent)
                self.styles.border_bottom = ("tall", "#585b70")
                self.styles.border_right = ("tall", "#45475a")
                self.styles.background = "#201a2e"
            except Exception:
                pass

    def on_mouse_down(self, event):
        self.add_class("-active")

    def on_mouse_up(self, event):
        self.remove_class("-active")

    def on_click(self, event):
        self.remove_class("-active")
        if self.app.screen is self.screen:
            self.screen.dismiss(self.mode_key)


class _AgentMenuCloseButton(Button):
    """3D Option A Tall Bevel close button for Kitties header."""

    def __init__(self):
        super().__init__("✕", id="cct-agentmenu-close", classes="cct-agentmenu-close-btn")


class _ManageAgentsRow(Static):
    """Bottom action row: open full AI Agents & Kitties Customizer."""

    def __init__(self):
        super().__init__(
            "[#fab387 b]⚙ Config Kitties[/]  [#565f89]· Kitties Studio & System Prompt Editor \u21b5[/]\n"
            "  [#565f89]Manage custom personas, system prompts & agent skills[/]",
            classes="cct-agentmenu-row cct-agentmenu-manage",
        )

    def on_mouse_down(self, event):
        self.add_class("-active")

    def on_mouse_up(self, event):
        self.remove_class("-active")

    def on_click(self, event):
        self.remove_class("-active")
        if self.app.screen is self.screen:
            self.screen.dismiss("__manage__")


class AgentModeMenu(Screen):
    """Tactile 3D dropdown popup to quickly switch AI agents and modes."""

    BINDINGS = [
        Binding("escape", "dismiss_menu", "Close", show=False),
        Binding("up", "select_prev", "Previous", show=False),
        Binding("down", "select_next", "Next", show=False),
        Binding("enter", "confirm_selection", "Select", show=False),
    ]

    DEFAULT_CSS = """
    AgentModeMenu {
        align: left top;
        background: rgba(0, 0, 0, 0.65);
    }
    #cct-agentmenu-box {
        width: 74;
        max-width: 96%;
        height: auto;
        max-height: 94%;
        background: #13141f;
        border: tall;
        border-top: tall #8b92b2;
        border-left: tall #6e7594;
        border-bottom: tall #585b70;
        border-right: tall #45475a;
        padding: 0 1;
        layout: vertical;
        overflow: hidden;
    }
    AgentModeMenu.is-portrait #cct-agentmenu-box,
    .is-portrait #cct-agentmenu-box {
        width: 96%;
        max-width: 98%;
        max-height: 94%;
        padding: 0;
    }
    AgentModeMenu.is-portrait .cct-agentmenu-row,
    .is-portrait .cct-agentmenu-row {
        height: auto;
        min-height: 3;
        max-height: 4;
        padding: 0 1;
    }
    #cct-agentmenu-titlebar {
        height: 3;
        min-height: 3;
        max-height: 3;
        padding: 0 1;
        layout: horizontal;
        align-vertical: middle;
        background: #1c1e2d;
        color: #fab387;
        border-top: tall #fab387;
        border-left: tall #fab387;
        border-bottom: tall #585b70;
        border-right: tall #45475a;
        margin: 1 0 0 0;
    }
    #cct-agentmenu-title {
        text-style: bold;
        width: 1fr;
        align-vertical: middle;
        color: #fab387;
    }
    Button#cct-agentmenu-close, Button.cct-agentmenu-close-btn, #cct-agentmenu-close, .cct-agentmenu-close-btn {
        width: 5;
        min-width: 0;
        max-width: 5;
        height: 1;
        min-height: 0;
        max-height: 1;
        padding: 0;
        margin: 0;
        background: #2b1d24;
        color: #ff7b72;
        border: none;
        border-left: tall #ffa198;
        border-right: tall #c73859;
        content-align: center middle;
        text-style: bold;
    }
    Button#cct-agentmenu-close:hover, Button.cct-agentmenu-close-btn:hover, #cct-agentmenu-close:hover, .cct-agentmenu-close-btn:hover {
        background: #e06c75;
        color: #ffffff;
        border: none;
        border-left: tall #ffffff;
        border-right: tall #801020;
    }
    Button#cct-agentmenu-close:focus, Button#cct-agentmenu-close.-active, #cct-agentmenu-close:focus, #cct-agentmenu-close.-active {
        background: #201018;
        color: #f38ba8;
        border: none;
        border-left: tall #801020;
        border-right: tall #ffa5b5;
    }
    #cct-agentmenu-list {
        height: auto;
        min-height: 6;
        max-height: 18;
        padding: 1 0 0 0;
        margin: 0;
        overflow-y: auto;
        scrollbar-gutter: stable;
        scrollbar-size-vertical: 1;
        scrollbar-color: #fab387 #1c1e2d;
        scrollbar-background: #13141f;
        scrollbar-corner-color: #13141f;
        scrollbar-color-hover: #ffd7a8 #25283c;
    }
    .cct-agentmenu-row {
        height: 4;
        padding: 0 1;
        margin: 0 0 1 0;
        background: #25283c;
        border-top: tall #cdd6f4;
        border-left: tall #89b4fa;
        border-bottom: tall #585b70;
        border-right: tall #45475a;
        transition: background 60ms, border 60ms;
        overflow: hidden;
    }
    .cct-agentmenu-row:hover, .cct-agentmenu-row-focused {
        background: #383d5c;
        border-top: tall #ffffff;
        border-left: tall #f9e2af;
        border-bottom: tall #6e7594;
        border-right: tall #585b70;
    }
    .cct-agentmenu-row.-active {
        border-top: tall #1c1e2e;
        border-left: tall #1c1e2e;
        border-bottom: tall #cdd6f4;
        border-right: tall #89b4fa;
        background: #161724;
    }
    .cct-agentmenu-row-active {
        border-left: tall #7aa2f7;
    }

    /* --- Agent-Specific 3D Effects, Background Highlights & Tall Color Modes --- */

    /* Qala (Notebook & Science) — Electric Blue */
    .cct-agentmenu-row-notebook {
        background: #18223c;
        border-top: tall #a5c3ff;
        border-left: tall #7aa2f7;
        border-bottom: tall #587ab0;
        border-right: tall #587ab0;
    }
    .cct-agentmenu-row-notebook:hover,
    .cct-agentmenu-row-notebook.cct-agentmenu-row-focused {
        background: #28365e;
        border-top: tall #ffffff;
        border-left: tall #c2d8ff;
        border-bottom: tall #608bc7;
        border-right: tall #608bc7;
    }
    .cct-agentmenu-row-notebook.-active {
        border-top: tall #0e1220;
        border-left: tall #0e1220;
        border-bottom: tall #a5c3ff;
        border-right: tall #7aa2f7;
        background: #0e1220;
    }
    .cct-agentmenu-row-notebook.cct-agentmenu-row-active {
        background: #202d4e;
        border-top: tall #c2d8ff;
        border-left: tall #7aa2f7;
        border-bottom: tall #547eb8;
        border-right: tall #547eb8;
    }

    /* Sage (Research Agent) — Vivid Pink */
    .cct-agentmenu-row-research {
        background: #2a1626;
        border-top: tall #f5c2e7;
        border-left: tall #f38ba8;
        border-bottom: tall #994483;
        border-right: tall #994483;
    }
    .cct-agentmenu-row-research:hover,
    .cct-agentmenu-row-research.cct-agentmenu-row-focused {
        background: #401f3a;
        border-top: tall #ffffff;
        border-left: tall #ffb3d9;
        border-bottom: tall #994483;
        border-right: tall #994483;
    }
    .cct-agentmenu-row-research.-active {
        border-top: tall #140912;
        border-left: tall #140912;
        border-bottom: tall #f5c2e7;
        border-right: tall #f38ba8;
        background: #140912;
    }
    .cct-agentmenu-row-research.cct-agentmenu-row-active {
        background: #361b31;
        border-top: tall #ffc0cb;
        border-left: tall #f38ba8;
        border-bottom: tall #8a3c75;
        border-right: tall #8a3c75;
    }

    /* Mira (Planning Agent) — Emerald Green */
    .cct-agentmenu-row-plan {
        background: #18281d;
        border-top: tall #b9f27c;
        border-left: tall #a6e3a1;
        border-bottom: tall #528c5e;
        border-right: tall #528c5e;
    }
    .cct-agentmenu-row-plan:hover,
    .cct-agentmenu-row-plan.cct-agentmenu-row-focused {
        background: #263e2d;
        border-top: tall #ffffff;
        border-left: tall #d4ff9c;
        border-bottom: tall #599965;
        border-right: tall #599965;
    }
    .cct-agentmenu-row-plan.-active {
        border-top: tall #0c1610;
        border-left: tall #0c1610;
        border-bottom: tall #b9f27c;
        border-right: tall #a6e3a1;
        background: #0c1610;
    }
    .cct-agentmenu-row-plan.cct-agentmenu-row-active {
        background: #203527;
        border-top: tall #d4ff9c;
        border-left: tall #a6e3a1;
        border-bottom: tall #508c5b;
        border-right: tall #508c5b;
    }

    /* Aria (Build Agent) — Amber / Warm Peach */
    .cct-agentmenu-row-build {
        background: #281e14;
        border-top: tall #ffe2a8;
        border-left: tall #fab387;
        border-bottom: tall #9c6537;
        border-right: tall #9c6537;
    }
    .cct-agentmenu-row-build:hover,
    .cct-agentmenu-row-build.cct-agentmenu-row-focused {
        background: #3e2e1e;
        border-top: tall #ffffff;
        border-left: tall #ffecd0;
        border-bottom: tall #9c6537;
        border-right: tall #9c6537;
    }
    .cct-agentmenu-row-build.-active {
        border-top: tall #140d07;
        border-left: tall #140d07;
        border-bottom: tall #ffe2a8;
        border-right: tall #fab387;
        background: #140d07;
    }
    .cct-agentmenu-row-build.cct-agentmenu-row-active {
        background: #35271a;
        border-top: tall #ffecd0;
        border-left: tall #fab387;
        border-bottom: tall #8c5b32;
        border-right: tall #8c5b32;
    }

    /* Dex (Debugger Agent) — Crimson Red */
    .cct-agentmenu-row-debugger {
        background: #2a151b;
        border-top: tall #ffa0a0;
        border-left: tall #eba0ac;
        border-bottom: tall #9c3b4d;
        border-right: tall #9c3b4d;
    }
    .cct-agentmenu-row-debugger:hover,
    .cct-agentmenu-row-debugger.cct-agentmenu-row-focused {
        background: #401f28;
        border-top: tall #ffffff;
        border-left: tall #ffc2c2;
        border-bottom: tall #9c3b4d;
        border-right: tall #9c3b4d;
    }
    .cct-agentmenu-row-debugger.-active {
        border-top: tall #14080b;
        border-left: tall #14080b;
        border-bottom: tall #ffa0a0;
        border-right: tall #eba0ac;
        background: #14080b;
    }
    .cct-agentmenu-row-debugger.cct-agentmenu-row-active {
        background: #361a22;
        border-top: tall #ffc2c2;
        border-left: tall #eba0ac;
        border-bottom: tall #8a3443;
        border-right: tall #8a3443;
    }

    /* Nova (Autonomous Agent) — Purple / Lavender */
    .cct-agentmenu-row-agent {
        background: #241638;
        border-top: tall #dbc5fa;
        border-left: tall #cba6f7;
        border-bottom: tall #894cc4;
        border-right: tall #894cc4;
    }
    .cct-agentmenu-row-agent:hover,
    .cct-agentmenu-row-agent.cct-agentmenu-row-focused {
        background: #382156;
        border-top: tall #ffffff;
        border-left: tall #ecdcfc;
        border-bottom: tall #894cc4;
        border-right: tall #894cc4;
    }
    .cct-agentmenu-row-agent.-active {
        border-top: tall #12091c;
        border-left: tall #12091c;
        border-bottom: tall #dbc5fa;
        border-right: tall #cba6f7;
        background: #12091c;
    }
    .cct-agentmenu-row-agent.cct-agentmenu-row-active {
        background: #2f1c48;
        border-top: tall #ecdcfc;
        border-left: tall #cba6f7;
        border-bottom: tall #7c44b5;
        border-right: tall #7c44b5;
    }

    #cct-agentmenu-footer {
        height: 5;
        min-height: 5;
        max-height: 5;
        padding: 0 1 1 1;
        margin: 0;
        layout: vertical;
    }
    .cct-agentmenu-manage {
        height: 4;
        margin: 0;
        background: #25283c;
        border-top: tall #fab387;
        border-left: tall #fab387;
        border-bottom: tall #585b70;
        border-right: tall #45475a;
        padding: 0 1;
    }
    .cct-agentmenu-manage:hover, .cct-agentmenu-manage.cct-agentmenu-manage-focused {
        background: #38334a;
        border-top: tall #ffffff;
        border-left: tall #ffffff;
        border-bottom: tall #7a5030;
        border-right: tall #585b70;
    }
    .cct-agentmenu-manage.-active {
        border-top: tall #1c1e2e;
        border-left: tall #1c1e2e;
        border-bottom: tall #fab387;
        border-right: tall #f9e2af;
        background: #171520;
    }
    """
    CSS = DEFAULT_CSS

    def __init__(self, anchor=None):
        super().__init__()
        self._anchor = anchor
        current = ai_modes.current_mode() or "agent"
        modes = list(ai_modes.MODE_ORDER)
        for k in ai_modes.MODE_META:
            if k not in modes:
                modes.append(k)
        self._modes = modes
        self._selected = self._modes.index(current) if current in self._modes else 0

    def compose(self):
        with Vertical(id="cct-agentmenu-box"):
            with Horizontal(id="cct-agentmenu-titlebar"):
                yield Static("🐱 Kitties (1-Click Switch)", id="cct-agentmenu-title", classes="cct-agentmenu-title")
                yield _AgentMenuCloseButton()
            with VerticalScroll(id="cct-agentmenu-list"):
                current = ai_modes.current_mode() or "agent"
                for i, mode_key in enumerate(self._modes):
                    meta = ai_modes.MODE_META.get(mode_key, {})
                    is_active = (mode_key == current)
                    yield _AgentMenuRow(mode_key, meta, is_active, i)
            with Vertical(id="cct-agentmenu-footer"):
                yield _ManageAgentsRow()

    def on_mount(self):
        self._sync_selected_class()
        self._reposition()
        self.call_after_refresh(self._reposition)

    def on_resize(self, event=None):
        self._reposition()

    def _sync_selected_class(self):
        rows = list(self.query(_AgentMenuRow))
        for i, row in enumerate(rows):
            if i == self._selected:
                row.add_class("cct-agentmenu-row-focused")
                try:
                    row.scroll_visible(top=False, animate=False)
                except Exception:
                    pass
            else:
                row.remove_class("cct-agentmenu-row-focused")
        manage_rows = list(self.query(_ManageAgentsRow))
        if manage_rows:
            if self._selected == len(self._modes):
                manage_rows[0].add_class("cct-agentmenu-manage-focused")
                try:
                    manage_rows[0].scroll_visible(top=False, animate=False)
                except Exception:
                    pass
            else:
                manage_rows[0].remove_class("cct-agentmenu-manage-focused")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id in ("cct-agentmenu-close",):
            self.dismiss(None)

    def action_select_prev(self):
        if self._modes:
            self._selected = (self._selected - 1) % len(self._modes)
            self._sync_selected_class()

    def action_select_next(self):
        if self._modes:
            self._selected = (self._selected + 1) % len(self._modes)
            self._sync_selected_class()

    def action_confirm_selection(self):
        if 0 <= self._selected < len(self._modes):
            self.dismiss(self._modes[self._selected])
        elif self._selected == len(self._modes):
            self.dismiss("__manage__")

    def action_dismiss_menu(self):
        self.dismiss(None)

    def _reposition(self):
        try:
            box = self.query_one("#cct-agentmenu-box")
            screen_w = getattr(self.app.size, "width", 80)
            screen_h = getattr(self.app.size, "height", 25)
            is_portrait = (screen_w < 80) or (screen_w < screen_h * 1.25)
            self.set_class(is_portrait, "is-portrait")

            box_w = min(box.size.width or 74, screen_w - 2)
            box_h = min(box.size.height or 24, screen_h - 2)

            if is_portrait:
                target_x = max(1, (screen_w - box_w) // 2)
                target_y = max(1, (screen_h - box_h) // 2)
                box.styles.offset = (target_x, target_y)
            elif self._anchor and hasattr(self._anchor, "region"):
                r = self._anchor.region
                target_x = max(1, min(r.x, screen_w - box_w - 1))
                # Position directly above anchor in the composer footer
                target_y = r.y - box_h
                if target_y < 1:
                    target_y = max(1, r.y + getattr(r, "height", 1))
                target_y = max(1, min(target_y, screen_h - box_h - 1))
                box.styles.offset = (target_x, target_y)
            else:
                box.styles.offset = (max(1, (screen_w - box_w) // 2), max(1, (screen_h - box_h) // 2))
        except Exception:
            pass

