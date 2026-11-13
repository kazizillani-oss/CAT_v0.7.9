# Patch calc_terminal/ui/footer.py and calc_terminal/ui/composer.py for the 3D layout & voice integration

import re

# --- 1. Patch calc_terminal/ui/footer.py ---
with open("calc_terminal/ui/footer.py", "r", encoding="utf-8") as f:
    footer_text = f.read()

# Replace compose() in ComposerFooter so action buttons are in composer.py
old_footer_compose = '''        def compose(self):
            with Horizontal(id="cct-left-controls"):
                yield _Badge(self._mode_badge_markup(self.notebook_mode),
                             "badge-notebook", self._toggle_notebook)
                yield Static("\\u00b7", classes="cct-badge-sep")
                yield _Badge(self._model_label, "badge-model", self._open_model)
            yield Static(id="cct-footer-spacer-left")
            yield Static(self._status_text(), id="cct-center-status")
            yield Static(id="cct-footer-spacer-right")
            with Horizontal(id="cct-right-controls"):
                yield Button(_safe_glyph("⏱", "(P)"), id="btn-permissions", classes="cct-icon-btn", tooltip="Permissions & Security (Click / Alt+P)")
                yield Button(_safe_glyph("🔗", "(+)"), id="btn-attach", classes="cct-icon-btn", tooltip="Attach file (Click / Alt+A)")
                yield Button(_safe_glyph("➤", ">"), id="btn-send", classes="cct-icon-btn cct-icon-send", tooltip="Send message (Enter)")'''

new_footer_compose = '''        def compose(self):
            with Horizontal(id="cct-left-controls"):
                yield _Badge(self._mode_badge_markup(self.notebook_mode),
                             "badge-notebook", self._toggle_notebook)
                yield Static("\\u00b7", classes="cct-badge-sep")
                yield _Badge(self._model_label, "badge-model", self._open_model)
            yield Static(id="cct-footer-spacer-left")
            yield Static(self._status_text(), id="cct-center-status")
            yield Static(id="cct-footer-spacer-right")'''

assert old_footer_compose in footer_text, "Failed to find old_footer_compose in footer.py"
footer_text = footer_text.replace(old_footer_compose, new_footer_compose)

with open("calc_terminal/ui/footer.py", "w", encoding="utf-8") as f:
    f.write(footer_text)
print("Updated calc_terminal/ui/footer.py")

# --- 2. Patch calc_terminal/ui/composer.py ---
with open("calc_terminal/ui/composer.py", "r", encoding="utf-8") as f:
    comp_text = f.read()

old_comp_compose = '''        def compose(self):
            with Horizontal(id="cct-streaming-row"):
                yield Static("", id="cct-streaming-status")
                yield Button(_safe_glyph("■ Stop", "Stop"), id="btn-stop", classes="cct-stop-btn", tooltip="Stop response (Esc)")
            yield Static("", id="cct-edit-banner")
            yield Static("", id="cct-latex-preview")
            with Horizontal(id="cct-prompt-row"):
                yield PromptIndicator()
                with Container(id="cct-editor-stack"):
                    editor = ComposerInput(id="cct-input", composer_ref=self)
                    editor.show_line_numbers = False
                    editor.highlight_cursor_line = False
                    yield editor
            # Sibling of the prompt row, not nested in cct-editor-stack (which
            # is height-capped for the input alone) so the palette's own rows
            # aren't clipped by the editor's height cap.
            yield CommandPalette()
            yield AttachmentBar()
            yield ComposerFooter(model_label=self._model_label)
            yield PermissionsSettingsPanel()'''

