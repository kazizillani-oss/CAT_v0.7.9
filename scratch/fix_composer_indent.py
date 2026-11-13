with open(r'calc_terminal/ui/composer.py', 'r', encoding='utf-8') as f:
    text = f.read()

bad_block = """                def _on_palette_state_changed(self, is_open):
            if is_open:
                self.styles.height = "auto"
                self.styles.max_height = "85%"
            else:
                if self._explicit_height is None:
                    self.styles.height = "auto"
                    self.styles.max_height = "32%"
                else:
                    self.styles.height = self._explicit_height
                    self.styles.max_height = "100%"

def _on_permission_panel_toggled(self, is_open):"""

good_block = """        def _on_palette_state_changed(self, is_open):
            if is_open:
                self.styles.height = "auto"
                self.styles.max_height = "85%"
            else:
                if self._explicit_height is None:
                    self.styles.height = "auto"
                    self.styles.max_height = "32%"
                else:
                    self.styles.height = self._explicit_height
                    self.styles.max_height = "100%"

        def _on_permission_panel_toggled(self, is_open):"""

if bad_block in text:
    text = text.replace(bad_block, good_block)
    with open(r'calc_terminal/ui/composer.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Fixed composer.py indentation!")
else:
    # Try normalizing CRLF
    text_n = text.replace('\r\n', '\n')
    bad_n = bad_block.replace('\r\n', '\n')
    good_n = good_block.replace('\r\n', '\n')
    if bad_n in text_n:
        text_n = text_n.replace(bad_n, good_n)
        with open(r'calc_terminal/ui/composer.py', 'w', encoding='utf-8') as f:
            f.write(text_n)
        print("Fixed composer.py indentation with newline normalization!")
    else:
        print("Could not find bad_block in composer.py")

