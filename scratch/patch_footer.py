with open('calc_terminal/ui/footer.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''        def compose(self):
            with Horizontal(id="cct-left-controls"):
                yield _Badge(self._mode_badge_markup(self.notebook_mode),
                             "badge-notebook", self._toggle_notebook)
                yield Static("\\u00b7", classes="cct-badge-sep")
                yield _Badge(self._model_label, "badge-model", self._open_model)
            yield Static(id="cct-footer-spacer-left")
            yield Static(self._status_text(), id="cct-center-status")
            yield Static(id="cct-footer-spacer-right")'''

replacement = '''        def compose(self):
            with Horizontal(id="cct-composer-left", classes="cct-toolbar-left"):
                yield Button(_safe_glyph("\U0001f517", "(+)"), id="btn-attach", classes="cct-icon-btn", tooltip="Attach file (Click / Alt+A)")
                yield Button(_safe_glyph("\u23f1", "(P)"), id="btn-permissions", classes="cct-icon-btn", tooltip="Permissions (Click / Alt+P)")
                yield Button(_safe_glyph("\U0001f6e1\ufe0f", "[S]"), id="btn-security", classes="cct-icon-btn", tooltip="Security mode (Click to cycle)")
            with Horizontal(id="cct-toolbar-center"):
                yield Static(self._status_text(), id="cct-center-status")
            with Horizontal(id="cct-right-controls", classes="cct-composer-right cct-toolbar-right"):
                yield Button(_safe_glyph("\U0001f399", "(V)"), id="btn-mic", classes="cct-icon-btn", tooltip="Real Voice mode (Click / /voice)")
                yield Button(_safe_glyph("\u25a0", "Stop"), id="btn-stop", classes="cct-icon-btn cct-btn-stop", tooltip="Stop response (Esc)")
                yield Button(_safe_glyph("\u27a4", ">"), id="btn-send", classes="cct-icon-btn cct-icon-send", tooltip="Send message (Enter)")

        def on_mount(self):
            try:
                self.query_one("#btn-stop", Button).display = False
            except Exception:
                pass'''

if target in text:
    new_text = text.replace(target, replacement)
    with open('calc_terminal/ui/footer.py', 'w', encoding='utf-8') as f:
        f.write(new_text)
    print("Successfully patched calc_terminal/ui/footer.py compose()")
else:
    print("Target not found in calc_terminal/ui/footer.py")
