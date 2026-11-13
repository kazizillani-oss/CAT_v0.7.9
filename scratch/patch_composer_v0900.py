# scratch/patch_composer_v0900.py
import re
import os

print("Applying v0.9.000 Master Composer & UI Patch...")

# 1. Patch calc_terminal/ui/footer.py
footer_path = 'calc_terminal/ui/footer.py'
with open(footer_path, 'r', encoding='utf-8') as f:
    f_content = f.read()

# Replace compose method in ComposerFooter
old_footer_compose_regex = re.compile(
    r'def compose\(self\):.*?# ── BOTTOM RIGHT: microphone \+ Send/Stop.*?classes="cct-ctl-send", tooltip="Send message \(Enter\)"\)',
    re.DOTALL
)

new_footer_compose = '''def compose(self):
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

if old_footer_compose_regex.search(f_content):
    f_content = old_footer_compose_regex.sub(new_footer_compose, f_content)
    print("Patched footer.py compose method via regex")
else:
    print("Warning: regex did not match footer.py compose, trying alternate replacement")

# Update on_resize in footer to handle new buttons
old_footer_resize = '''            try:
                attach_btn = self.query_one("#btn-attach", Button)
                mic_btn = self.query_one("#btn-mic", Button)
                send_btn = self.query_one("#btn-send", Button)
                attach_btn.display = True
                mic_btn.display = True
                send_btn.display = True
            except Exception:
                pass'''

new_footer_resize = '''            try:
                attach_btn = self.query_one("#btn-attach", Button)
                perm_btn = self.query_one("#btn-permissions", Button)
                sec_btn = self.query_one("#btn-security", Button)
                mic_btn = self.query_one("#btn-mic", Button)
                send_btn = self.query_one("#btn-send", Button)
                attach_btn.display = True
                perm_btn.display = (w >= 45)
                sec_btn.display = (w >= 60)
                mic_btn.display = True
                send_btn.display = True
            except Exception:
                pass'''

if old_footer_resize in f_content:
    f_content = f_content.replace(old_footer_resize, new_footer_resize)
    print("Patched footer.py on_resize method")

with open(footer_path, 'w', encoding='utf-8') as f:
    f.write(f_content)

print("Updated footer.py written.")

