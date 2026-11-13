# scratch/patch_btn_security.py
with open('calc_terminal/ui/composer.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''            elif bid == "btn-attach":
                try:
                    self.app.action_prompt_attach()
                except Exception:
                    pass'''

replacement = '''            elif bid == "btn-attach":
                try:
                    self.app.action_prompt_attach()
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

if target in text:
    text = text.replace(target, replacement, 1)
    with open('calc_terminal/ui/composer.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Added security and voice button handlers to composer.py")
else:
    print("Target not found in composer.py")

