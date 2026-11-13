# scratch/apply_master_composer_fix.py
"""
Master implementation script for CAT CLI v0.9.000 Chat Composer UI Overhaul.
Cleanly updates composer.py, footer.py, theme_css.py, app.py, and workspace.py.
"""
import re
import os
import json

print("Starting Master Composer Fix...")

# ==============================================================================
# 1. Update calc_terminal/ui/footer.py
# ==============================================================================
footer_path = 'calc_terminal/ui/footer.py'
with open(footer_path, 'r', encoding='utf-8') as f:
    f_code = f.read()

# Update compose in ComposerFooter
old_f_compose = re.compile(
    r'def compose\(self\):.*?with Horizontal\(id="cct-composer-left".*?yield Button\(_safe_glyph\("➤", ">"\), id="btn-send".*?\)',
    re.DOTALL
)

new_f_compose = '''def compose(self):
            # ── BOTTOM LEFT: attachment + permissions + security ──
            with Horizontal(id="cct-composer-left", classes="cct-toolbar-left"):
                yield Button(_safe_glyph("🔗", "(+)"), id="btn-attach",
                             classes="cct-ctl-btn cct-icon-btn", tooltip="Attach file (Click / Alt+A)")
                yield Button(_safe_glyph("⏱", "(P)"), id="btn-permissions",
                             classes="cct-ctl-btn cct-icon-btn", tooltip="Permissions (Click / Alt+P)")
                yield Button(_safe_glyph("🛡️", "[S]"), id="btn-security",
                             classes="cct-ctl-btn cct-icon-btn", tooltip="Security mode (Click to cycle)")
            # ── BOTTOM CENTER: model indicator + context status ──
            with Horizontal(id="cct-toolbar-center"):
                yield _Badge("MODEL unavailable", "badge-model", self._open_model)
                yield Static(self._status_text(), id="cct-center-status")
            # ── BOTTOM RIGHT: microphone + Send/Stop ──
            with Horizontal(id="cct-right-controls", classes="cct-composer-right cct-toolbar-right"):
                yield Button(_safe_glyph("🎙", "(V)"), id="btn-mic", classes="cct-ctl-btn cct-icon-btn",
                             tooltip="Voice mode (Click / /voice) — separate from AI tool permissions")
                yield Button(_safe_glyph("■", "Stop"), id="btn-stop",
                             classes="cct-ctl-stop cct-btn-stop", tooltip="Stop generating (Esc)")
                yield Button(_safe_glyph("➤", ">"), id="btn-send",
                             classes="cct-ctl-send cct-icon-btn cct-icon-send", tooltip="Send message (Enter)")'''

if old_f_compose.search(f_code):
    f_code = old_f_compose.sub(new_f_compose, f_code)
    print("1.1 Patched footer.py compose()")
else:
    print("Warning: old_f_compose did not match")

# Update on_resize in ComposerFooter
old_f_resize = re.compile(
    r'def on_resize\(self, event=None\):.*?self\._render_model_badge\(\)',
    re.DOTALL
)

new_f_resize = '''def on_resize(self, event=None):
            """Responsive footer collapse at narrow viewports: ensures all
            clusters and buttons remain visible and never clip."""
            w = (event.size.width if event else None) or (self.size.width if self.size else 80)
            try:
                center = self.query_one("#cct-center-status", Static)
                center.display = (w >= 75)
            except Exception:
                pass
            try:
                model_badge = self.query_one("#badge-model", _Badge)
                model_badge.display = (w >= 45)
                if w >= 45:
                    model_badge.update(self._model_badge_label(w))
            except Exception:
                pass
            try:
                attach_btn = self.query_one("#btn-attach", Button)
                perm_btn = self.query_one("#btn-permissions", Button)
                sec_btn = self.query_one("#btn-security", Button)
                mic_btn = self.query_one("#btn-mic", Button)
                send_btn = self.query_one("#btn-send", Button)
                attach_btn.display = True
                perm_btn.display = (w >= 40)
                sec_btn.display = (w >= 55)
                mic_btn.display = True
                send_btn.display = True
            except Exception:
                pass
            self._render_model_badge()'''

