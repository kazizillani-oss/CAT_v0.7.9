"""
CCT UI — the single permission renderer. Two widgets, both reading and
writing through calc_terminal/permissions.py's shared PermissionManager
(the one source of truth for permission state — this module never
tracks its own copy):

  * PermissionCard — an inline "AI wants permission" request, mounted
    as a ConversationItem in the conversation stream (per the redesign
    brief: "Permission requests become part of conversation history",
    never a modal/popup).
  * PermissionsSettingsPanel — the full on/off checklist, opened from
    the footer's Permissions button.

Both post events (PermissionGranted/PermissionDenied/PermissionCancelled)
rather than deciding what a decision means — calc_terminal/permissions.py
records it, calc_terminal/ui/app.py resolves whatever backend call was
waiting.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

from .. import permissions as perm
from .events import PermissionGranted, PermissionDenied, PermissionCancelled

TEXTUAL_AVAILABLE = True
try:
    from textual.containers import Horizontal, Vertical
    from textual.widgets import Static, Button, Switch, Label
except Exception:
    TEXTUAL_AVAILABLE = False


if TEXTUAL_AVAILABLE:

    class PermissionCard(Vertical):
        """Inline 'AI wants permission' request — mounted into the
        conversation log as its own item, never a popup."""

        def __init__(self, request_id, key, action_text, reason_text, id=None, path=None):
            super().__init__(id=id, classes="cct-permcard")
            self.request_id = request_id
            self.key = key
            self._action_text = action_text
            self._reason_text = reason_text
            self._path = path
            self._resolved = False

        def compose(self):
            # Restricted mode (spec Mode 2) reviews this as a suggested
            # patch — Accept/Reject — instead of Ask mode's (spec Mode 1)
            # Allow-Once/Always-Allow/Deny. Same request, same event
            # contract either way; only the labels/verb change.
            self._restricted = perm.manager.restricted_review(self.key)
            title = "Suggested action \u2014 review required" if self._restricted else "Permission required"
            yield Static(title, classes="cct-permcard-title")
            yield Static(f"The AI wants to [b]{self._action_text}[/b]")
            if self._path:
                yield Static(f"Path: {self._path}", classes="cct-permcard-path")
            yield Static(f"Reason: {self._reason_text}", classes="cct-permcard-reason")
            with Horizontal(classes="cct-permcard-buttons"):
                if self._restricted:
                    yield Button("Accept", id="allow-once", classes="cct-ctrl")
                    yield Button("Reject", id="deny", classes="cct-ctrl")
                else:
                    # v0.7.7 spec section 3: the dialog offers five
                    # choices — Allow Once / Always Allow / Deny /
                    # Always Deny / Cancel (wrapped on a second row so
                    # the card stays compact).
                    yield Button("Allow Once", id="allow-once", classes="cct-ctrl")
                    yield Button("Always Allow", id="always-allow", classes="cct-ctrl")
                    yield Button("Deny", id="deny", classes="cct-ctrl")
            if not self._restricted:
                with Horizontal(classes="cct-permcard-buttons"):
                    yield Button("Always Deny", id="always-deny", classes="cct-ctrl")
                    yield Button("Cancel", id="cancel", classes="cct-ctrl")

        def on_button_pressed(self, event: Button.Pressed):
            if self._resolved:
                return
            self._resolved = True
            bid = event.button.id
            for b in self.query(Button):
                b.disabled = True
            from . import theme_css
            if bid == "always-allow":
                self.post_message(PermissionGranted(self.request_id, self.key, remember=True))
                tone = "success"
                verb = "always allow"
            elif bid == "allow-once":
                self.post_message(PermissionGranted(self.request_id, self.key, remember=False))
                tone = "success"
                verb = "accept" if getattr(self, "_restricted", False) else "allow once"
            elif bid == "always-deny":
                # v0.7.7: permanent (session) refusal — recorded in the
                # shared PermissionManager so future requests for this
                # key are refused without prompting at all.
                self.post_message(PermissionDenied(self.request_id, self.key, remember=True))
                tone = "error"
                verb = "always deny"
            elif bid == "cancel":
                self.post_message(PermissionCancelled(self.request_id, self.key))
                tone = "warn"
                verb = "cancel"
            else:
                self.post_message(PermissionDenied(self.request_id, self.key, remember=False))
                tone = "error"
                verb = "reject" if getattr(self, "_restricted", False) else "deny"
            color = theme_css.current_hex(tone)
            self.mount(Static(f"[{color}]\u2192 {verb}[/]", classes="cct-permcard-verdict"))

    class Toggle3D(Button):
        """Skeuomorphic 3D On/Off tactile slider switch with physical rail,
        depression animation, and glowing state indicator."""

        def __init__(self, key, is_on=False, on_toggle=None):
            self._key = key
            self.is_on = is_on
            self._on_toggle = on_toggle
            super().__init__(
                self._format_label(is_on),
                id=f"perm-toggle-{key}",
                classes="cct-toggle-3d " + ("-on" if is_on else "-off"),
            )
            self.can_focus = True

        @staticmethod
        def _format_label(is_on: bool) -> str:
            # Tactile physical slider switch with 3D track and knob
            return "[──● ON ]" if is_on else "[○── OFF]"

        @property
        def is_enabled(self) -> bool:
            return self.is_on

        def on_button_pressed(self, event: Button.Pressed):
            event.stop()
            self.is_on = not self.is_on
            self.set_class(self.is_on, "-on")
            self.set_class(not self.is_on, "-off")
            self.label = self._format_label(self.is_on)
            perm.manager.set(self._key, self.is_on)
            if self._on_toggle:
                self._on_toggle(self._key, self.is_on)

    class PermissionRow(Horizontal):
        """One checklist line inside PermissionsSettingsPanel: a label
        and a 3D tactile On/Off switch."""

        def __init__(self, key, label, is_on):
            super().__init__(classes="cct-perm-row")
            self._key = key
            self._label_text = label
            self._is_on = is_on

        def compose(self):
            from . import theme_css
            color = theme_css.current_hex("success" if self._is_on else "text-muted")
            mark = "●" if self._is_on else "○"
            yield Static(f"[{color}]{mark}[/] {self._label_text}", classes="cct-perm-label")
            yield Toggle3D(self._key, self._is_on, on_toggle=self._on_toggle_changed)

        def _on_toggle_changed(self, key, value):
            from . import theme_css
            self._is_on = value
            color = theme_css.current_hex("success" if value else "text-muted")
            mark = "●" if value else "○"
            try:
                self.query_one(".cct-perm-label", Static).update(f"[{color}]{mark}[/] {self._label_text}")
            except Exception:
                pass

    class PermissionsSettingsPanel(Vertical):
        """Redesigned 3D Skeuomorphic Permissions & Settings Dashboard with
        header bar, security mode cycler, close button, and 2-column organized grid."""

        def __init__(self, id="cct-permission-panel"):
            super().__init__(id=id)

        @property
        def is_open(self) -> bool:
            return self.has_class("open")

        def _mode_badge_text(self):
            mode = getattr(perm.manager, "mode", "ask")
            return perm.MODE_LABELS.get(mode, "🔒 Ask Every Time")

        def compose(self):
            # 1. Header Bar: Icon, Title, Mode Badge Cycler, and Close Button
            with Horizontal(id="cct-perm-header"):
                with Horizontal(id="cct-perm-title-box"):
                    yield Static("🛡", id="cct-perm-icon")
                    yield Static("Permissions & Security Controls", id="cct-perm-title")
                yield Button(self._mode_badge_text(), id="cct-perm-mode-btn", tooltip="Click to cycle Security Mode (Ask / Restricted / Full)")
                yield Static("", id="cct-perm-spacer")
                yield Button("✕", id="cct-perm-close", classes="cct-icon-btn", tooltip="Close permissions panel (Esc)")

            # 2. Body: Two organized 3D columns
            exec_keys = {"read_files", "write_files", "execute_python", "shell_commands", "install_packages"}
            tools_keys = {"device_control", "internet", "formula_library", "notebook", "calculator"}

            with Horizontal(id="cct-perm-grid"):
                with Vertical(classes="cct-perm-col"):
                    yield Static("⚡ Files & Execution", classes="cct-perm-col-title")
                    for key, label, is_on in perm.manager.snapshot():
                        if key in exec_keys:
                            yield PermissionRow(key, label, is_on)

                with Vertical(classes="cct-perm-col"):
                    yield Static("🌐 Network & Tools", classes="cct-perm-col-title")
                    for key, label, is_on in perm.manager.snapshot():
                        if key in tools_keys:
                            yield PermissionRow(key, label, is_on)

        def on_button_pressed(self, event: Button.Pressed):
            bid = event.button.id
            if bid == "cct-perm-close":
                event.stop()
                self.close_panel()
            elif bid == "cct-perm-mode-btn":
                event.stop()
                modes = list(perm.MODES)
                curr = getattr(perm.manager, "mode", "ask")
                next_mode = modes[(modes.index(curr) + 1) % len(modes)]
                perm.manager.set_mode(next_mode)
                event.button.label = self._mode_badge_text()

        def on_key(self, event) -> None:
            if event.key == "escape":
                event.stop()
                try:
                    event.prevent_default()
                except Exception:
                    pass
                self.close_panel()

        def close_panel(self):
            self.remove_class("open")
            if self.parent and hasattr(self.parent, "_on_permission_panel_toggled"):
                self.parent._on_permission_panel_toggled(False)

        def refresh_rows(self):
            from . import theme_css
            try:
                mode_btn = self.query_one("#cct-perm-mode-btn", Button)
                mode_btn.label = self._mode_badge_text()
            except Exception:
                pass
            for key, label, is_on in perm.manager.snapshot():
                try:
                    toggle = self.query_one(f"#perm-toggle-{key}", Toggle3D)
                    toggle.is_on = is_on
                    toggle.set_class(is_on, "-on")
                    toggle.set_class(not is_on, "-off")
                    toggle.label = Toggle3D._format_label(is_on)
                    row = toggle.parent
                    if row:
                        color = theme_css.current_hex("success" if is_on else "text-muted")
                        mark = "●" if is_on else "○"
                        row.query_one(".cct-perm-label", Static).update(f"[{color}]{mark}[/] {label}")
                except Exception:
                    pass

else:
    PermissionCard = None
    PermissionRow = None
    PermissionsSettingsPanel = None
