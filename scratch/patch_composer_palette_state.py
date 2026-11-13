with open(r"calc_terminal/ui/composer.py", "r", encoding="utf-8") as f:
    text = f.read()

target = """        def _on_palette_state_changed(self, is_open):
            if is_open:
                self.styles.height = "auto"
                self.styles.max_height = "85%"
            else:
                if self._explicit_height is None:
                    self.styles.height = "auto"
                    self.styles.max_height = "32%"
                else:
                    self.styles.height = self._explicit_height
                    self.styles.max_height = "100%\""""

replacement = """        def _on_palette_state_changed(self, is_open):
            try:
                editor = self.query_one("#cct-input", ComposerInput)
                stack = self.query_one("#cct-editor-stack", Container)
                row = self.query_one("#cct-prompt-row")
            except Exception:
                editor = stack = row = None

            if is_open:
                # Keep prompt row compact (1-2 lines for typed command like `> /`)
                line_count = max(1, min(3, editor.text.count("\\n") + 1)) if editor else 1
                if editor:
                    editor.styles.height = line_count
                if stack:
                    stack.styles.height = line_count
                if row:
                    row.styles.height = "auto"
                self.styles.height = "auto"
                self.styles.max_height = "55%"
            else:
                if self._explicit_height is None:
                    self.styles.height = "auto"
                    self.styles.max_height = "32%"
                    line_count = max(1, min(5, editor.text.count("\\n") + 1)) if editor else 1
                    if editor:
                        editor.styles.height = line_count
                    if stack:
                        stack.styles.height = line_count
                    if row:
                        row.styles.height = "auto"
                else:
                    self.styles.height = self._explicit_height
                    self.styles.max_height = "100%"
                    if editor:
                        editor.styles.height = "1fr"
                    if stack:
                        stack.styles.height = "1fr"
                    if row:
                        row.styles.height = "1fr\""""

text_n = text.replace('\r\n', '\n')
target_n = target.replace('\r\n', '\n')
replacement_n = replacement.replace('\r\n', '\n')

if target_n in text_n:
    text_n = text_n.replace(target_n, replacement_n)
    with open(r"calc_terminal/ui/composer.py", "w", encoding="utf-8") as f:
        f.write(text_n)
    print("Successfully patched calc_terminal/ui/composer.py")
else:
    print("Error: Target not found in composer.py")