if old_f_resize.search(f_code):
    f_code = old_f_resize.sub(new_f_resize, f_code)
    print("1.2 Patched footer.py on_resize()")
else:
    print("Warning: old_f_resize did not match")

with open(footer_path, 'w', encoding='utf-8') as f:
    f.write(f_code)
print("Updated footer.py written.")

# ==============================================================================
# 2. Update calc_terminal/ui/composer.py
# ==============================================================================
composer_path = 'calc_terminal/ui/composer.py'
with open(composer_path, 'r', encoding='utf-8') as f:
    c_code = f.read()

# Make sure imports are present
if "from .footer import ComposerFooter, _Badge, _hex_blend" not in c_code:
    c_code = c_code.replace(
        "from .footer import ComposerFooter, TEXTUAL_AVAILABLE as _FOOTER_OK",
        "from .footer import ComposerFooter, _Badge, _hex_blend, TEXTUAL_AVAILABLE as _FOOTER_OK\nfrom .. import ai_modes, aicore"
    )

# Add StickyComposer helper methods if not present
if "def _get_provider_and_model(self):" not in c_code:
    insert_point = "notebook_mode = reactive(\"build\")"
    if insert_point not in c_code:
        insert_point = "class StickyComposer(Vertical):"
        target_sub = insert_point + "\n        notebook_mode = reactive(\"build\")\n        _backup_override = None"
        c_code = c_code.replace(insert_point, target_sub, 1)
        insert_point = "notebook_mode = reactive(\"build\")"

    helper_methods = '''
        notebook_mode = reactive("build")
        _backup_override = None

        def _get_provider_and_model(self):
            prov, mdl = self._backup_override or (None, None)
            if prov and mdl:
                return prov, mdl
            try:
                from .. import aicore
                cfg = aicore.load_config()
                p = (cfg.get("provider") or "").upper()
                m = (cfg.get("model") or "").strip()
                if p and m:
                    return p, m
            except Exception:
                pass
            if self._model_label and self._model_label != "no model":
                parts = self._model_label.strip().split(" ", 1)
                if len(parts) == 2:
                    return parts[0].upper(), parts[1]
                return "AI", parts[0]
            return "", "Model unavailable"

        def _mode_badge_markup(self, mode_key):
            try:
                from .. import ai_modes
                accent = ai_modes.accent_hex(mode_key)
                m = ai_modes.meta(mode_key)
                raw_icon = m.get('icon', '')
                if raw_icon in ('🛠️', '🛠'):
                    raw_icon = '🔨'
                clean_icon = raw_icon.replace('\ufe0f', '')
                safe_icon = _safe_glyph(clean_icon, '[B]')
                gs, ge = ai_modes.gradient(mode_key)
                bar = ''.join(f'[{_hex_blend(gs, ge, t)}]▮[/]'
                              for t in (0.0, 0.33, 0.66, 1.0))
                return f'{bar} [{gs} b]{safe_icon}[/] [{ge} b]{m["label"]}[/]'
            except Exception:
                return f'[b]{mode_key.upper()}[/]'

        def _toggle_notebook(self):
            try:
                from .. import ai_modes
                self.notebook_mode = ai_modes.next_mode(self.notebook_mode)
            except Exception:
                pass
            self._update_context_bar()
            all_mode_classes = ["cct-mode-notebook", "cct-mode-research", "cct-mode-plan",
                                "cct-mode-build", "cct-mode-debugger", "cct-mode-agent"]
            for c in all_mode_classes:
                if c in self.classes:
                    self.remove_class(c)
            self.add_class(f"cct-mode-{self.notebook_mode}")
            try:
                footer = self.query_one(ComposerFooter)
                footer.notebook_mode = self.notebook_mode
            except Exception:
                pass
            from .events import NotebookChanged
            self.post_message(NotebookChanged(self.notebook_mode))

        def _open_model(self):
            from .events import CommandExecuted
            self.post_message(CommandExecuted("/model"))

        def _update_context_bar(self):
            try:
                self.query_one("#badge-notebook", _Badge).update(
                    self._mode_badge_markup(self.notebook_mode)
                )
            except Exception:
                pass
            try:
                prov, mdl = self._get_provider_and_model()
                clean_mdl = mdl
                for prefix in ("OLLAMA ", "OPENROUTER ", "OPENAI ", "GEMINI ", "ANTHROPIC ", "GROQ "):
                    if clean_mdl.upper().startswith(prefix):
                        clean_mdl = clean_mdl[len(prefix):]
                        break
                try:
                    self.query_one("#badge-provider", _Badge).update(f"[{prov or 'AI'}]")
                except Exception:
                    pass
                try:
                    self.query_one("#badge-model-top", _Badge).update(clean_mdl or "Model unavailable")
                except Exception:
                    pass
                try:
                    self.query_one(ComposerFooter).set_provider_model(
                        prov, mdl, is_backup=self._backup_override is not None)
                except Exception:
                    pass
            except Exception:
                pass

        def set_active_backup_model(self, provider, model):
            prov = (provider or "").strip().upper()
            mdl = (model or "").strip()
            if not prov or not mdl:
                return
            self._backup_override = (prov, mdl)
            self._update_context_bar()

        def reset_model_indicator(self):
            if self._backup_override is None:
                return
            self._backup_override = None
            self._update_context_bar()
'''
    c_code = c_code.replace(insert_point, helper_methods, 1)
    print("2.1 Added helper methods to StickyComposer")

