"""
CAT UI — Kitties & AI Modes Manager (v0.7.9.8+).

User Section > Kitties: Fully customizable AI agents & modes with a tactile
3D Skeuomorphic hardware chassis. Create unlimited AI agents in seconds,
automate your laptop completely, delegate tasks between kitties, and spawn
custom agents like Laptop Automator Kitty (💻), Multi Kitty (🔄), Grok Kitty (⚡),
and OpenAI Dots Kitty (⚪).
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import re

TEXTUAL_AVAILABLE = True
try:
    from textual.screen import Screen, ModalScreen
    from textual.containers import Vertical, Horizontal, VerticalScroll
    from textual.widgets import Static, Button, Input, TextArea
    from textual.binding import Binding
except Exception:
    TEXTUAL_AVAILABLE = False

if TEXTUAL_AVAILABLE:
    try:
        from .. import ai_modes
    except Exception:
        ai_modes = None
    try:
        from . import theme_css
    except Exception:
        theme_css = None

    _HEX_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")
    _KEY_RE = re.compile(r"^[a-z0-9_]{2,20}$")

    _PRESETS = [
        "#7aa2f7", "#bb9af7", "#e0af68", "#9ece6a",
        "#ff69b4", "#dc143c", "#f59e0b", "#10b981",
    ]

    def _valid_hex(s):
        return bool(_HEX_RE.match((s or "").strip()))

    def _valid_key(k):
        return bool(_KEY_RE.match((k or "").strip().lower()))

    class MultiLinePromptArea(TextArea):
        """Spacious, multi-line editor for AI Mode system prompts & behaviors.
        Implements both .text and .value so it is 100% compatible with TextArea
        and Input access patterns."""
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("show_line_numbers", False)
            super().__init__(*args, **kwargs)

        @property
        def value(self) -> str:
            return self.text

        @value.setter
        def value(self, v: str) -> None:
            self.load_text(str(v or ""))

    class _ModeRow(Horizontal):
        """One Kitty's full 3D skeuomorphic editor row (colour + label/icon/prompt + actions)."""
        def __init__(self, mode_key):
            super().__init__(classes="mcc-row", id=f"mcc-row-{mode_key}")
            self.mode_key = mode_key
            self._edit_expanded = False

        def compose(self):
            m = ai_modes.MODE_META.get(self.mode_key, {})
            label = m.get("label", self.mode_key)
            icon = m.get("icon", "🐱")
            purpose = m.get("purpose", "")[:120]
            prompt = m.get("system_prompt", "")
            accent = ai_modes.accent_hex(self.mode_key)
            g_start, g_end = ai_modes.gradient(self.mode_key)
            is_current = (self.mode_key == ai_modes.current_mode())
            cur_mark = "● ACTIVE" if is_current else "○"

            with Vertical(classes="mcc-info"):
                with Horizontal(classes="mcc-header"):
                    yield Static(f"[{accent} bold]{cur_mark}[/]  {icon} [b]{label}[/b]", classes="mcc-label", markup=True)
                    yield Static(f"[{accent}]/{self.mode_key}[/]", classes="mcc-key", markup=True)
                yield Static(purpose or "General coding & reasoning Kitty persona", classes="mcc-purpose")
                yield Static(f"[{accent}]█[/] {accent}  grad [{g_start}]█[/][{g_end}]█[/] {g_start}→{g_end}", classes="mcc-preview", markup=True)

                # Spacious 3D edit box (expands when '✎ Edit' is clicked)
                with Vertical(classes="mcc-editbox", id=f"mcc-edit-{self.mode_key}"):
                    yield Static(f"✎ Edit {label} Persona & Instructions:", classes="mcc-edit-title")
                    with Horizontal(classes="mcc-edit-row"):
                        yield Input(value=label, placeholder="Display Name", id=f"mcc-label-{self.mode_key}", classes="mcc-input-sm")
                        yield Input(value=icon, placeholder="Icon", id=f"mcc-icon-{self.mode_key}", classes="mcc-input-sm mcc-input-icon")
                        yield Input(value=accent, placeholder="#rrggbb", id=f"mcc-input-{self.mode_key}", classes="mcc-input")
                    yield Input(value=purpose, placeholder="Purpose / Specialty (one-line summary)", id=f"mcc-purpose-{self.mode_key}", classes="mcc-input-wide")
                    yield Static("System Prompt & Behavior Instructions (Multi-line):", classes="mcc-prompt-label")
                    yield MultiLinePromptArea(text=prompt, id=f"mcc-prompt-{self.mode_key}", classes="mcc-prompt-area")
                    with Horizontal(classes="mcc-edit-actions"):
                        yield Button("💾 Save Persona", id=f"mcc-save-{self.mode_key}", variant="primary", classes="cct-btn-sm mcc-3d-btn")
                        yield Button("✕ Close", id=f"mcc-cancel-{self.mode_key}", classes="cct-btn-sm mcc-3d-btn")
                        yield Button("↺ Default", id=f"mcc-reset-{self.mode_key}", classes="cct-btn-sm mcc-3d-btn")
                        if self.mode_key not in ("notebook", "research", "plan", "build", "debugger", "agent"):
                            yield Button("🗑 Delete", id=f"mcc-delete-{self.mode_key}", variant="error", classes="cct-btn-sm mcc-3d-btn")

            with Vertical(classes="mcc-actions"):
                yield Button("⚡ Activate", id=f"mcc-activate-{self.mode_key}", variant="default", classes="cct-btn-sm mcc-3d-btn")
                yield Button("✎ Edit Mode", id=f"mcc-toggle-edit-{self.mode_key}", classes="cct-btn-sm mcc-3d-btn")

        def toggle_edit(self):
            self._edit_expanded = not self._edit_expanded
            try:
                eb = self.query_one(f"#mcc-edit-{self.mode_key}", Vertical)
                if self._edit_expanded:
                    eb.add_class("show")
                    try:
                        self.query_one(f"#mcc-label-{self.mode_key}", Input).focus()
                    except Exception:
                        pass
                else:
                    eb.remove_class("show")
            except Exception:
                pass

        def refresh_preview(self):
            try:
                m = ai_modes.MODE_META.get(self.mode_key, {})
                label = m.get("label", self.mode_key)
                icon = m.get("icon", "🐱")
                purpose = m.get("purpose", "")[:120]
                prompt = m.get("system_prompt", "")
                accent = ai_modes.accent_hex(self.mode_key)
                g_start, g_end = ai_modes.gradient(self.mode_key)
                is_current = (self.mode_key == ai_modes.current_mode())
                cur_mark = "● ACTIVE" if is_current else "○"

                self.query_one(".mcc-label", Static).update(f"[{accent} bold]{cur_mark}[/]  {icon} [b]{label}[/b]")
                self.query_one(".mcc-key", Static).update(f"[{accent}]/{self.mode_key}[/]")
                self.query_one(".mcc-purpose", Static).update(purpose or "General coding & reasoning Kitty persona")
                self.query_one(".mcc-preview", Static).update(f"[{accent}]█[/] {accent}  grad [{g_start}]█[/][{g_end}]█[/] {g_start}→{g_end}")

                try:
                    self.query_one(f"#mcc-input-{self.mode_key}", Input).value = accent
                except Exception:
                    pass
                try:
                    self.query_one(f"#mcc-label-{self.mode_key}", Input).value = label
                except Exception:
                    pass
                try:
                    self.query_one(f"#mcc-icon-{self.mode_key}", Input).value = icon
                except Exception:
                    pass
                try:
                    self.query_one(f"#mcc-purpose-{self.mode_key}", Input).value = purpose
                except Exception:
                    pass
                try:
                    self.query_one(f"#mcc-prompt-{self.mode_key}").value = prompt
                except Exception:
                    pass
            except Exception:
                pass

    # Alias for backward compat
    _ModeColorRow = _ModeRow

    class ModeColorsPanel(ModalScreen):
        """Kitties & AI Modes Manager — 3D Skeuomorphic Tactile Chassis."""

        CSS = """
        ModeColorsPanel {
            align: center middle;
            background: rgba(15, 15, 20, 0.65);
        }
        #mcc-box {
            width: 104; max-width: 98%; height: auto; max-height: 48;
            background: #1a1b26;
            border: tall #565f89;
            border-top: tall #7aa2f7;
            border-left: tall #7aa2f7;
            border-bottom: tall #0f0f14;
            border-right: tall #0f0f14;
            padding: 0; layout: vertical; overflow: hidden;
        }
        #mcc-titlebar {
            height: 5; min-height: 5; padding: 0 2;
            background: #1f2335;
            border-bottom: tall #0f0f14;
            layout: horizontal; align: center middle;
        }
        #mcc-title {
            width: 1fr; text-style: bold; color: #7aa2f7;
            height: 3; content-align: left middle;
        }
        #mcc-close {
            width: auto; min-width: 11; height: 3; min-height: 3; max-height: 3;
            padding: 0 1; margin: 0;
            background: #e06c75; color: #ffffff;
            text-style: bold;
            border-top: tall #ff9999;
            border-left: tall #ff9999;
            border-bottom: tall #4a151b;
            border-right: tall #4a151b;
            content-align: center middle;
        }
        #mcc-close:hover {
            background: #ff5370; color: #ffffff;
            border-top: tall #ffffff;
            border-left: tall #ffffff;
        }
        #mcc-close:focus {
            border-top: tall #4a151b;
            border-left: tall #4a151b;
            border-bottom: tall #ff9999;
            border-right: tall #ff9999;
        }
        #mcc-subtitle {
            color: #7982a9; height: auto; padding: 0 2;
        }
        #mcc-spawners {
            height: 5; min-height: 5; padding: 0 2; layout: horizontal;
            border-bottom: solid #24283b; background: #16161e;
            align: center middle;
        }
        #mcc-spawners-label {
            width: auto; color: #c0caf5; text-style: bold; height: 3;
            content-align: center middle; padding-right: 1;
        }
        .mcc-spawner-btn {
            height: 3; min-height: 3; max-height: 3;
            margin-right: 1; padding: 0 1;
            border: tall;
            border-top: tall #565f89; border-left: tall #565f89;
            border-bottom: tall #0f0f14; border-right: tall #0f0f14;
            background: #24283b; color: #c0caf5;
            text-style: bold;
            content-align: center middle;
        }
        .mcc-spawner-btn:hover {
            border-top: tall #ffffff; border-left: tall #7aa2f7;
            background: #3b4261; color: #ffffff;
        }
        .mcc-spawner-btn:focus {
            border-top: tall #0f0f14; border-left: tall #0f0f14;
            border-bottom: tall #7aa2f7; border-right: tall #7aa2f7;
            background: #16161e;
        }
        #mcc-presets {
            height: 5; min-height: 5; padding: 0 2; layout: horizontal;
            border-bottom: solid #24283b; background: #14151f;
            align: center middle;
        }
        #mcc-presets-label {
            width: auto; color: #c0caf5; text-style: bold; height: 3;
            content-align: center middle; padding-right: 1;
        }
        .mcc-preset {
            width: 5; min-width: 5; height: 3; min-height: 3; padding: 0;
            margin-right: 1;
            border-top: tall #ffffff 45%;
            border-left: tall #ffffff 45%;
            border-bottom: tall #000000 65%;
            border-right: tall #000000 65%;
            content-align: center middle;
            text-style: bold;
        }
        .mcc-preset:hover {
            border-top: tall #ffffff;
            border-left: tall #ffffff;
        }
        .mcc-preset:focus {
            border-top: tall #000000;
            border-left: tall #000000;
            border-bottom: tall #ffffff;
            border-right: tall #ffffff;
        }
        #mcc-create {
            height: auto; padding: 1 2; border-bottom: tall #0f0f14; background: #1f2335 40%;
        }
        #mcc-create-title { height: 1; text-style: bold; color: #7aa2f7; }
        #mcc-create-row1 { height: 3; layout: horizontal; margin-top: 1; }
        #mcc-create-row1 Input { width: 1fr; margin-right: 1; }
        #mcc-create-row2 { height: 3; layout: horizontal; margin-top: 1; }
        #mcc-create-row2 Input { width: 1fr; margin-right: 1; }
        #mcc-create-row3 { height: 3; layout: horizontal; margin-top: 1; }
        #mcc-create-row3 Input { width: 1fr; }
        #mcc-create-actions { height: 3; layout: horizontal; margin-top: 1; }
        #mcc-create-actions Button { margin-right: 1; }
        #mcc-list {
            height: 1fr; min-height: 12; max-height: 26;
            overflow-y: auto; overflow-x: hidden;
            scrollbar-gutter: stable; scrollbar-size: 1 1;
            margin: 0 1; padding: 0;
        }
        .mcc-row {
            height: auto; min-height: 7; padding: 1 1;
            border-bottom: solid #24283b;
            border-top: tall #3b4261; border-left: tall #3b4261;
            border-right: tall #16161e;
            background: #1a1b26;
            layout: horizontal;
            margin-bottom: 1;
        }
        .mcc-row:hover {
            border-left: tall #7aa2f7; background: #24283b;
        }
        .mcc-info { width: 1fr; height: auto; min-width: 24; }
        .mcc-header { height: 1; layout: horizontal; }
        .mcc-label { width: auto; height: 1; text-style: bold; margin-right: 1; color: #c0caf5; }
        .mcc-key { width: auto; height: 1; color: #7982a9; }
        .mcc-purpose { width: auto; height: 1; color: #7982a9; }
        .mcc-preview { width: auto; height: 1; color: #9aa5ce; }
        .mcc-preview { width: auto; height: 1; color: #9aa5ce; }
        .mcc-editbox {
            height: auto; margin-top: 1; display: none; background: #13141f; padding: 1;
            border: tall #7aa2f7;
            border-top: tall #7aa2f7; border-left: tall #7aa2f7;
            border-bottom: tall #0f0f14; border-right: tall #0f0f14;
        }
        .mcc-editbox.show { display: block; }
        .mcc-edit-title { color: #7aa2f7; text-style: bold; height: 1; margin-bottom: 1; }
        .mcc-edit-row { height: 3; layout: horizontal; margin-bottom: 1; }
        .mcc-input-sm { width: 1fr; margin-right: 1; }
        .mcc-input-icon { width: 10; min-width: 10; }
        .mcc-input { width: 16; min-width: 16; height: 3; margin-right: 1; }
        .mcc-input-wide { width: 100%; height: 3; margin-bottom: 1; }
        .mcc-prompt-label { color: #7aa2f7; height: 1; margin-top: 1; text-style: bold; }
        .mcc-prompt-area {
            width: 100%; height: 6; min-height: 6; max-height: 9;
            background: #1a1b26; border: solid #565f89;
            margin-bottom: 1;
        }
        .mcc-edit-actions { height: 3; layout: horizontal; margin-top: 1; }
        .mcc-edit-actions Button { margin-right: 1; }
        .mcc-actions {
            width: auto; height: auto; min-width: 18;
            layout: vertical; align: right middle;
        }
        .mcc-actions Button { min-width: 14; height: 3; margin-bottom: 1; }
        .mcc-3d-btn {
            border: tall;
            border-top: tall #565f89; border-left: tall #565f89;
            border-bottom: tall #0f0f14; border-right: tall #0f0f14;
            background: #24283b; color: #c0caf5;
        }
        .mcc-3d-btn:hover {
            border-top: tall #ffffff; border-left: tall #7aa2f7;
            background: #3b4261;
        }
        .mcc-3d-btn:focus {
            border-top: tall #0f0f14; border-left: tall #0f0f14;
            border-bottom: tall #7aa2f7; border-right: tall #7aa2f7;
            background: #16161e;
        }
        #mcc-create {
            height: auto; padding: 1 2; border-bottom: tall #0f0f14; background: #1f2335 40%;
            display: none;
        }
        #mcc-create.show {
            display: block;
        }
        #mcc-create-header {
            height: 3; layout: horizontal; align: center middle; margin-bottom: 1;
        }
        #mcc-create-title { width: 1fr; height: 1; text-style: bold; color: #7aa2f7; }
        #mcc-create-close { width: auto; height: 3; }
        #mcc-actions {
            height: auto; padding: 1 2; border-top: tall #0f0f14; background: #1f2335;
            layout: horizontal;
        }
        #mcc-actions-left { width: 1fr; layout: horizontal; }
        #mcc-actions-left Button { margin-right: 1; }
        #mcc-actions-right { width: auto; layout: horizontal; }
        #mcc-actions-right Button { margin-left: 1; }
        #mcc-hint { color: #7982a9; height: auto; padding: 0 2 1 2; text-align: center; }
        #mcc-error { color: #f7768e; height: 1; padding: 0 2; display: none; text-style: bold; }
        #mcc-error.show { display: block; }
        .cct-compact .mcc-row { layout: vertical; min-height: 10; }
        .cct-compact .mcc-actions { width: 100%; padding-top: 1; }
        .cct-compact #mcc-box { width: 98%; }
        .cct-compact #mcc-create-row1 { layout: vertical; height: auto; }
        .cct-compact #mcc-create-row1 Input { width: 100%; margin-bottom: 1; }
        .cct-compact #mcc-create-row2 { layout: vertical; height: auto; }
        .cct-compact #mcc-create-row2 Input { width: 100%; margin-bottom: 1; }
        """

        BINDINGS = [Binding("escape", "cancel", "Cancel")]

        def __init__(self, initial_edit=None):
            super().__init__()
            self.initial_edit = (initial_edit or "").strip().lower()

        def compose(self):
            with Vertical(id="mcc-box"):
                with Horizontal(id="mcc-titlebar"):
                    yield Static("🐱  Kitties & AI Modes Studio", id="mcc-title")
                    yield Button("✕ Close", id="mcc-close")
                yield Static("Active Personas & Autonomous AI Agents. Manage, customize, and edit AI modes with ease.", id="mcc-subtitle")

                # Streamlined Agent Workshop action bar
                with Horizontal(id="mcc-spawners"):
                    yield Static("Agent Workshop:", id="mcc-spawners-label")
                    yield Button("＋ Create Agent", id="mcc-action-new", classes="mcc-spawner-btn")
                    yield Button("⚡ Fast Clone", id="mcc-action-clone", classes="mcc-spawner-btn")
                    yield Button("🔄 Delegation", id="mcc-action-share", classes="mcc-spawner-btn")

                with Horizontal(id="mcc-presets"):
                    yield Static("Palette:", id="mcc-presets-label")
                    for idx, hx in enumerate(_PRESETS):
                        btn = Button(" ", id=f"mcc-preset-{idx}", classes="mcc-preset")
                        btn.tooltip = f"Apply {hx} to selected Kitty"
                        btn._preset_hex = hx
                        yield btn

                # Create form (hidden by default until '＋ Create Agent' is clicked)
                with Vertical(id="mcc-create"):
                    with Horizontal(id="mcc-create-header"):
                        yield Static("＋ Create Custom AI Agent Persona", id="mcc-create-title")
                        yield Button("✕ Cancel", id="mcc-create-close", classes="cct-btn-sm mcc-3d-btn")
                    with Horizontal(id="mcc-create-row1"):
                        yield Input(placeholder="key (e.g. my_agent, coder, dev)", id="mcc-new-key", classes="mcc-input-sm")
                        yield Input(placeholder="Label (e.g. Master Coder)", id="mcc-new-label", classes="mcc-input-sm")
                        yield Input(placeholder="Icon (⚡, 🚀, 🐱, ✨)", id="mcc-new-icon", classes="mcc-input-sm mcc-input-icon")
                        yield Input(placeholder="#rrggbb", id="mcc-new-color", classes="mcc-input")
                    with Horizontal(id="mcc-create-row2"):
                        yield Input(placeholder="Purpose (e.g. Autonomous AI agent with full computer & CAT CLI automation)", id="mcc-new-purpose", classes="mcc-input-sm")
                    with Vertical(id="mcc-create-row3"):
                        yield Static("System Prompt & Behavior Instructions (Multi-line):", classes="mcc-prompt-label")
                        yield MultiLinePromptArea(id="mcc-new-prompt", classes="mcc-prompt-area")
                    with Horizontal(id="mcc-create-actions"):
                        yield Button("Create Kitty", id="mcc-create-btn", variant="primary", classes="mcc-3d-btn")
                        yield Button("Clear", id="mcc-create-clear", classes="mcc-3d-btn")

                yield Static("", id="mcc-error")

                with VerticalScroll(id="mcc-list"):
                    for key in list(ai_modes.MODE_ORDER):
                        yield _ModeRow(key)

                with Horizontal(id="mcc-actions"):
                    with Horizontal(id="mcc-actions-left"):
                        yield Button("↺ Restore Defaults", id="mcc-reset-all", classes="mcc-3d-btn")
                    with Horizontal(id="mcc-actions-right"):
                        yield Button("Done ↵", id="mcc-close2", variant="primary", classes="mcc-3d-btn")
                yield Static("Tip: Click '✎ Edit Mode' on any Kitty to configure colors, purpose, and custom system prompts.", id="mcc-hint")

        def on_mount(self):
            try:
                self.query_one("#mcc-box").add_class("open")
            except Exception:
                pass
            try:
                for idx, hx in enumerate(_PRESETS):
                    btn = self.query_one(f"#mcc-preset-{idx}", Button)
                    btn.styles.background = hx
                    btn.label = " "
                    btn.tooltip = f"Apply {hx} to selected Kitty"
            except Exception:
                pass
            if self.size.width < 96 or self.size.height < 36:
                try:
                    self.query_one("#mcc-box").add_class("cct-compact")
                except Exception:
                    pass
            if getattr(self, "initial_edit", None) and ai_modes and self.initial_edit in ai_modes.MODE_META:
                try:
                    row = self.query_one(f"#mcc-row-{self.initial_edit}", _ModeRow)
                    if not row._edit_expanded:
                        row.toggle_edit()
                    self.call_after_refresh(lambda: row.scroll_visible())
                except Exception:
                    pass

        def _show_status(self, msg="", is_error=False):
            try:
                lbl = self.query_one("#mcc-error", Static)
                if msg:
                    prefix = "⚠ " if is_error else "✓ "
                    color = "#f7768e" if is_error else "#9ece6a"
                    lbl.styles.color = color
                    lbl.update(f"[{color} bold]{prefix}{msg}[/]")
                    lbl.add_class("show")
                else:
                    lbl.remove_class("show")
            except Exception:
                pass

        def _show_error(self, msg=""):
            self._show_status(msg, is_error=True)

        def _show_info(self, msg=""):
            self._show_status(msg, is_error=False)

        def _repaint_app(self):
            try:
                app = self.app
                if hasattr(app, "_repaint_theme_layers"):
                    app._repaint_theme_layers()
                else:
                    app.refresh_css(animate=False)
                try:
                    if hasattr(app, "composer") and hasattr(app, "_current_ai_mode"):
                        app.composer.set_ai_mode(app._current_ai_mode)
                except Exception:
                    pass
            except Exception:
                pass

        def _refresh_list(self):
            try:
                container = self.query_one("#mcc-list", VerticalScroll)
                desired_order = list(ai_modes.MODE_ORDER)
                current_rows = {getattr(r, "mode_key", None): r for r in container.query(_ModeRow)}

                # 1. Remove rows that were deleted
                for key, row in list(current_rows.items()):
                    if key and key not in desired_order:
                        row.remove()

                # 2. Update existing rows or mount new ones
                for key in desired_order:
                    if key in current_rows and current_rows[key] is not None:
                        current_rows[key].refresh_preview()
                    else:
                        new_row = _ModeRow(key)
                        container.mount(new_row)
                # 3. Ensure visual order matches desired_order
                try:
                    container.sort_children(
                        key=lambda w: desired_order.index(getattr(w, "mode_key", ""))
                        if getattr(w, "mode_key", None) in desired_order else 999
                    )
                except Exception:
                    pass
            except Exception:
                pass
            self._repaint_app()

        def _refresh_row(self, key):
            try:
                row = self.query_one(f"#mcc-row-{key}", _ModeRow)
                row.refresh_preview()
            except Exception:
                pass
            self._repaint_app()

        def on_button_pressed(self, event):
            bid = event.button.id or ""

            # 1. Preset Palette clicks
            if bid.startswith("mcc-preset-"):
                try:
                    hx = getattr(event.button, "_preset_hex", None) or _PRESETS[int(bid.split("-")[-1])]
                    focused = None
                    target_mode = None
                    for k in list(ai_modes.MODE_ORDER):
                        try:
                            inp = self.query_one(f"#mcc-input-{k}", Input)
                            if inp.has_focus:
                                focused = inp
                                target_mode = k
                                break
                        except Exception:
                            pass
                    if focused is None:
                        try:
                            new_inp = self.query_one("#mcc-new-color", Input)
                            if new_inp.has_focus:
                                focused = new_inp
                        except Exception:
                            pass
                    if focused is None:
                        cur = ai_modes.current_mode()
                        try:
                            focused = self.query_one(f"#mcc-input-{cur}", Input)
                            target_mode = cur
                        except Exception:
                            focused = self.query_one("#mcc-new-color", Input)
                    if focused:
                        focused.value = hx
                        focused.focus()
                    if target_mode and _valid_hex(hx):
                        ai_modes.update_mode(target_mode, accent_hex=hx)
                        self._refresh_row(target_mode)
                        self._show_info(f"Color {hx} applied to '{target_mode}'")
                    else:
                        self._show_info(f"Color {hx} selected")
                except Exception:
                    pass
                return

            # 2. Close actions
            if bid in ("mcc-close", "mcc-close2"):
                self.dismiss(None)
                return

            # 3. Agent Workshop Actions
            if bid == "mcc-action-new":
                try:
                    cbox = self.query_one("#mcc-create", Vertical)
                    cbox.add_class("show")
                    self.query_one("#mcc-new-key", Input).value = "custom_agent"
                    self.query_one("#mcc-new-label", Input).value = "Custom Agent"
                    self.query_one("#mcc-new-icon", Input).value = "✨"
                    self.query_one("#mcc-new-color", Input).value = "#bb9af7"
                    self.query_one("#mcc-new-purpose", Input).value = "Autonomous AI agent with full computer & CAT CLI automation."
                    self.query_one("#mcc-new-prompt", MultiLinePromptArea).value = (
                        "You are a specialized autonomous AI agent in CAT CLI. You operate with first-principles "
                        "reasoning, Think Mode chain-of-thought, and full authority to run commands and automate workflows."
                    )
                    self.query_one("#mcc-new-key", Input).focus()
                    self._show_info("Ready to create custom agent. Adjust details above and click 'Create Kitty'.")
                    try:
                        self.app._system_note("Ready to create a custom AI agent. Enter details and click 'Create Kitty'.")
                    except Exception:
                        pass
                except Exception:
                    pass
                return

            if bid == "mcc-create-close":
                try:
                    self.query_one("#mcc-create", Vertical).remove_class("show")
                except Exception:
                    pass
                return

            if bid == "mcc-action-clone":
                try:
                    cur = ai_modes.current_mode()
                    cur_info = ai_modes.get_mode_info(cur)
                    base_key = f"{cur}_clone"
                    cand_key = base_key
                    counter = 2
                    while cand_key in ai_modes.MODE_META:
                        cand_key = f"{cur}_clone{counter}"
                        counter += 1

                    lbl = f"{cur_info.get('label', cur)} (Clone)"
                    icn = cur_info.get('icon', '⚡')
                    preset_idx = (len(ai_modes.MODE_ORDER) + 1) % len(_PRESETS)
                    clr = _PRESETS[preset_idx]
                    purp = cur_info.get('purpose', '') or f"Cloned agent based on {cur} with full automation capabilities."
                    prmpt = cur_info.get('system_prompt', '') or f"You are a cloned high-capability AI agent based on {cur}."

                    ok, msg = ai_modes.create_mode(cand_key, lbl, icn, clr, purp, prmpt)
                    if ok:
                        self._show_info(f"⚡ Cloned '{cur}' into new agent '{cand_key}'!")
                        self._refresh_list()
                        try:
                            self.app._system_note(f"⚡ Cloned '{cur}' into new agent '{cand_key}'!")
                        except Exception:
                            pass
                    else:
                        self._show_error(msg)
                except Exception as e:
                    self._show_error(str(e))
                return

            if bid == "mcc-action-share":
                try:
                    cur = ai_modes.current_mode()
                    tgt = "agent" if cur != "agent" else "debugger"
                    ai_modes.share_task_between_kitties(
                        from_kitty=cur,
                        to_kitty=tgt,
                        task_objective=f"Delegated task workflow from {cur}",
                        prompt="Autonomous task handoff with full computer execution context.",
                        response=""
                    )
                    self._show_info(f"🔄 Task delegated: '{cur}' → '{tgt}'! Next prompt will include shared context.")
                    try:
                        self.app._system_note(f"🔄 Task sharing queue active: delegated from {cur} to {tgt}.")
                    except Exception:
                        pass
                except Exception as e:
                    self._show_error(str(e))
                return

            # 4. Reset All
            if bid == "mcc-reset-all":
                ai_modes.reset_all_modes()
                self._refresh_list()
                try:
                    self.app._system_note("All Kitties restored to defaults")
                except Exception:
                    pass
                self._show_error("")
                return

            # 5. Clear Form
            if bid == "mcc-create-clear":
                for iid in ["#mcc-new-key", "#mcc-new-label", "#mcc-new-icon", "#mcc-new-color", "#mcc-new-purpose", "#mcc-new-prompt"]:
                    try:
                        self.query_one(iid, Input).value = ""
                    except Exception:
                        pass
                self._show_error("")
                return

            # 6. Create Kitty
            if bid == "mcc-create-btn":
                try:
                    key = self.query_one("#mcc-new-key", Input).value.strip().lower()
                    label = self.query_one("#mcc-new-label", Input).value.strip()
                    icon = self.query_one("#mcc-new-icon", Input).value.strip()
                    color = self.query_one("#mcc-new-color", Input).value.strip()
                    purpose = self.query_one("#mcc-new-purpose", Input).value.strip()
                    prompt_w = self.query_one("#mcc-new-prompt")
                    prompt = (getattr(prompt_w, "text", None) or getattr(prompt_w, "value", "") or "").strip()
                    if not _valid_key(key):
                        self._show_error("Key: 2-20 chars a-z0-9_")
                        return
                    if not _valid_hex(color):
                        self._show_error(f"Invalid hex '{color}'")
                        return
                    ok, msg = ai_modes.create_mode(key, label or key.title(), icon or "🐱", color, purpose, prompt)
                    if ok:
                        self._show_info(f"✓ Kitty '{key}' created successfully!")
                        self._refresh_list()
                        for iid in ["#mcc-new-key", "#mcc-new-label", "#mcc-new-icon", "#mcc-new-color", "#mcc-new-purpose", "#mcc-new-prompt"]:
                            try:
                                self.query_one(iid, Input).value = ""
                            except Exception:
                                pass
                        try:
                            self.query_one("#mcc-create", Vertical).remove_class("show")
                        except Exception:
                            pass
                        try:
                            self.app._system_note(f"Kitty '{key}' created")
                        except Exception:
                            pass
                    else:
                        self._show_error(msg)
                except Exception as e:
                    self._show_error(str(e))
                return

            # 7. Activate Kitty
            if bid.startswith("mcc-activate-"):
                mode = bid.replace("mcc-activate-", "")
                ai_modes.set_mode(mode)
                self._repaint_app()
                self._refresh_list()
                self._show_info(f"⚡ Active Kitty switched to '{mode}'!")
                try:
                    self.app._system_note(f"Active Kitty switched to {mode}")
                except Exception:
                    pass
                return

            # 8. Toggle Edit Box
            if bid.startswith("mcc-toggle-edit-"):
                mode = bid.replace("mcc-toggle-edit-", "")
                try:
                    row = self.query_one(f"#mcc-row-{mode}", _ModeRow)
                    row.toggle_edit()
                except Exception:
                    pass
                return

            if bid.startswith("mcc-cancel-"):
                mode = bid.replace("mcc-cancel-", "")
                try:
                    row = self.query_one(f"#mcc-row-{mode}", _ModeRow)
                    if getattr(row, "_edit_expanded", False):
                        row.toggle_edit()
                except Exception:
                    pass
                return

            if bid.startswith("mcc-reset-"):
                mode = bid.replace("mcc-reset-", "")
                try:
                    if hasattr(ai_modes, "_DEFAULT_MODE_META") and mode in ai_modes._DEFAULT_MODE_META:
                        def_m = ai_modes._DEFAULT_MODE_META[mode]
                        accent_hex = ai_modes._rgb_to_hex(def_m["accent"])
                        ai_modes.update_mode(
                            mode,
                            label=def_m["label"],
                            icon=def_m["icon"],
                            accent_hex=accent_hex,
                            purpose=def_m["purpose"],
                            system_prompt=def_m.get("system_prompt", ""),
                        )
                        self._refresh_row(mode)
                        self._show_info(f"↺ Restored '{mode}' to factory defaults.")
                    else:
                        self._show_info(f"Mode '{mode}' has no factory preset.")
                except Exception as e:
                    self._show_error(str(e))
                return

            # 9. Save Row
            if bid.startswith("mcc-save-"):
                mode = bid.replace("mcc-save-", "")
                try:
                    label = self.query_one(f"#mcc-label-{mode}", Input).value.strip()
                    icon = self.query_one(f"#mcc-icon-{mode}", Input).value.strip()
                    color = self.query_one(f"#mcc-input-{mode}", Input).value.strip()
                    purpose = self.query_one(f"#mcc-purpose-{mode}", Input).value.strip()
                    prompt_w = self.query_one(f"#mcc-prompt-{mode}")
                    prompt = (getattr(prompt_w, "text", None) or getattr(prompt_w, "value", "") or "").strip()
                    if color and not _valid_hex(color):
                        self._show_error(f"Invalid hex for {mode}: '{color}'")
                        return
                    ok = ai_modes.update_mode(
                        mode,
                        label=label if label else None,
                        icon=icon if icon else None,
                        accent_hex=color if color and _valid_hex(color) else None,
                        purpose=purpose if purpose else None,
                        system_prompt=prompt if prompt else None,
                    )
                    if ok:
                        self._show_info(f"✓ Kitty '{mode}' saved successfully!")
                        self._refresh_row(mode)
                        try:
                            row = self.query_one(f"#mcc-row-{mode}", _ModeRow)
                            if getattr(row, "_edit_expanded", False):
                                row.toggle_edit()
                        except Exception:
                            pass
                        try:
                            self.app._system_note(f"Kitty '{mode}' saved")
                        except Exception:
                            pass
                    else:
                        self._show_error(f"Could not save {mode}")
                except Exception as e:
                    self._show_error(str(e))
                return

            # 10. Delete Row
            if bid.startswith("mcc-delete-"):
                mode = bid.replace("mcc-delete-", "")
                ok, msg = ai_modes.delete_mode(mode)
                if ok:
                    self._show_info(msg)
                    self._refresh_list()
                    try:
                        self.app._system_note(msg)
                    except Exception:
                        pass
                else:
                    self._show_error(msg)
                return

            if bid.startswith("mcc-up-"):
                mode = bid.replace("mcc-up-", "")
                if ai_modes.move_mode(mode, -1):
                    self._refresh_list()
                    self._show_info(f"Moved '{mode}' up")
                else:
                    self._show_error("Already at top")
                return

            if bid.startswith("mcc-down-"):
                mode = bid.replace("mcc-down-", "")
                if ai_modes.move_mode(mode, 1):
                    self._refresh_list()
                    self._show_info(f"Moved '{mode}' down")
                else:
                    self._show_error("Already at bottom")
                return

            # 12. Reset Row
            if bid.startswith("mcc-reset-"):
                mode = bid.replace("mcc-reset-", "")
                if mode == "all":
                    return
                if ai_modes.reset_mode_color(mode):
                    self._refresh_row(mode)
                    try:
                        self.app._system_note(f"Kitty '{mode}' reset to default")
                    except Exception:
                        pass
                    self._show_error("")
                else:
                    self._show_error(f"Cannot reset '{mode}' (custom Kitty — delete to remove)")
                return

        def on_input_submitted(self, event):
            iid = getattr(event.input, "id", "") or ""
            if iid.startswith("mcc-input-") and not iid.startswith("mcc-new"):
                mode = iid.replace("mcc-input-", "")
                try:
                    val = event.input.value.strip()
                    if not _valid_hex(val):
                        self._show_error(f"Invalid hex: '{val}'")
                        return
                    if ai_modes.update_mode(mode, accent_hex=val):
                        self._show_error("")
                        self._refresh_row(mode)
                        try:
                            self.app._system_note(f"{mode} colour → {val}")
                        except Exception:
                            pass
                except Exception as e:
                    self._show_error(str(e))
            elif iid.startswith("mcc-new"):
                try:
                    self.on_button_pressed(type("E", (), {"button": type("B", (), {"id": "mcc-create-btn"})(), "stop": lambda: None})())
                except Exception:
                    pass

        def action_cancel(self):
            self.dismiss(None)

        def on_key(self, event):
            if event.key == "escape":
                self.dismiss(None)

    ModeColorsPanel_OLD = ModeColorsPanel

else:
    ModeColorsPanel = None
    _ModeRow = None
