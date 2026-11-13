with open('calc_terminal/ui/composer.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update imports
old_imp = 'from .footer import ComposerFooter, TEXTUAL_AVAILABLE as _FOOTER_OK'
new_imp = 'from .footer import ComposerFooter, _Badge, _hex_blend, TEXTUAL_AVAILABLE as _FOOTER_OK\nfrom .. import ai_modes, aicore'

if old_imp in text:
    text = text.replace(old_imp, new_imp)
    print("Updated imports in composer.py")
else:
    print("old_imp not found in composer.py")

# 2. Update StickyComposer methods and compose
old_compose = '''        @property
        def prompt_indicator(self):
            return self.query_one(PromptIndicator)

        def compose(self):
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

new_compose = '''        notebook_mode = reactive("build")

        @property
        def prompt_indicator(self):
            return self.query_one(PromptIndicator)

        def _get_provider_and_model(self):
            try:
                from .. import aicore
                cfg = aicore.load_config()
                p = (cfg.get("provider") or "").upper()
                m = cfg.get("model") or ""
                if p and m:
                    return p, m
            except Exception:
                pass
            if self._model_label and self._model_label != "no model":
                parts = self._model_label.strip().split(" ", 1)
                if len(parts) == 2:
                    return parts[0].upper(), parts[1]
                return "AI", parts[0]
            return "PROVIDER", "no model"

        def _mode_badge_markup(self, mode_key):
            accent = ai_modes.accent_hex(mode_key)
            m = ai_modes.meta(mode_key)
            raw_icon = m.get('icon', '')
            if raw_icon in ('🛠️', '🛠'):
                raw_icon = '🔨'
            clean_icon = raw_icon.replace('\ufe0f', '')
            safe_icon = _safe_glyph(clean_icon, '[B]')
            try:
                gs, ge = ai_modes.gradient(mode_key)
                bar = ''.join(f'[{_hex_blend(gs, ge, t)}]\u25ae[/]'
                              for t in (0.0, 0.33, 0.66, 1.0))
                return f'{bar} [{gs} b]{safe_icon}[/] [{ge} b]{m["label"]}[/]'
            except Exception:
                return f'[{accent} b]{safe_icon} {m["label"]}[/]'

        def _toggle_notebook(self):
            self.notebook_mode = ai_modes.next_mode(self.notebook_mode)
            self._update_context_bar()
            all_mode_classes = ["cct-mode-notebook", "cct-mode-research", "cct-mode-plan",
                                "cct-mode-build", "cct-mode-debugger", "cct-mode-agent"]
            for c in all_mode_classes:
                self.remove_class(c)
            self.add_class(f"cct-mode-{self.notebook_mode}")
            try:
                footer = self.query_one(ComposerFooter)
                footer.notebook_mode = self.notebook_mode
            except Exception:
                pass
            self.post_message(NotebookChanged(self.notebook_mode))

        def _open_model(self):
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
                self.query_one("#badge-provider", _Badge).update(f"[{prov}]")
                self.query_one("#badge-model", _Badge).update(mdl)
            except Exception:
                pass

        def compose(self):
            prov, mdl = self._get_provider_and_model()
            with Horizontal(id="cct-composer-context-bar"):
                with Horizontal(id="cct-context-left"):
                    yield _Badge(self._mode_badge_markup(self.notebook_mode),
                                 "badge-notebook", self._toggle_notebook)
                    yield Static("\u00b7", classes="cct-badge-sep")
                    yield _Badge(f"[{prov}]", "badge-provider", self._open_model)
                    yield Static("\u00b7", classes="cct-badge-sep")
                    yield _Badge(mdl, "badge-model", self._open_model)
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
                yield Button(_safe_glyph("■ Stop", "Stop"), id="btn-streaming-stop", classes="cct-stop-btn", tooltip="Stop response (Esc)")

            yield Static("", id="cct-edit-banner")
            yield Static("", id="cct-latex-preview")
            yield CommandPalette()
            yield AttachmentBar()
            yield ComposerFooter(model_label=self._model_label)
            yield PermissionsSettingsPanel()'''

if old_compose in text:
    text = text.replace(old_compose, new_compose)
    print("Replaced StickyComposer.compose in composer.py")
else:
    print("old_compose NOT found in composer.py")

# 3. Update set_model_label and set_ai_mode
old_set_model = '''        def set_model_label(self, label):
            self._model_label = label
            self.query_one(ComposerFooter).set_model_label(label)

        def set_ai_mode(self, mode_key):
            """Syncs the footer's mode badge after a `/mode`, `/agent`,
            `/build`, `/plan`, or `/notebook` command switches mode —
            keeps the clickable badge and the typed command in lock
            step without either one owning the other's state twice."""
            try:
                footer = self.query_one(ComposerFooter)
                footer.notebook_mode = mode_key
                footer.query_one("#badge-notebook").update(footer._mode_badge_markup(mode_key))
            except Exception:
                pass
            all_mode_classes = ["cct-mode-notebook", "cct-mode-research", "cct-mode-plan",
                                "cct-mode-build", "cct-mode-debugger", "cct-mode-agent"]
            for c in all_mode_classes:
                if c in self.classes:
                    self.remove_class(c)'''

new_set_model = '''        def set_model_label(self, label):
            self._model_label = label
            self._update_context_bar()
            try:
                self.query_one(ComposerFooter).set_model_label(label)
            except Exception:
                pass

        def set_ai_mode(self, mode_key):
            """Syncs the mode badge after a `/mode`, `/agent`,
            `/build`, `/plan`, or `/notebook` command switches mode."""
            self.notebook_mode = mode_key
            self._update_context_bar()
            try:
                footer = self.query_one(ComposerFooter)
                footer.notebook_mode = mode_key
            except Exception:
                pass
            all_mode_classes = ["cct-mode-notebook", "cct-mode-research", "cct-mode-plan",
                                "cct-mode-build", "cct-mode-debugger", "cct-mode-agent"]
            for c in all_mode_classes:
                if c in self.classes:
                    self.remove_class(c)'''

if old_set_model in text:
    text = text.replace(old_set_model, new_set_model)
    print("Replaced set_model_label and set_ai_mode in composer.py")
else:
    print("old_set_model NOT found in composer.py")

with open('calc_terminal/ui/composer.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Finished patching composer.py")
