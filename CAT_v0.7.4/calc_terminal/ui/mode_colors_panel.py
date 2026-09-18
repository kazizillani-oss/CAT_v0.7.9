"""
CCT UI — ModeColorsPanel / ModesManager (v0.7.9.8).

User Section > Modes: fully customizable AI modes — change colour (gradient
auto), edit label/icon/purpose, create new modes, delete modes, reorder,
reset. Persists to ~/.cct_config.json via ai_modes.* and instantly repaints.

Design: responsive, easy to use, not in main menu (only User section).
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

import re

TEXTUAL_AVAILABLE = True
try:
    from textual.screen import Screen
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
        "#7aa2f7", "#bb9af7", "#e0af68", "#9ece6a", "#ff69b4", "#dc143c",
        "#ff7f50", "#40e0d0", "#ffd700", "#8a2be2", "#00fa9a", "#ff6347",
        "#1e90ff", "#ff1493", "#32cd32", "#ffa500",
    ]

    def _valid_hex(s):
        return bool(_HEX_RE.match((s or "").strip()))

    def _valid_key(k):
        return bool(_KEY_RE.match((k or "").strip().lower()))

    class _ModeRow(Horizontal):
        """One mode's full editor row (colour + label/icon/purpose + actions)."""
        def __init__(self, mode_key):
            super().__init__(classes="mcc-row", id=f"mcc-row-{mode_key}")
            self.mode_key = mode_key

        def compose(self):
            m = ai_modes.MODE_META.get(self.mode_key, {})
            label = m.get("label", self.mode_key)
            icon = m.get("icon", "")
            purpose = m.get("purpose", "")[:80]
            accent = ai_modes.accent_hex(self.mode_key)
            g_start, g_end = ai_modes.gradient(self.mode_key)
            is_current = (self.mode_key == ai_modes.current_mode())
            cur_mark = "●" if is_current else "○"
            # left: info + editable fields
            with Vertical(classes="mcc-info"):
                # header: current marker + icon + label (editable)
                with Horizontal(classes="mcc-header"):
                    yield Static(f"[{accent}]{cur_mark}[/] {icon} {label}", classes="mcc-label", markup=True)
                    yield Static(f"[{accent}]{self.mode_key}[/]", classes="mcc-key", markup=True)
                yield Static(purpose or "No purpose", classes="mcc-purpose")
                yield Static(f"[{accent}]█[/] {accent}  grad [{g_start}]█[/][{g_end}]█[/] {g_start}→{g_end}", classes="mcc-preview", markup=True)
                # inline edit fields (collapsed by default, shown on Edit)
                with Vertical(classes="mcc-editbox", id=f"mcc-edit-{self.mode_key}"):
                    with Horizontal(classes="mcc-edit-row"):
                        yield Input(value=label, placeholder="Label", id=f"mcc-label-{self.mode_key}", classes="mcc-input-sm")
                        yield Input(value=icon, placeholder="Icon", id=f"mcc-icon-{self.mode_key}", classes="mcc-input-sm mcc-input-icon")
                        yield Input(value=accent, placeholder="#rrggbb", id=f"mcc-input-{self.mode_key}", classes="mcc-input")
                    yield Input(value=purpose, placeholder="Purpose (one-line)", id=f"mcc-purpose-{self.mode_key}", classes="mcc-input-wide")
            # right: actions
            with Vertical(classes="mcc-actions"):
                with Horizontal(classes="mcc-actions-row"):
                    yield Button("Save", id=f"mcc-save-{self.mode_key}", variant="primary", classes="cct-btn-sm")
                    yield Button("Delete", id=f"mcc-delete-{self.mode_key}", variant="error", classes="cct-btn-sm")
                with Horizontal(classes="mcc-actions-row"):
                    yield Button("↑", id=f"mcc-up-{self.mode_key}", classes="cct-btn-sm")
                    yield Button("↓", id=f"mcc-down-{self.mode_key}", classes="cct-btn-sm")
                    yield Button("Reset", id=f"mcc-reset-{self.mode_key}", classes="cct-btn-sm")

        def refresh_preview(self):
            try:
                m = ai_modes.MODE_META.get(self.mode_key, {})
                label = m.get("label", self.mode_key)
                icon = m.get("icon", "")
                purpose = m.get("purpose", "")[:80]
                accent = ai_modes.accent_hex(self.mode_key)
                g_start, g_end = ai_modes.gradient(self.mode_key)
                is_current = (self.mode_key == ai_modes.current_mode())
                cur_mark = "●" if is_current else "○"
                self.query_one(".mcc-label", Static).update(f"[{accent}]{cur_mark}[/] {icon} {label}")
                self.query_one(".mcc-key", Static).update(f"[{accent}]{self.mode_key}[/]")
                self.query_one(".mcc-purpose", Static).update(purpose or "No purpose")
                self.query_one(".mcc-preview", Static).update(f"[{accent}]█[/] {accent}  grad [{g_start}]█[/][{g_end}]█[/] {g_start}→{g_end}")
                # update inputs to reflect new values (keep user edits if focused? just update)
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
            except Exception:
                pass

    # Alias for backward compat (old name)
    _ModeColorRow = _ModeRow

    class ModeColorsPanel(Screen):
        """Modes manager — User Section only (not main menu). Full CRUD."""

        CSS = """
        ModeColorsPanel { align: center middle; background: $app-background 60%; }
        #mcc-box {
            width: 96; max-width: 98%; height: auto; max-height: 46;
            background: $surface; border: round $border;
            padding: 0; layout: vertical; overflow: hidden;
        }
        #mcc-titlebar {
            height: 3; min-height: 3; padding: 1 2 0 2;
            border-bottom: solid $border; layout: horizontal;
        }
        #mcc-title { width: 1fr; text-style: bold; }
        #mcc-subtitle { color: $text-faint; height: auto; padding: 0 2 1 2; }
        #mcc-presets {
            height: auto; padding: 0 2 1 2; layout: horizontal;
            border-bottom: solid $border;
        }
        #mcc-presets-label { width: auto; color: $text-faint; height: 1; padding-right: 1; }
        .mcc-preset {
            width: 3; min-width: 3; height: 1; min-height: 1; padding: 0;
            margin-right: 1; border: none; content-align: center middle;
        }
        #mcc-create {
            height: auto; padding: 1 2; border-bottom: solid $border; background: $surface-alt 20%;
        }
        #mcc-create-title { height: 1; text-style: bold; color: $accent; }
        #mcc-create-row1 { height: 3; layout: horizontal; margin-top: 1; }
        #mcc-create-row1 Input { width: 1fr; margin-right: 1; }
        #mcc-create-row2 { height: 3; layout: horizontal; margin-top: 1; }
        #mcc-create-row2 Input { width: 1fr; margin-right: 1; }
        #mcc-create-row3 { height: 3; layout: horizontal; margin-top: 1; }
        #mcc-create-row3 Input { width: 1fr; }
        #mcc-create-actions { height: 3; layout: horizontal; margin-top: 1; }
        #mcc-create-actions Button { margin-right: 1; }
        #mcc-list {
            height: 1fr; min-height: 10; max-height: 22;
            overflow-y: auto; overflow-x: hidden;
            scrollbar-gutter: stable; scrollbar-size: 1 1;
            margin: 0 1; padding: 0;
        }
        .mcc-row {
            height: auto; min-height: 7; padding: 1 1;
            border-bottom: solid $border; border-left: thick transparent;
            layout: horizontal; overflow: hidden;
        }
        .mcc-row:hover { border-left: thick $accent; background: $surface-alt 30%; }
        .mcc-info { width: 1fr; height: auto; min-width: 24; }
        .mcc-header { height: 1; layout: horizontal; }
        .mcc-label { width: auto; height: 1; text-style: bold; margin-right: 1; }
        .mcc-key { width: auto; height: 1; color: $text-faint; }
        .mcc-purpose { width: auto; height: 1; color: $text-faint; }
        .mcc-preview { width: auto; height: 1; color: $text-muted; }
        .mcc-editbox { height: auto; margin-top: 1; display: none; }
        .mcc-editbox.show { display: block; }
        .mcc-edit-row { height: 3; layout: horizontal; margin-bottom: 1; }
        .mcc-input-sm { width: 1fr; margin-right: 1; }
        .mcc-input-icon { width: 10; min-width: 10; }
        .mcc-input { width: 16; min-width: 16; height: 3; margin-right: 1; }
        .mcc-input-wide { width: 100%; height: 3; }
        .mcc-actions {
            width: auto; height: auto; min-width: 24;
            layout: vertical; align: center middle;
        }
        .mcc-actions-row { height: 3; layout: horizontal; margin-bottom: 1; }
        .mcc-actions-row Button { min-width: 10; height: 3; margin-right: 1; }
        #mcc-actions {
            height: auto; padding: 1 2; border-top: solid $border;
            layout: horizontal;
        }
        #mcc-actions-left { width: 1fr; layout: horizontal; }
        #mcc-actions-left Button { margin-right: 1; }
        #mcc-actions-right { width: auto; layout: horizontal; }
        #mcc-actions-right Button { margin-left: 1; }
        #mcc-hint { color: $text-faint; height: auto; padding: 0 2 1 2; text-align: center; }
        #mcc-error { color: $error; height: 1; padding: 0 2; display: none; }
        #mcc-error.show { display: block; }
        .cct-compact .mcc-row { layout: vertical; min-height: 10; }
        .cct-compact .mcc-actions { width: 100%; padding-top: 1; }
        .cct-compact #mcc-box { width: 98; }
        .cct-compact #mcc-create-row1 { layout: vertical; height: auto; }
        .cct-compact #mcc-create-row1 Input { width: 100%; margin-bottom: 1; }
        .cct-compact #mcc-create-row2 { layout: vertical; height: auto; }
        .cct-compact #mcc-create-row2 Input { width: 100%; margin-bottom: 1; }
        """

        BINDINGS = [Binding("escape", "cancel", "Cancel")]

        def compose(self):
            with Vertical(id="mcc-box"):
                with Horizontal(id="mcc-titlebar"):
                    yield Static("🎨  AI Modes — Manage", id="mcc-title")
                    yield Button("✕", id="mcc-close", classes="cct-ctrl")
                yield Static("Create, edit, reorder, delete modes — colours auto-gradient. Only in User section.", id="mcc-subtitle")
                with Horizontal(id="mcc-presets"):
                    yield Static("Presets:", id="mcc-presets-label")
                    for idx, hx in enumerate(_PRESETS):
                        btn = Button("█", id=f"mcc-preset-{idx}", classes="mcc-preset")
                        btn.tooltip = hx
                        btn._preset_hex = hx
                        yield btn
                # create form
                with Vertical(id="mcc-create"):
                    yield Static("＋ Create New Mode", id="mcc-create-title")
                    with Horizontal(id="mcc-create-row1"):
                        yield Input(placeholder="key (a-z0-9_, 2-20)", id="mcc-new-key", classes="mcc-input-sm")
                        yield Input(placeholder="Label", id="mcc-new-label", classes="mcc-input-sm")
                        yield Input(placeholder="Icon", id="mcc-new-icon", classes="mcc-input-sm mcc-input-icon")
                        yield Input(placeholder="#rrggbb", id="mcc-new-color", classes="mcc-input")
                    with Horizontal(id="mcc-create-row2"):
                        yield Input(placeholder="Purpose (one-line)", id="mcc-new-purpose", classes="mcc-input-sm")
                    with Horizontal(id="mcc-create-actions"):
                        yield Button("Create", id="mcc-create-btn", variant="primary", classes="cct-btn-sm")
                        yield Button("Clear", id="mcc-create-clear", classes="cct-btn-sm")
                yield Static("", id="mcc-error")
                with VerticalScroll(id="mcc-list"):
                    for key in list(ai_modes.MODE_ORDER):
                        yield _ModeRow(key)
                with Horizontal(id="mcc-actions"):
                    with Horizontal(id="mcc-actions-left"):
                        yield Button("↺ Reset All to Defaults", id="mcc-reset-all", classes="cct-btn-sm")
                    with Horizontal(id="mcc-actions-right"):
                        yield Button("Close", id="mcc-close2", variant="primary", classes="cct-btn-sm")
                yield Static("Tip: Edit label/icon/purpose/colour then Save. ↑↓ to reorder. Delete removes mode (min 1).", id="mcc-hint")

        def on_mount(self):
            try:
                self.query_one("#mcc-box").add_class("open")
            except Exception:
                pass
            try:
                for idx, hx in enumerate(_PRESETS):
                    btn = self.query_one(f"#mcc-preset-{idx}", Button)
                    btn.label = f"[{hx}]█[/]"
            except Exception:
                pass
            if self.size.width < 90 or self.size.height < 34:
                try:
                    self.query_one("#mcc-box").add_class("cct-compact")
                except Exception:
                    pass
            try:
                self.query_one("#mcc-new-key", Input).focus()
            except Exception:
                pass

        def _show_error(self, msg=""):
            try:
                lbl = self.query_one("#mcc-error", Static)
                if msg:
                    lbl.update(msg)
                    lbl.add_class("show")
                else:
                    lbl.remove_class("show")
            except Exception:
                pass

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
            # rebuild list from current MODE_ORDER
            try:
                container = self.query_one("#mcc-list", VerticalScroll)
                container.remove_children()
                for key in list(ai_modes.MODE_ORDER):
                    container.mount(_ModeRow(key))
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
            if bid.startswith("mcc-preset-"):
                try:
                    hx = getattr(event.button, "_preset_hex", None) or _PRESETS[int(bid.split("-")[-1])]
                    # paste into focused color input or new-color
                    focused = None
                    for k in list(ai_modes.MODE_ORDER):
                        try:
                            inp = self.query_one(f"#mcc-input-{k}", Input)
                            if inp.has_focus:
                                focused = inp
                                break
                        except Exception:
                            pass
                    if focused is None:
                        try:
                            new_inp = self.query_one("#mcc-new-color", Input)
                            if new_inp.has_focus or not focused:
                                focused = new_inp
                        except Exception:
                            pass
                    if focused is None:
                        cur = ai_modes.current_mode()
                        try:
                            focused = self.query_one(f"#mcc-input-{cur}", Input)
                        except Exception:
                            focused = self.query_one("#mcc-new-color", Input)
                    focused.value = hx
                    focused.focus()
                    self._show_error("")
                except Exception:
                    pass
                return
            if bid in ("mcc-close", "mcc-close2"):
                self.dismiss(None)
                return
            if bid == "mcc-reset-all":
                ai_modes.reset_all_modes()
                self._refresh_list()
                try:
                    self.app._system_note("All modes reset to defaults")
                except Exception:
                    pass
                self._show_error("")
                return
            if bid == "mcc-create-clear":
                for iid in ["#mcc-new-key", "#mcc-new-label", "#mcc-new-icon", "#mcc-new-color", "#mcc-new-purpose"]:
                    try:
                        self.query_one(iid, Input).value = ""
                    except Exception:
                        pass
                self._show_error("")
                return
            if bid == "mcc-create-btn":
                try:
                    key = self.query_one("#mcc-new-key", Input).value.strip().lower()
                    label = self.query_one("#mcc-new-label", Input).value.strip()
                    icon = self.query_one("#mcc-new-icon", Input).value.strip()
                    color = self.query_one("#mcc-new-color", Input).value.strip()
                    purpose = self.query_one("#mcc-new-purpose", Input).value.strip()
                    if not _valid_key(key):
                        self._show_error("Key: 2-20 chars a-z0-9_")
                        return
                    if not _valid_hex(color):
                        self._show_error(f"Invalid hex '{color}'")
                        return
                    ok, msg = ai_modes.create_mode(key, label or key.title(), icon or "●", color, purpose)
                    if ok:
                        self._show_error("")
                        self._refresh_list()
                        # clear create form
                        for iid in ["#mcc-new-key", "#mcc-new-label", "#mcc-new-icon", "#mcc-new-color", "#mcc-new-purpose"]:
                            try:
                                self.query_one(iid, Input).value = ""
                            except Exception:
                                pass
                        try:
                            self.app._system_note(f"Mode '{key}' created")
                        except Exception:
                            pass
                    else:
                        self._show_error(msg)
                except Exception as e:
                    self._show_error(str(e))
                return
            if bid.startswith("mcc-save-"):
                mode = bid.replace("mcc-save-", "")
                try:
                    label = self.query_one(f"#mcc-label-{mode}", Input).value.strip()
                    icon = self.query_one(f"#mcc-icon-{mode}", Input).value.strip()
                    color = self.query_one(f"#mcc-input-{mode}", Input).value.strip()
                    purpose = self.query_one(f"#mcc-purpose-{mode}", Input).value.strip()
                    if color and not _valid_hex(color):
                        self._show_error(f"Invalid hex for {mode}: '{color}'")
                        return
                    # update each field if provided
                    ok = True
                    if label or icon or purpose or color:
                        # use update_mode with provided values; if blank keep old
                        ok = ai_modes.update_mode(mode,
                            label=label if label else None,
                            icon=icon if icon else None,
                            accent_hex=color if color and _valid_hex(color) else None,
                            purpose=purpose if purpose else None)
                    if ok:
                        self._show_error("")
                        self._refresh_row(mode)
                        try:
                            self.app._system_note(f"{mode} saved")
                        except Exception:
                            pass
                    else:
                        self._show_error(f"Could not save {mode}")
                except Exception as e:
                    self._show_error(str(e))
                return
            if bid.startswith("mcc-delete-"):
                mode = bid.replace("mcc-delete-", "")
                ok, msg = ai_modes.delete_mode(mode)
                if ok:
                    self._show_error("")
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
                    self._show_error("")
                else:
                    self._show_error("Already at top")
                return
            if bid.startswith("mcc-down-"):
                mode = bid.replace("mcc-down-", "")
                if ai_modes.move_mode(mode, 1):
                    self._refresh_list()
                    self._show_error("")
                else:
                    self._show_error("Already at bottom")
                return
            if bid.startswith("mcc-reset-"):
                # careful: mcc-reset-all handled above, this is per-mode reset (only for built-ins)
                mode = bid.replace("mcc-reset-", "")
                if mode == "all":
                    return
                if ai_modes.reset_mode_color(mode):
                    self._refresh_row(mode)
                    try:
                        self.app._system_note(f"{mode} colour reset")
                    except Exception:
                        pass
                    self._show_error("")
                else:
                    # try full reset for custom modes? delete and recreate as default if was built-in?
                    self._show_error(f"Cannot reset '{mode}' (custom mode — delete to remove)")
                return
            if bid.startswith("mcc-preset"):
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
            elif iid == "mcc-new-color" or iid.startswith("mcc-new-"):
                # enter in create form triggers create
                try:
                    # simulate create btn
                    self.on_button_pressed(type("E", (), {"button": type("B", (), {"id": "mcc-create-btn"})(), "stop": lambda: None})())
                except Exception:
                    pass

        def action_cancel(self):
            self.dismiss(None)

        def on_key(self, event):
            if event.key == "escape":
                self.dismiss(None)

    # Keep old name alias for any external import
    ModeColorsPanel_OLD = ModeColorsPanel

else:
    ModeColorsPanel = None
    _ModeRow = None