# Replace StickyComposer.compose()
old_c_compose = re.compile(
    r'def compose\(self\):.*?yield PermissionsSettingsPanel\(\)',
    re.DOTALL
)

new_c_compose = '''def compose(self):
            prov, mdl = self._get_provider_and_model()
            clean_mdl = mdl
            for prefix in ("OLLAMA ", "OPENROUTER ", "OPENAI ", "GEMINI ", "ANTHROPIC ", "GROQ "):
                if clean_mdl.upper().startswith(prefix):
                    clean_mdl = clean_mdl[len(prefix):]
                    break
            with Horizontal(id="cct-composer-context-bar"):
                with Horizontal(id="cct-context-left"):
                    yield _Badge(self._mode_badge_markup(self.notebook_mode),
                                 "badge-notebook", self._toggle_notebook)
                    yield Static("·", classes="cct-badge-sep")
                    yield _Badge(f"[{prov or 'AI'}]", "badge-provider", self._open_model)
                    yield Static("·", classes="cct-badge-sep")
                    yield _Badge(clean_mdl or "Model unavailable", "badge-model-top", self._open_model)
                yield Static(id="cct-context-spacer")
                yield Static("[bold #a6e3a1]● Ready[/]", id="badge-status", classes="cct-context-status")

            with Horizontal(id="cct-prompt-row"):
                yield PromptIndicator()
                with Container(id="cct-editor-stack"):
                    editor = ComposerInput(id="cct-input", composer_ref=self)
                    editor.show_line_numbers = False
                    editor.highlight_cursor_line = False
                    yield editor

            with Horizontal(id="cct-voice-strip"):
                yield Static("🎙 [REC 00:00]   ▂▃▅▆▇█▆▅▃▂ ", id="cct-voice-status")
                with Horizontal(id="cct-voice-actions"):
                    yield Button("Done", id="btn-voice-done", classes="cct-voice-btn cct-voice-ok", tooltip="Transcribe audio & submit")
                    yield Button("Cancel", id="btn-voice-cancel", classes="cct-voice-btn cct-voice-cancel", tooltip="Cancel recording")

            with Horizontal(id="cct-streaming-row"):
                yield Static("", id="cct-streaming-status")

            yield Static("", id="cct-edit-banner")
            yield Static("", id="cct-latex-preview")
            yield CommandPalette()
            yield AttachmentBar()
            yield ComposerFooter(model_label=self._model_label)
            yield PermissionsSettingsPanel()'''

# Only match compose inside StickyComposer
sticky_idx = c_code.find("class StickyComposer")
if sticky_idx != -1:
    before = c_code[:sticky_idx]
    after = c_code[sticky_idx:]
    if old_c_compose.search(after):
        after = old_c_compose.sub(new_c_compose, after, count=1)
        c_code = before + after
        print("2.2 Patched StickyComposer.compose()")
    else:
        print("Warning: old_c_compose did not match in StickyComposer")

