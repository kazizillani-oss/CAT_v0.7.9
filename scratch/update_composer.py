# scratch/update_composer.py
with open('calc_terminal/ui/composer.py', 'r', encoding='utf-8') as f:
    code = f.read()

old_palette_changed = """        def _on_palette_state_changed(self, is_open):
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
                self.styles.max_height = "42%"
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
                        row.styles.height = "1fr" """

# Let's inspect the exact lines in composer.py with repr to ensure exact match
lines = code.splitlines(keepends=True)
start_idx = None
end_idx = None
for i, l in enumerate(lines):
    if "def _on_palette_state_changed" in l:
        start_idx = i
    if start_idx is not None and "def _on_permission_panel_toggled" in l:
        end_idx = i
        break

assert start_idx is not None and end_idx is not None

new_chunk = """        def _on_palette_state_changed(self, is_open):
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
                # Reset min_height to 0 so dragged explicit height doesn't leave an empty void
                self.styles.min_height = 0
                self.styles.height = "auto"
                self.styles.max_height = "55%"
            else:
                if self._explicit_height is None:
                    self.styles.min_height = 0
                    self.styles.height = "auto"
                    self.styles.max_height = "36%"
                    line_count = max(2, min(6, editor.text.count("\\n") + 1)) if editor else 2
                    if editor:
                        editor.styles.height = line_count
                    if stack:
                        stack.styles.height = line_count
                    if row:
                        row.styles.height = "auto"
                else:
                    self.styles.min_height = self._explicit_height
                    self.styles.height = self._explicit_height
                    self.styles.max_height = "100%"
                    if editor:
                        editor.styles.height = "1fr"
                    if stack:
                        stack.styles.height = "1fr"
                    if row:
                        row.styles.height = "1fr"\n\n"""

lines[start_idx:end_idx] = [new_chunk]
with open('calc_terminal/ui/composer.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("composer.py updated successfully!")

