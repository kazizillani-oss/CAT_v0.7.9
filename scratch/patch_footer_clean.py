# scratch/patch_footer_clean.py
with open('calc_terminal/ui/footer.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace 🕘 with ⏱
text = text.replace('Button(_safe_glyph("🕘", "(P)")', 'Button(_safe_glyph("⏱", "(P)")')

target_resize = '''        def on_resize(self, event=None):
            """Responsive footer collapse at narrow viewports: ensures send button never gets pushed off and controls never clip."""
            w = (event.size.width if event else None) or (self.size.width if self.size else 80)
            try:
                center = self.query_one("#cct-center-status", Static)
                center.display = (w >= 80)
                center.update(self._status_text(w))
            except Exception:
                pass
            try:
                model_badge = self.query_one("#badge-model", _Badge)
                sep = self.query_one(".cct-badge-sep", Static)
                model_badge.display = True
                sep.display = True
                if w < 55:
                    clean = self._shorten_model_label(self._model_label, w)
                    if len(clean) > 8:
                        clean = clean[:7] + "…"
                    model_badge.update(clean)
                elif w < 75:
                    clean = self._shorten_model_label(self._model_label, w)
                    if len(clean) > 12:
                        clean = clean[:11] + "…"
                    model_badge.update(clean)
                else:
                    display_label = self._shorten_model_label(self._model_label, w)
                    model_badge.update(display_label)
            except Exception:
                pass'''

new_resize = '''        def on_resize(self, event=None):
            """Responsive footer collapse at narrow viewports: ensures send button never gets pushed off and controls never clip."""
            w = (event.size.width if event else None) or (self.size.width if self.size else 80)
            try:
                center = self.query_one("#cct-center-status", Static)
                center.display = (w >= 80)
                center.update(self._status_text(w))
                spacer_r = self.query_one("#cct-footer-spacer-right", Static)
                spacer_r.display = (w >= 80)
            except Exception:
                pass
            try:
                model_badge = self.query_one("#badge-model", _Badge)
                sep = self.query_one(".cct-badge-sep", Static)
                model_badge.display = True
                sep.display = True
                if w < 42:
                    clean = self._shorten_model_label(self._model_label, w)
                    if len(clean) > 5:
                        clean = clean[:4] + "…"
                    model_badge.update(clean)
                elif w < 55:
                    clean = self._shorten_model_label(self._model_label, w)
                    if len(clean) > 8:
                        clean = clean[:7] + "…"
                    model_badge.update(clean)
                elif w < 75:
                    clean = self._shorten_model_label(self._model_label, w)
                    if len(clean) > 12:
                        clean = clean[:11] + "…"
                    model_badge.update(clean)
                else:
                    display_label = self._shorten_model_label(self._model_label, w)
                    model_badge.update(display_label)
            except Exception:
                pass
            try:
                send_btn = self.query_one("#btn-send", Button)
                attach_btn = self.query_one("#btn-attach", Button)
                perm_btn = self.query_one("#btn-permissions", Button)
                send_btn.display = True
                attach_btn.display = True
                perm_btn.display = True
            except Exception:
                pass'''

p = text.find('def on_resize')
p2 = text.find('class StatusLine')
text = text[:p] + new_resize.strip() + '\n\n    ' + text[p2:]

with open('calc_terminal/ui/footer.py', 'w', encoding='utf-8', newline='') as f:
    f.write(text)
print('Successfully updated footer.py')