new_comp_compose = '''        def compose(self):
            with Horizontal(id="cct-voice-strip"):
                yield Static("🎙 [REC 00:00]   ▂▃▅▆▇█▆▅▃▂ ", id="cct-voice-status")
                with Horizontal(id="cct-voice-actions"):
                    yield Button("Done", id="btn-voice-done", classes="cct-voice-btn cct-voice-ok", tooltip="Transcribe audio & submit")
                    yield Button("Cancel", id="btn-voice-cancel", classes="cct-voice-btn cct-voice-cancel", tooltip="Cancel recording")
            with Horizontal(id="cct-streaming-row"):
                yield Static("", id="cct-streaming-status")
                yield Button(_safe_glyph("■ Stop", "Stop"), id="btn-streaming-stop", classes="cct-stop-btn", tooltip="Stop response (Esc)")
            yield Static("", id="cct-edit-banner")
            yield Static("", id="cct-latex-preview")
            with Horizontal(id="cct-composer-frame"):
                with Horizontal(id="cct-composer-left"):
                    yield Button(_safe_glyph("🔗", "(+)"), id="btn-attach", classes="cct-icon-btn", tooltip="Attach file (Click / Alt+A)")
                    yield Button(_safe_glyph("⏱", "(P)"), id="btn-permissions", classes="cct-icon-btn", tooltip="Permissions (Click / Alt+P)")
                    yield Button(_safe_glyph("🛡️", "[S]"), id="btn-security", classes="cct-icon-btn", tooltip="Security mode (Click to cycle)")
                with Horizontal(id="cct-prompt-row"):
                    yield PromptIndicator()
                    with Container(id="cct-editor-stack"):
                        editor = ComposerInput(id="cct-input", composer_ref=self)
                        editor.show_line_numbers = False
                        editor.highlight_cursor_line = False
                        yield editor
                with Horizontal(id="cct-right-controls", classes="cct-composer-right"):
                    yield Button(_safe_glyph("🎙", "(V)"), id="btn-mic", classes="cct-icon-btn", tooltip="Real Voice mode (Click / /voice)")
                    yield Button(_safe_glyph("■", "Stop"), id="btn-stop", classes="cct-icon-btn cct-btn-stop", tooltip="Stop response (Esc)")
                    yield Button(_safe_glyph("➤", ">"), id="btn-send", classes="cct-icon-btn cct-icon-send", tooltip="Send message (Enter)")
            yield CommandPalette()
            yield AttachmentBar()
            yield ComposerFooter(model_label=self._model_label)
            yield PermissionsSettingsPanel()'''

assert old_comp_compose in comp_text, "Failed to find old_comp_compose in composer.py"
comp_text = comp_text.replace(old_comp_compose, new_comp_compose)

# Add voice methods and handlers to StickyComposer
voice_methods = '''
        def toggle_voice(self):
            """Toggle real microphone input and waveform visualization."""
            from ..voice import voice_manager, VoiceState
            if voice_manager.state == VoiceState.IDLE:
                if not voice_manager.check_permission():
                    try:
                        self.app.notify("Microphone access restricted.", title="Voice Mode", severity="warning")
                    except Exception:
                        pass
                    return
                success = voice_manager.start_recording()
                if success:
                    try:
                        strip = self.query_one("#cct-voice-strip")
                        strip.display = True
                        mic_btn = self.query_one("#btn-mic", Button)
                        mic_btn.set_class(True, "cct-mic-active")
                    except Exception:
                        pass
                    self._start_voice_refresh_timer()
            elif voice_manager.state == VoiceState.LISTENING:
                self.voice_done()
            else:
                self.voice_cancel()

        def _start_voice_refresh_timer(self):
            if getattr(self, "_voice_timer", None) is not None:
                return
            self._voice_timer = self.set_interval(0.08, self._refresh_voice_ui)

        def _refresh_voice_ui(self):
            from ..voice import voice_manager, VoiceState
            if voice_manager.state == VoiceState.LISTENING:
                dur = voice_manager.get_duration_str()
                wf = "".join(voice_manager._waveform_buffer[-16:])
                try:
                    status = self.query_one("#cct-voice-status", Static)
                    status.update(f"[bold #f7768e]● REC[/] [{dur}] [bold #7aa2f7]{wf}[/]")
                except Exception:
                    pass
            elif voice_manager.state in (VoiceState.PROCESSING, VoiceState.TRANSCRIBING):
                try:
                    status = self.query_one("#cct-voice-status", Static)
                    status.update(f"[bold #e0af68]⏳ Transcribing audio...[/]")
                except Exception:
                    pass
            elif voice_manager.state == VoiceState.READY_TO_SUBMIT:
                text = voice_manager._transcribed_text
                voice_manager.cancel_recording()
                self._stop_voice_refresh_timer()
                if text:
                    editor = self.query_one("#cct-input", ComposerInput)
                    current = (editor.text or "").strip()
                    editor.text = (current + " " + text).strip() if current else text
                    editor.focus()
                    try:
                        self.app.notify(f"Transcribed: \\"{text}\\"", title="🎙 Voice", timeout=2.5)
                    except Exception:
                        pass
                try:
                    self.query_one("#cct-voice-strip").display = False
                    self.query_one("#btn-mic", Button).set_class(False, "cct-mic-active")
                except Exception:
                    pass
            elif voice_manager.state in (VoiceState.IDLE, VoiceState.ERROR):
                if voice_manager.state == VoiceState.ERROR:
                    try:
                        self.app.notify(f"Voice: {voice_manager._error_message}", title="Voice Error", severity="error")
                    except Exception:
                        pass
                self.voice_cancel()

        def _stop_voice_refresh_timer(self):
            if getattr(self, "_voice_timer", None) is not None:
                try:
                    self._voice_timer.stop()
                except Exception:
                    pass
                self._voice_timer = None

        def voice_done(self):
            from ..voice import voice_manager
            voice_manager.stop_and_transcribe()

        def voice_cancel(self):
            from ..voice import voice_manager
            voice_manager.cancel_recording()
            self._stop_voice_refresh_timer()
            try:
                self.query_one("#cct-voice-strip").display = False
                self.query_one("#btn-mic", Button).set_class(False, "cct-mic-active")
            except Exception:
                pass

        def cycle_security_mode(self):
            """Cycle security permission modes: Ask -> Restricted -> Full -> Ask."""
            from .. import perm
            current = perm.manager.mode
            next_mode = "restricted" if current == "ask" else ("full" if current == "restricted" else "ask")
            perm.manager.set_mode(next_mode)
            try:
                icon = "🛡️" if next_mode == "full" else ("⏱" if next_mode == "ask" else "🔒")
                self.app.notify(f"Security Mode: {next_mode.title()}", title=f"{icon} Security", timeout=2.0)
                sec_btn = self.query_one("#btn-security", Button)
                sec_btn.tooltip = f"Security: {next_mode.title()} (Click to cycle)"
            except Exception:
                pass
            try:
                from .events import PermissionModeChanged
                self.post_message(PermissionModeChanged(next_mode))
            except Exception:
                pass
'''

