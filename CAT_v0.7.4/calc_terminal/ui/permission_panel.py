"""
CCT UI — the single permission & interaction renderer.
Provides:
  * PermissionCard — an inline 3D Skeuomorphic "AI wants permission" request,
    mounted into conversation history with tactile physical buttons.
  * QuestionCard — an interactive 3D Skeuomorphic card for when the AI coding
    agent asks questions with choices or free-form text input.
  * Toggle3D — tactile 3D On/Off physical rocker switch.
  * PermissionRow — row component with label and 3D toggle.
  * PermissionsSettingsPanel — the full on/off checklist opened from footer.
"""

if __name__ == "__main__":
    print("This is a library file and is not meant to be run directly.")
    import sys
    sys.exit(1)

from .. import permissions as perm
from .events import PermissionGranted, PermissionDenied, PermissionCancelled, QuestionAnswered

TEXTUAL_AVAILABLE = True
try:
    from textual.containers import Horizontal, Vertical
    from textual.widgets import Static, Button, Switch, Label, Input
except Exception:
    TEXTUAL_AVAILABLE = False


if TEXTUAL_AVAILABLE:

    class PermissionCard(Vertical):
        """Inline 'AI wants permission' request — mounted into the
        conversation log as its own item with 3D skeuomorphic tactile styling."""

        def __init__(self, request_id, key, action_text, reason_text, id=None, path=None):
            super().__init__(id=id, classes="cct-permcard")
            self.request_id = request_id
            self.key = key
            self._action_text = action_text
            self._reason_text = reason_text
            self._path = path
            self._resolved = False

        def compose(self):
            self._restricted = perm.manager.restricted_review(self.key)
            badge_title = "⚡ ACTION REVIEW REQUIRED" if self._restricted else "🛡 PERMISSION REQUIRED"
            yield Static(f" [b]{badge_title}[/] ", classes="cct-permcard-badge")
            yield Static(f"The AI wants to execute: [bold #e0e7ff]{self._action_text}[/]", classes="cct-permcard-action")
            if self._path:
                yield Static(f"📁 Path: [bold #38bdf8]{self._path}[/]", classes="cct-permcard-path")
            yield Static(f"💬 Reason: [dim]{self._reason_text}[/]", classes="cct-permcard-reason")

            # Tactile 3D Buttons Row
            with Horizontal(classes="cct-permcard-buttons"):
                if self._restricted:
                    yield Button("✔ Accept", id="allow-once", classes="cct-perm-btn cct-perm-btn-allow")
                    yield Button("✖ Reject", id="deny", classes="cct-perm-btn cct-perm-btn-deny")
                    yield Button("✕ Cancel", id="cancel", classes="cct-perm-btn cct-perm-btn-cancel")
                else:
                    yield Button("✔ Allow Once", id="allow-once", classes="cct-perm-btn cct-perm-btn-allow")
                    yield Button("⚡ Always Allow", id="always-allow", classes="cct-perm-btn cct-perm-btn-always")
                    yield Button("✖ Deny", id="deny", classes="cct-perm-btn cct-perm-btn-deny")
                    yield Button("🚫 Always Deny", id="always-deny", classes="cct-perm-btn cct-perm-btn-always-deny")
                    yield Button("✕ Cancel", id="cancel", classes="cct-perm-btn cct-perm-btn-cancel")

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
                verb = "Always Allowed"
            elif bid == "allow-once":
                self.post_message(PermissionGranted(self.request_id, self.key, remember=False))
                tone = "success"
                verb = "Accepted" if getattr(self, "_restricted", False) else "Allowed Once"
            elif bid == "always-deny":
                self.post_message(PermissionDenied(self.request_id, self.key, remember=True))
                tone = "error"
                verb = "Always Denied"
            elif bid == "cancel":
                self.post_message(PermissionCancelled(self.request_id, self.key))
                tone = "warn"
                verb = "Cancelled"
            else:
                self.post_message(PermissionDenied(self.request_id, self.key, remember=False))
                tone = "error"
                verb = "Rejected" if getattr(self, "_restricted", False) else "Denied"

            color = theme_css.current_hex(tone)
            self.mount(Static(f"[{color} bold]➜ Decision: {verb}[/]", classes="cct-permcard-verdict"))


    class QuestionCard(Vertical):
        """Interactive 3D Skeuomorphic card for when the AI coding agent
        asks the user a question with choices or custom text response."""

        def __init__(self, request_id, question, options=None, id=None):
            super().__init__(id=id, classes="cct-permcard cct-questioncard")
            self.request_id = request_id
            self.question = question
            self.options = options or []
            self._resolved = False

        def compose(self):
            yield Static(" ❓ AI CODING INQUIRY ", classes="cct-questioncard-badge")
            yield Static(f"[bold #f8fafc]{self.question}[/]", classes="cct-permcard-title")

            # If preset options are provided, render 3D tactile buttons
            if self.options:
                with Horizontal(classes="cct-permcard-buttons"):
                    for idx, opt in enumerate(self.options):
                        yield Button(f"{idx + 1}. {opt}", id=f"q-opt-{idx}", classes="cct-perm-btn cct-perm-btn-option")

            # Free-form input row for typing own answer
            with Horizontal(classes="cct-permcard-buttons"):
                yield Input(placeholder="Type your answer here (or pick an option above)...",
                            id=f"q-input-{self.request_id}",
                            classes="cct-perm-input")
                yield Button("Respond ↵", id=f"q-submit-{self.request_id}", classes="cct-perm-btn cct-perm-btn-allow")

        def on_input_changed(self, event: Input.Changed):
            try:
                app = self.app
                if hasattr(app, "composer") and app.composer:
                    app.composer.resume_streaming_timer()
            except Exception:
                pass

        def on_input_submitted(self, event: Input.Submitted):
            if self._resolved:
                return
            ans = event.value.strip()
            if ans:
                self._submit_answer(ans)

        def on_button_pressed(self, event: Button.Pressed):
            if self._resolved:
                return
            bid = event.button.id
            if bid.startswith("q-opt-"):
                try:
                    idx = int(bid.replace("q-opt-", ""))
                    ans = self.options[idx]
                    self._submit_answer(ans)
                    return
                except Exception:
                    pass
            elif bid.startswith("q-submit-"):
                inp = self.query_one(f"#q-input-{self.request_id}", Input)
                ans = inp.value.strip()
                if not ans and self.options:
                    ans = self.options[0]
                self._submit_answer(ans or "Acknowledged")

        def _submit_answer(self, answer: str):
            self._resolved = True
            try:
                app = self.app
                if hasattr(app, "composer") and app.composer:
                    app.composer.resume_streaming_timer()
            except Exception:
                pass
            for b in self.query(Button):
                b.disabled = True
            try:
                inp = self.query_one(f"#q-input-{self.request_id}", Input)
                inp.disabled = True
            except Exception:
                pass
            self.post_message(QuestionAnswered(self.request_id, answer))
            self.mount(Static(f"[#38bdf8 bold]➜ Responded:[/] [italic #e2e8f0]\"{answer}\"[/]", classes="cct-permcard-verdict"))


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
        """Redesigned 3D Skeuomorphic Permissions & Security Controls Dashboard."""

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
                yield Button("✕", id="cct-perm-close", classes="cct-perm-close-btn", tooltip="Close permissions panel (Esc)")

            # 2. Body: Two organized 3D columns
            exec_keys = {"read_files", "write_files", "execute_python", "shell_commands", "install_packages"}
            tools_keys = {"device_control", "internet", "browser_automation", "formula_library", "notebook", "calculator"}

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
    QuestionCard = None
    Toggle3D = None
    PermissionRow = None
    PermissionsSettingsPanel = None