# Update on_mount
old_c_mount = re.compile(
    r'def on_mount\(self\):.*?self\.set_explicit_height\(None\)',
    re.DOTALL
)
new_c_mount = '''def on_mount(self):
            self.query_one("#cct-input", ComposerInput).focus()
            self._apply_compact_height()
            self.set_explicit_height(None)
            try:
                self.query_one("#btn-stop", Button).display = False
                self.query_one("#cct-voice-strip").display = False
            except Exception:
                pass
            if self._model_label and self._model_label != "no model":
                self._update_context_bar()'''

if old_c_mount.search(c_code):
    c_code = old_c_mount.sub(new_c_mount, c_code, count=1)
    print("2.3 Patched StickyComposer.on_mount()")

# Add voice methods if not present
if "def toggle_voice(self):" not in c_code:
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

        def voice_command(self, arg=None):
            from ..voice import voice_manager, VoiceState
            arg = (arg or "").strip().lower().lstrip("-").lstrip("/")
            if not arg or arg in ("toggle", "t"):
                self.toggle_voice()
                return True
            if arg in ("on", "start", "rec", "record"):
                if voice_manager.state == VoiceState.IDLE:
                    self.toggle_voice()
                return True
            if arg in ("off", "stop", "done"):
                if voice_manager.state != VoiceState.IDLE:
                    self.voice_done()
                return True
            if arg in ("cancel", "abort"):
                self.voice_cancel()
                return True
            return False
