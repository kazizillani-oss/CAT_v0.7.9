from pathlib import Path

# 1. Add footer.py to sync_all_targets.py
sync_path = Path('scratch/sync_all_targets.py')
stext = sync_path.read_text(encoding='utf-8')
if 'os.path.join("ui", "footer.py"),' not in stext:
    stext = stext.replace(
        'os.path.join("ui", "composer.py"),',
        'os.path.join("ui", "composer.py"),\n    os.path.join("ui", "footer.py"),'
    )
    sync_path.write_text(stext, encoding='utf-8')
    print("Added footer.py to sync_all_targets.py!")

# 2. Fix app.py _COMPONENT_CSS for #cct-bottom-row and 3D buttons
app_path = Path('calc_terminal/ui/app.py')
with open(app_path, 'r', encoding='utf-8', newline='') as f:
    app_text = f.read()

app_text_norm = app_text.replace('\r\n', '\n')

old_app_bottom_row = """#cct-bottom-row {
    height: auto;
    min-height: 1;
    max-height: 2;
    margin: 0;
    padding: 0 1;
    layout: horizontal;
    align-vertical: middle;
    border: none;
    background: transparent;
    overflow: hidden;
}"""

new_app_bottom_row = """#cct-bottom-row {
    height: 3;
    min-height: 3;
    max-height: 3;
    margin: 0;
    padding: 0 1;
    layout: horizontal;
    align-vertical: middle;
    border-top: solid #24283b;
    background: #161722;
    overflow: hidden;
}"""

if old_app_bottom_row in app_text_norm:
    app_text_norm = app_text_norm.replace(old_app_bottom_row, new_app_bottom_row, 1)
    print("Fixed #cct-bottom-row in app.py!")

# Replace flat button styles in app.py with 3D mechanical button styles
old_btn_block = """Button.cct-icon-btn,
Button#btn-permissions,
Button#btn-attach,
Button.cct-icon-send,
Button#btn-send {
    offset: 0 0;
    offset-x: 0;
    offset-y: 0;
    transition: none;
    border: none;
    height: 1;
    min-height: 1;
    max-height: 1;
}

Button.cct-icon-btn, Button#btn-permissions {
    background: transparent;
    color: $text;
    border: none;
    min-width: 4;
    width: auto;
    height: 1;
    min-height: 1;
    max-height: 1;
    padding: 0 1;
    margin: 0;
    content-align: center middle;
    text-style: bold;
}
Button#btn-attach {
    background: transparent;
    color: $text;
    border: none;
    min-width: 4;
    width: auto;
    height: 1;
    min-height: 1;
    max-height: 1;
    padding: 0 1;
    margin: 0;
    content-align: center middle;
    text-style: bold;
}
Button.cct-icon-btn:hover, Button#btn-permissions:hover, Button#btn-attach:hover {
    color: #ffffff;
    background: $accent 35%;
    text-style: bold;
    border: none;
}
Button.cct-icon-btn:focus, Button#btn-permissions:focus, Button#btn-attach:focus {
    color: $accent-highlight;
    background: $surface-highlight 40%;
    text-style: bold;
    border: none;
}
Button.cct-icon-btn.-active, Button#btn-permissions.-active, Button#btn-attach.-active {
    background: $accent;
    color: #ffffff;
    border: none;
    offset: 0 0;
}

Button.cct-icon-send, Button#btn-send {
    color: $accent;
    text-style: bold;
    border: none;
    min-width: 4;"""

new_btn_block = """Button.cct-icon-btn,
Button#btn-permissions,
Button#btn-attach,
Button.cct-icon-send,
Button#btn-send {
    height: 3;
    min-height: 3;
    max-height: 3;
    width: 5;
    min-width: 5;
    max-width: 5;
    padding: 0;
    margin: 0;
    content-align: center middle;
    offset: 0 0;
}

Button#btn-permissions {
    background: transparent;
    color: $accent;
    border: tall;
    border-top: tall #6b7596;
    border-left: tall #565f7c;
    border-bottom: tall #0e0f17;
    border-right: tall #13141f;
}
Button#btn-attach {
    background: transparent;
    color: $accent;
    border: tall;
    border-top: tall #6b7596;
    border-left: tall #565f7c;
    border-bottom: tall #0e0f17;
    border-right: tall #13141f;
    margin-left: 1;
}
Button.cct-icon-btn:hover, Button#btn-permissions:hover, Button#btn-attach:hover {
    color: #ffffff;
    background: $accent 24%;
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-bottom: tall $accent-darken-3;
    border-right: tall $accent-darken-2;
}
Button.cct-icon-btn:focus, Button#btn-permissions:focus, Button#btn-attach:focus,
Button.cct-icon-btn.-active, Button#btn-permissions.-active, Button#btn-attach.-active {
    background: #12131c;
    border-top: tall #0e0f17;
    border-left: tall #13141f;
    border-bottom: tall #6b7596;
    border-right: tall #565f7c;
}

Button.cct-icon-send, Button#btn-send {
    background: #e0af68;
    color: #12131d;
    text-style: bold;
    border: tall;
    border-top: tall #ffeaa7;
    border-left: tall #f7d794;
    border-bottom: tall #78350f;
    border-right: tall #92400e;
    margin-left: 1;
    min-width: 5;"""

if old_btn_block in app_text_norm:
    app_text_norm = app_text_norm.replace(old_btn_block, new_btn_block, 1)
    print("Fixed 3D button keycaps in app.py!")

with open(app_path, 'w', encoding='utf-8', newline='') as f:
    f.write(app_text_norm.replace('\n', '\r\n'))

# 3. Ensure calc_terminal/ui/footer.py has model_badge.display = True at all widths
foot_path = Path('calc_terminal/ui/footer.py')
with open(foot_path, 'r', encoding='utf-8', newline='') as f:
    foot_text = f.read()

foot_text_norm = foot_text.replace('\r\n', '\n')

old_foot_code = """                model_badge = self.query_one("#badge-model", _Badge)
                sep = self.query_one(".cct-badge-sep", Static)
                if w < 55:
                    model_badge.display = False
                    sep.display = False"""

new_foot_code = """                model_badge = self.query_one("#badge-model", _Badge)
                sep = self.query_one(".cct-badge-sep", Static)
                model_badge.display = True
                sep.display = True
                if w < 55:"""

if old_foot_code in foot_text_norm:
    foot_text_norm = foot_text_norm.replace(old_foot_code, new_foot_code, 1)
    with open(foot_path, 'w', encoding='utf-8', newline='') as f:
        f.write(foot_text_norm.replace('\n', '\r\n'))
    print("Fixed footer.py model_badge display!")

print("All pre-sync fixes completed.")