# Add button handlers for mic, security, voice-done, voice-cancel in on_button_pressed
old_handlers = '''            elif bid == "btn-attach":
                try:
                    self.app.action_prompt_attach()
                except Exception:
                    pass'''

new_handlers = '''            elif bid == "btn-attach":
                try:
                    self.app.action_prompt_attach()
                except Exception:
                    pass
            elif bid == "btn-mic":
                self.toggle_voice()
            elif bid == "btn-security":
                self.cycle_security_mode()
            elif bid == "btn-voice-done":
                self.voice_done()
            elif bid == "btn-voice-cancel":
                self.voice_cancel()'''

assert old_handlers in comp_text, "Failed to find old_handlers in composer.py"
comp_text = comp_text.replace(old_handlers, new_handlers)

# Mount initial states: #btn-stop hidden, #cct-voice-strip hidden
old_on_mount = '''        def on_mount(self):
            self.query_one("#cct-input", ComposerInput).focus()
            self._apply_compact_height()
            self.set_explicit_height(None)'''

new_on_mount = '''        def on_mount(self):
            self.query_one("#cct-input", ComposerInput).focus()
            self._apply_compact_height()
            self.set_explicit_height(None)
            try:
                self.query_one("#btn-stop", Button).display = False
                self.query_one("#cct-voice-strip").display = False
            except Exception:
                pass'''

assert old_on_mount in comp_text, "Failed to find old_on_mount in composer.py"
comp_text = comp_text.replace(old_on_mount, new_on_mount + voice_methods)

# Update set_streaming to toggle send/stop display
old_streaming_send = '''            try:
                send_btn = self.query_one("#btn-send", Button)
                if value:
                    send_btn.label = _safe_glyph("⏸", "||")
                    send_btn.tooltip = "Interrupt response (Click || / Esc)"
                    send_btn.disabled = False
                    send_btn.set_class(True, "cct-btn-interrupt")
                else:
                    send_btn.label = _safe_glyph("➤", ">")
                    send_btn.tooltip = "Send message (Enter)"
                    send_btn.disabled = False
                    send_btn.set_class(False, "cct-btn-interrupt")
            except Exception:
                pass
            try:
                self.query_one("#btn-stop", Button).display = value
            except Exception:
                pass'''

new_streaming_send = '''            try:
                send_btn = self.query_one("#btn-send", Button)
                stop_btn = self.query_one("#btn-stop", Button)
                if value:
                    # When generating: Stop button correctly replaces Send button
                    send_btn.display = False
                    stop_btn.display = True
                    stop_btn.disabled = False
                else:
                    # When idle: Send button restored
                    stop_btn.display = False
                    send_btn.display = True
                    send_btn.disabled = False
            except Exception:
                pass'''

assert old_streaming_send in comp_text, "Failed to find old_streaming_send in composer.py"
comp_text = comp_text.replace(old_streaming_send, new_streaming_send)

with open("calc_terminal/ui/composer.py", "w", encoding="utf-8") as f:
    f.write(comp_text)
print("Updated calc_terminal/ui/composer.py")