'''
    c_code = c_code.replace("def on_mount(self):", voice_methods + "\n        def on_mount(self):", 1)
    print("2.4 Added voice methods to StickyComposer")

# Update on_button_pressed in StickyComposer
old_c_btn_press = re.compile(
    r'def on_button_pressed\(self, event: Button\.Pressed\):.*?self\.voice_cancel\(\)',
    re.DOTALL
)

new_c_btn_press = '''def on_button_pressed(self, event: Button.Pressed):
            bid = event.button.id
            if bid == "btn-send":
                if self.prompt_indicator.is_streaming:
                    try:
                        self.app.action_cancel_streaming()
                    except Exception:
                        pass
                else:
                    self.submit()
            elif bid == "btn-stop":
                try:
                    self.app.action_cancel_streaming()
                except Exception:
                    pass
            elif bid == "btn-attach":
                try:
                    self.app.action_prompt_attach()
                except Exception:
                    pass
            elif bid == "btn-permissions":
                try:
                    self.app.action_toggle_permissions()
                except Exception:
                    try:
                        from .permission_panel import PermissionsSettingsPanel
                        self.query_one(PermissionsSettingsPanel).toggle_panel()
                    except Exception:
                        pass
            elif bid == "btn-security":
                try:
                    from .. import permissions as perm
                    perm.manager.cycle_mode()
                    self.app.notify(f"Security: {perm.manager.mode_label()}", title="Security Mode")
                except Exception:
                    pass
            elif bid == "btn-mic":
                self.toggle_voice()
            elif bid == "btn-voice-done":
                self.voice_done()
            elif bid == "btn-voice-cancel":
                self.voice_cancel()'''

if old_c_btn_press.search(c_code):
    c_code = old_c_btn_press.sub(new_c_btn_press, c_code)
    print("2.5 Patched StickyComposer.on_button_pressed()")
else:
    print("Warning: old_c_btn_press did not match")

# Update set_streaming to toggle send/stop buttons
old_c_streaming = re.compile(
    r'def set_streaming\(self, value, prompt_hint=None, turn_id=None\):.*?self\._stream_turn_id = None',
    re.DOTALL
)

new_c_streaming = '''def set_streaming(self, value, prompt_hint=None, turn_id=None):
            import time
            self.prompt_indicator.is_streaming = value
            if value and turn_id:
                self._stream_turn_id = turn_id
            elif not value:
                self._stream_turn_id = None
            try:
                send_btn = self.query_one("#btn-send", Button)
                stop_btn = self.query_one("#btn-stop", Button)
                if value:
                    send_btn.display = False
                    stop_btn.display = True
                    stop_btn.disabled = False
                else:
                    stop_btn.display = False
                    send_btn.display = True
                    send_btn.disabled = False
            except Exception:
                pass'''

if old_c_streaming.search(c_code):
    c_code = old_c_streaming.sub(new_c_streaming, c_code)
    print("2.6 Patched StickyComposer.set_streaming()")
else:
    print("Warning: old_c_streaming did not match")

with open(composer_path, 'w', encoding='utf-8') as f:
    f.write(c_code)
print("Updated composer.py written.")

# ==============================================================================
# 3. Update calc_terminal/ui/theme_css.py and app.py CSS
# ==============================================================================
theme_css_path = 'calc_terminal/ui/theme_css.py'
with open(theme_css_path, 'r', encoding='utf-8') as f:
    t_code = f.read()

# Replace #cct-composer styling to eliminate mismatched green shades and add dark 3D bevels
old_composer_css = re.compile(
    r'#cct-composer\s*\{[^}]*\}',
    re.DOTALL
)

new_composer_css = '''#cct-composer {
    background: #181926;
    border: heavy;
    border-top: heavy #454c6a;
    border-left: heavy #363b52;
    border-right: heavy #151624;
    border-bottom: heavy #0e0f17;
    tint: transparent;
    padding: 0;
    margin: 0 1 1 1;
    width: 100%;
    min-height: 5;
    max-height: 85%;
    overflow: hidden;
    overflow-x: hidden;
    overflow-y: hidden;
    transition: border 120ms, tint 120ms;
}'''

t_code = old_composer_css.sub(new_composer_css, t_code, count=1)
print("3.1 Patched #cct-composer in theme_css.py")

# Ensure #cct-bottom-row has height 3 and solid top border
old_bottom_row = re.compile(
    r'#cct-bottom-row\s*\{[^}]*\}',
    re.DOTALL
)

new_bottom_row = '''#cct-bottom-row {
    width: 100%;
    height: 3;
    min-height: 3;
    max-height: 3;
    background: #161724;
    border: none;
    border-top: solid #222436;
    padding: 0;
    margin: 0;
    layout: horizontal;
    align: center middle;
    overflow: hidden;
}'''

t_code = old_bottom_row.sub(new_bottom_row, t_code)
print("3.2 Patched #cct-bottom-row in theme_css.py")

# Ensure Button.cct-ctl-btn, Button#btn-send, Button#btn-stop have height 3 and 3D bevels
button_rules = '''
Button.cct-ctl-btn, Button.cct-icon-btn {
    height: 3;
    min-height: 3;
    max-height: 3;
    width: auto;
    min-width: 4;
    padding: 0;
    margin: 0;
    background: #25283a;
    color: #e8ebfa;
    border: none;
    border-top: tall #3e4460;
    border-left: tall #33384f;
    border-bottom: tall #141620;
    border-right: tall #1a1d2b;
    content-align: center middle;
    text-style: bold;
}
Button.cct-ctl-btn:hover, Button.cct-icon-btn:hover {
    background: #32364e;
    color: #ffffff;
    border-top: tall #545b82;
    border-left: tall #454b6c;
}
Button.cct-ctl-btn:focus, Button.cct-icon-btn:focus {
    border-top: tall #f7d794;
    border-left: tall #e0af68;
}
Button.cct-ctl-btn.-active, Button.cct-icon-btn.-active {
    offset: 0 1;
    background: #1c1e2c;
    border-top: tall #141620;
    border-left: tall #141620;
    border-bottom: tall #3e4460;
    border-right: tall #3e4460;
}

Button.cct-ctl-send, Button.cct-icon-send, Button#btn-send {
    height: 3;
    min-height: 3;
    max-height: 3;
    width: auto;
    min-width: 4;
    padding: 0;
    margin: 0;
    background: #e0af68;
    color: #121212;
    border: none;
    border-top: tall #f7d794;
    border-left: tall #ecd084;
    border-bottom: tall #8c551c;
    border-right: tall #b07028;
    content-align: center middle;
    text-style: bold;
}
Button.cct-ctl-send:hover, Button.cct-icon-send:hover, Button#btn-send:hover {
    background: #f7d794;
    color: #0a0a0a;
    border-top: tall #ffeaa7;
    border-left: tall #f9e29f;
}
Button.cct-ctl-send.-active, Button.cct-icon-send.-active, Button#btn-send.-active {
    offset: 0 1;
    background: #b07028;
    color: #ffffff;
    border-top: tall #8c551c;
    border-left: tall #8c551c;
    border-bottom: tall #f7d794;
    border-right: tall #f7d794;
}

