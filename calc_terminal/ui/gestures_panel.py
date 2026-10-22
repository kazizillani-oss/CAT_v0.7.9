"""
CAT UI — gestures_panel.py: Gesture Manager (spec section 23).

Responsive: uses percentage widths, auto height, scroll, and stacked
fallbacks for narrow terminals. Buttons use consistent sizing and
plain-text labels (no emoji-width mismatches). Layout never clips.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

from ..gestures.bindings import GESTURE_TRIGGERS, GESTURE_TARGETS, GESTURE_ACTIONS
from ..gestures.manager import list_gestures, add_gesture, delete_gesture, toggle_gesture, reset_defaults

TEXTUAL_AVAILABLE = True
try:
    from textual.containers import Vertical, Horizontal, VerticalScroll
    from textual.screen import Screen
    from textual.widgets import Static, Button, Input, Select
    from textual.binding import Binding
except Exception:
    TEXTUAL_AVAILABLE = False


if TEXTUAL_AVAILABLE:

    class _GestureRow(Horizontal):
        def __init__(self, gesture):
            super().__init__(classes="cct-gesture-row")
            self.gesture = gesture

        def compose(self):
            g = self.gesture
            enabled = g.get("enabled", True)
            name = g.get("name","")
            trg = g.get("trigger","")
            tgt = g.get("target","")
            act = g.get("action","")
            keys = g.get("keys","")
            detail = f"{keys} ({tgt}) -> {act}" if trg == "shortcut" and keys else f"{trg} on {tgt}  ->  {act}"
            # Left: name + detail stacked, so narrow terminals don't clip
            with Vertical(classes="cct-gesture-left"):
                if enabled:
                    yield Static(f"[b]{name}[/]", classes="cct-gesture-name")
                else:
                    yield Static(f"[dim]{name} (disabled)[/]", classes="cct-gesture-name")
                yield Static(detail, classes="cct-gesture-detail")
            # Right: actions - fixed width group that stays visible
            with Horizontal(classes="cct-gesture-actions"):
                label = "Disable" if enabled else "Enable"
                yield Button(label, id=f"gesture-toggle-{g.get('id')}", classes="cct-btn cct-btn-sm")
                yield Button("Delete", id=f"gesture-del-{g.get('id')}", variant="error", classes="cct-btn cct-btn-sm")

        def on_button_pressed(self, event):
            event.stop()
            gid = self.gesture.get("id")
            if event.button.id == f"gesture-toggle-{gid}":
                toggle_gesture(gid)
                for scr in self.app.screen_stack:
                    if isinstance(scr, GesturesPanel):
                        scr.refresh_gestures()
                        break
            elif event.button.id == f"gesture-del-{gid}":
                delete_gesture(gid)
                for scr in self.app.screen_stack:
                    if isinstance(scr, GesturesPanel):
                        scr.refresh_gestures()
                        break


    class GesturesPanel(Screen):
        """Gesture Manager — responsive CAT-style manager panel."""

        CSS = """
        GesturesPanel { align: center middle; background: $app-background 60%; }

        #gestures-box {
            width: 84; height: auto; max-height: 42;
            background: $surface; border: round $border;
            padding: 0; overflow: hidden;
            layout: vertical;
        }
        #gestures-titlebar {
            height: 3; min-height: 3;
            padding: 1 2 0 2; border-bottom: solid $border;
            layout: horizontal;
        }
        #gestures-title { width: 1fr; text-style: bold; }
        #gestures-subtitle { color: $text-faint; height: auto; padding: 0 2 1 2; }
        #gestures-disabled { height: auto; padding: 2 2; align: center middle; }
        .gestures-disabled-msg { color: $warning; text-style: bold; height: auto; text-align: center; padding-bottom: 1; }

        #gestures-count {
            height: 1; color: $text-faint;
            padding: 0 2; margin-bottom: 1;
        }

        #gestures-list {
            height: 1fr; min-height: 8; max-height: 20;
            overflow-y: auto; overflow-x: hidden;
            margin: 0 1; padding: 0 0;
            scrollbar-gutter: stable; scrollbar-size: 1 1;
            scrollbar-color: $border $surface;
            scrollbar-color-hover: $accent $surface;
        }
        #gestures-empty {
            color: $text-faint; padding: 2 1; text-align: center; height: auto;
        }

        .cct-gesture-row {
            height: auto; min-height: 4;
            padding: 1 1;
            border-bottom: solid $border;
            border-left: thick transparent;
            layout: horizontal;
            overflow: hidden;
        }
        .cct-gesture-row:hover {
            border-left: thick $accent;
            background: $surface-alt 40%;
        }
        .cct-gesture-left { width: 1fr; height: auto; min-width: 12; }
        .cct-gesture-name { width: auto; height: 1; }
        .cct-gesture-detail { width: auto; height: 1; color: $text-muted; }
        .cct-gesture-actions {
            width: auto; height: auto; min-width: 20;
            layout: horizontal; align: center middle;
        }
        .cct-gesture-actions Button { margin-left: 1; min-width: 10; height: 3; }

        /* Compact: stack left+actions vertically on very narrow terminals */
        .cct-compact .cct-gesture-row { layout: vertical; min-height: 6; }
        .cct-compact .cct-gesture-actions { width: 100%; padding-top: 1; }

        /* Form — responsive: rows become vertical on narrow */
        #gestures-form {
            height: auto; padding: 1 2;
            border-top: solid $border; background: $app-background 35%;
        }
        #gestures-form-title { height: 1; text-style: bold; color: $accent; padding-bottom: 1; }
        #gestures-form-row1 { height: 3; margin-bottom: 1; }
        #gestures-form-row1 Input { width: 1fr; }
        #gestures-form-row2 {
            height: auto; min-height: 3;
            layout: horizontal; overflow-x: auto;
            scrollbar-size: 1 1; scrollbar-gutter: stable;
        }
        #gestures-form-row2 Select { width: 1fr; min-width: 14; margin-right: 1; margin-bottom: 1; }
        #gestures-form-row2 Button { min-width: 12; height: 3; }

        #gestures-form-row3 {
            height: 3; margin-top: 1; layout: horizontal;
            display: none;
        }
        #gestures-form-row3.show { display: block; }
        #gestures-form-row3 Input { width: 1fr; }
        #gestures-shortcut-hint { color: $text-faint; height: 1; padding: 0 2; display: none; }
        #gestures-shortcut-hint.show { display: block; }

        .cct-compact #gestures-form-row2 { layout: vertical; }
        .cct-compact #gestures-form-row2 Select { width: 100%; margin-right: 0; }

        #gestures-actions {
            height: auto; min-height: 3; padding: 1 2;
            layout: horizontal; overflow-x: auto;
            scrollbar-size: 1 1; scrollbar-gutter: stable;
            border-top: solid $border;
        }
        #gestures-actions Button { margin-right: 1; margin-bottom: 1; min-width: 16; }

        #gestures-hint {
            height: auto; min-height: 2;
            color: $text-faint; padding: 1 2;
            text-align: center;
            border-top: solid $border;
        }

        .cct-compact #gestures-box { width: 96; height: auto; }
        """

        BINDINGS = [Binding("escape", "cancel", "Cancel")]

        def __init__(self):
            super().__init__()

        def compose(self):
            # Extension guard: if Gestures is disabled/uninstalled, show disabled state
            try:
                from .. import extensions as _ext
                if not _ext.is_enabled("gestures"):
                    with Vertical(id="gestures-box"):
                        with Horizontal(id="gestures-titlebar"):
                            yield Static("Gestures & Shortcuts", id="gestures-title")
                            yield Button("✕", id="gestures-close", classes="cct-ctrl")
                        yield Static("Gestures is disabled — enable it in Extensions to use gestures and shortcuts.", id="gestures-subtitle")
                        with Vertical(id="gestures-disabled"):
                            yield Static("🔌 Gestures is currently disabled.", classes="gestures-disabled-msg")
                            yield Button("Open Extensions", id="gestures-open-ext", variant="primary")
                            yield Button("Close", id="gestures-close2")
                    return
            except Exception:
                pass
            with Vertical(id="gestures-box"):
                with Horizontal(id="gestures-titlebar"):
                    yield Static("Gestures & Shortcuts", id="gestures-title")
                    yield Button("X", id="gestures-close", classes="cct-ctrl")
                # v0.7.9.10 fix: Gestures is independent of MCP — never show
                # "MCP server down" here. This panel manages only gestures/
                # shortcuts (see gestures/manager.py), while MCP servers
                # live exclusively in McpServersPanel (calc_terminal/mcp.py).
                yield Static("Gestures: double-click/long-press/swipe. Shortcuts: custom key combos -> actions. (Independent of MCP servers)", id="gestures-subtitle")
                yield Static("", id="gestures-count")
                with VerticalScroll(id="gestures-list"):
                    pass
                with Vertical(id="gestures-form"):
                    yield Static("Add new gesture / shortcut", id="gestures-form-title")
                    with Horizontal(id="gestures-form-row1"):
                        yield Input(placeholder="Name  (e.g. Shift+Enter -> Preview)", id="gestures-name")
                    with Horizontal(id="gestures-form-row2"):
                        yield Select([(t, t) for t in GESTURE_TRIGGERS], prompt="Trigger", id="gestures-trigger", value=GESTURE_TRIGGERS[0])
                        yield Select([(t, t) for t in GESTURE_TARGETS], prompt="Target", id="gestures-target", value=GESTURE_TARGETS[0])
                        yield Select([(a, a) for a in GESTURE_ACTIONS], prompt="Action", id="gestures-action", value=GESTURE_ACTIONS[0])
                        yield Button("Add", id="gestures-add", variant="primary", classes="cct-btn-sm")
                    with Horizontal(id="gestures-form-row3"):
                        yield Input(placeholder="Shortcut keys (e.g. shift+enter, ctrl+s, ctrl+shift+p)", id="gestures-keys")
                    yield Static("Hint: shift+enter, ctrl+s, ctrl+shift+p, f5, alt+enter ...", id="gestures-shortcut-hint")
                with Horizontal(id="gestures-actions"):
                    yield Button("Reset Defaults", id="gestures-reset", classes="cct-btn-sm")
                    yield Button("Close", id="gestures-close2", variant="primary", classes="cct-btn-sm")
                yield Static("Double-click editor -> VS Code  ·  preview -> fullscreen  ·  shortcut: shift+enter -> preview", id="gestures-hint")

        def on_mount(self):
            self.call_after_refresh(lambda: self.query_one("#gestures-box").add_class("open") if self.query_one("#gestures-box").has_class("open") is False else None)
            try:
                self.query_one("#gestures-box").add_class("open")
            except Exception:
                pass
            self.call_after_refresh(self.refresh_gestures)
            self._update_shortcut_row()
            try:
                if self.size.width < 76 or self.size.height < 30:
                    self.query_one("#gestures-box").add_class("cct-compact")
            except Exception:
                pass
            try:
                self.query_one("#gestures-name", Input).focus()
            except Exception:
                pass

        def _update_shortcut_row(self):
            try:
                trg = self.query_one("#gestures-trigger", Select).value
                show = (trg == "shortcut")
                row = self.query_one("#gestures-form-row3", Horizontal)
                hint = self.query_one("#gestures-shortcut-hint", Static)
                if show:
                    row.add_class("show")
                    hint.add_class("show")
                else:
                    row.remove_class("show")
                    hint.remove_class("show")
            except Exception:
                pass

        def on_select_changed(self, event):
            # show/hide shortcut keys input when trigger changes
            if getattr(event.select, "id", "") == "gestures-trigger":
                self._update_shortcut_row()

        def refresh_gestures(self):
            try:
                container = self.query_one("#gestures-list", VerticalScroll)
                count_label = self.query_one("#gestures-count", Static)
            except Exception:
                return
            try:
                container.remove_children()
            except Exception:
                pass
            gestures = list_gestures()
            enabled = sum(1 for g in gestures if g.get("enabled"))
            try:
                count_label.update(f"{len(gestures)} gestures  ·  {enabled} enabled")
            except Exception:
                pass
            if not gestures:
                try:
                    container.mount(Static("No gestures yet.\nAdd one below or reset to defaults.", id="gestures-empty"))
                except Exception:
                    pass
                return
            for g in gestures:
                try:
                    container.mount(_GestureRow(g))
                except Exception:
                    pass

        def on_button_pressed(self, event):
            bid = event.button.id
            if bid == "gestures-open-ext":
                try:
                    self.dismiss(None)
                    from .extensions_panel import ExtensionsPanel
                    self.app.push_screen(ExtensionsPanel())
                except Exception:
                    self.dismiss(None)
                return
            if bid in ("gestures-close", "gestures-close2"):
                self.dismiss(None)
            elif bid == "gestures-reset":
                reset_defaults()
                self.refresh_gestures()
                try:
                    self.app._system_note("Gestures reset to defaults")
                except Exception:
                    pass
            elif bid == "gestures-add":
                try:
                    name = self.query_one("#gestures-name", Input).value.strip() or "Custom gesture"
                    try:
                        trigger = self.query_one("#gestures-trigger", Select).value
                    except Exception:
                        trigger = None
                    try:
                        target = self.query_one("#gestures-target", Select).value
                    except Exception:
                        target = None
                    try:
                        action = self.query_one("#gestures-action", Select).value
                    except Exception:
                        action = None
                    try:
                        keys = self.query_one("#gestures-keys", Input).value.strip().lower() if trigger == "shortcut" else ""
                    except Exception:
                        keys = ""
                    if not trigger or trigger not in GESTURE_TRIGGERS:
                        trigger = GESTURE_TRIGGERS[0]
                    if not target or target not in GESTURE_TARGETS:
                        target = GESTURE_TARGETS[0]
                    if not action or action not in GESTURE_ACTIONS:
                        action = GESTURE_ACTIONS[0]
                    # shortcut needs keys
                    if trigger == "shortcut":
                        if not keys:
                            try:
                                self.app._system_note("Enter shortcut keys (e.g. shift+enter, ctrl+s)")
                            except Exception:
                                pass
                            return
                    result = add_gesture(name, trigger, target, action, keys=keys)
                    if result:
                        self.refresh_gestures()
                        try:
                            self.query_one("#gestures-name", Input).value = ""
                            self.query_one("#gestures-keys", Input).value = ""
                        except Exception:
                            pass
                        try:
                            self.app._system_note(f"Added {'shortcut' if trigger=='shortcut' else 'gesture'}: {name}")
                        except Exception:
                            pass
                    else:
                        try:
                            self.app._system_note("Could not add — check values (duplicate shortcut or invalid keys)")
                        except Exception:
                            pass
                except Exception as e:
                    try:
                        self.app._system_note(f"Could not add gesture: {e}")
                    except Exception:
                        pass

        def action_cancel(self):
            self.dismiss(None)

        def on_key(self, event):
            if event.key == "escape":
                self.dismiss(None)

else:
    GesturesPanel = None