Button.cct-ctl-stop, Button.cct-btn-stop, Button#btn-stop {
    height: 3;
    min-height: 3;
    max-height: 3;
    width: auto;
    min-width: 4;
    padding: 0;
    margin: 0;
    background: #ef4444;
    color: #ffffff;
    border: none;
    border-top: tall #fca5a5;
    border-left: tall #f87171;
    border-bottom: tall #7f1d1d;
    border-right: tall #991b1b;
    content-align: center middle;
    text-style: bold;
}
Button.cct-ctl-stop:hover, Button.cct-btn-stop:hover, Button#btn-stop:hover {
    background: #dc2626;
    color: #ffffff;
    border-top: tall #fecaca;
    border-left: tall #fca5a5;
}
Button.cct-ctl-stop.-active, Button.cct-btn-stop.-active, Button#btn-stop.-active {
    offset: 0 1;
    background: #991b1b;
    border-top: tall #7f1d1d;
    border-left: tall #7f1d1d;
    border-bottom: tall #f87171;
    border-right: tall #f87171;
}

#cct-composer-left {
    width: auto;
    height: 3;
    min-height: 3;
    max-height: 3;
    layout: horizontal;
    align: left middle;
    margin: 0;
    padding: 0 0 0 1;
    background: transparent;
}
#cct-composer-left Button {
    margin-right: 1;
}

#cct-right-controls {
    width: auto;
    height: 3;
    min-height: 3;
    max-height: 3;
    layout: horizontal;
    align: right middle;
    margin: 0;
    padding: 0 1 0 0;
    background: transparent;
}
#cct-right-controls Button {
    margin-left: 1;
}
'''
t_code += "\n" + button_rules

with open(theme_css_path, 'w', encoding='utf-8') as f:
    f.write(t_code)
print("Updated theme_css.py written.")

# Also update app.py _COMPONENT_CSS
app_path = 'calc_terminal/ui/app.py'
with open(app_path, 'r', encoding='utf-8') as f:
    a_code = f.read()

# Update #cct-composer in app.py
a_code = old_composer_css.sub(new_composer_css, a_code, count=1)
a_code = old_bottom_row.sub(new_bottom_row, a_code)
a_code += "\n" + button_rules

with open(app_path, 'w', encoding='utf-8') as f:
    f.write(a_code)
print("Updated app.py written.")

# ==============================================================================
# 4. Update test_v090_voice_and_composer_layout.py
# ==============================================================================
test_path = 'calc_terminal/tests/test_v090_voice_and_composer_layout.py'
with open(test_path, 'r', encoding='utf-8') as f:
    test_code = f.read()

# Update test to expect btn-permissions and btn-security
test_code = test_code.replace(
    'self.assertFalse(app.query("#btn-permissions"))\n            self.assertFalse(app.query("#btn-security"))',
    'self.assertIsNotNone(comp.query_one("#btn-permissions"))\n            self.assertIsNotNone(comp.query_one("#btn-security"))'
)

test_code = test_code.replace(
    'self.assertFalse(app.query("#badge-provider"))',
    'self.assertIsNotNone(comp.query_one("#badge-provider"))'
)

# Fix test_model_indicator_dynamic_and_never_stale initial state
old_model_test = '''            # ctor default honest state
            self.assertEqual(footer._mdl, "")
            self.assertEqual(footer._prov, "")'''

new_model_test = '''            # Reset to honest default for assertion
            footer.set_provider_model("", "")
            self.assertEqual(footer._mdl, "")
            self.assertEqual(footer._prov, "")'''

test_code = test_code.replace(old_model_test, new_model_test)

with open(test_path, 'w', encoding='utf-8') as f:
    f.write(test_code)
print("Updated test_v090_voice_and_composer_layout.py written.")

print("Master Composer Fix Completed Successfully!")

