# scratch/update_app_and_theme_css.py
import re

# ----------------- 1. Update app.py -----------------
with open('calc_terminal/ui/app.py', 'r', encoding='utf-8') as f:
    app_code = f.read()

# Replace composer block in app.py
old_composer_block = """#cct-composer {
    background: #181926;
    border: tall;
    border-top: tall #565f7c;
    border-left: tall #414868;
    border-bottom: tall #0d0e15;
    border-right: tall #12131d;
    tint: transparent;
    padding: 0;
    margin: 0 1 1 1;
    height: auto;
    min-height: 0;
    max-height: 75%;
    width: 1fr;
    layout: vertical;
    transition: border 120ms, tint 120ms;
}
#cct-composer:hover {
    tint: transparent;
}
#cct-composer:focus-within {
    background: #181926;
    border: tall;
    border-top: tall #f7d794;
    border-left: tall #e0af68;
    border-bottom: tall #0d0e15;
    border-right: tall #12131d;
    tint: transparent;
}"""

new_composer_block = """#cct-composer {
    background: #181926;
    border: heavy;
    border-top: heavy #6b7596;
    border-left: heavy #565f7c;
    border-bottom: heavy #24283b;
    border-right: heavy #2a2e42;
    tint: transparent;
    padding: 0;
    margin: 0 1 1 1;
    height: auto;
    min-height: 0;
    max-height: 75%;
    width: 1fr;
    layout: vertical;
    transition: border 120ms, tint 120ms;
}
#cct-composer:hover {
    tint: transparent;
}
#cct-composer:focus-within {
    background: #181926;
    border: heavy;
    border-top: heavy #f7d794;
    border-left: heavy #e0af68;
    border-bottom: heavy #24283b;
    border-right: heavy #2a2e42;
    tint: transparent;
}"""

if old_composer_block in app_code:
    app_code = app_code.replace(old_composer_block, new_composer_block, 1)

with open('calc_terminal/ui/app.py', 'w', encoding='utf-8') as f:
    f.write(app_code)

# ----------------- 2. Update theme_css.py -----------------
with open('calc_terminal/ui/theme_css.py', 'r', encoding='utf-8') as f:
    theme_code = f.read()

old_th_chassis = """#cct-composer {
    background: #181926;
    border: tall;
    border-top: tall #565f7c;
    border-left: tall #414868;
    border-bottom: tall #0d0e15;
    border-right: tall #12131d;
    tint: transparent;
    padding: 0;
    margin: 0 1 1 1;
    transition: border 120ms, tint 120ms;
}
#cct-composer:hover {
    tint: transparent;
}
#cct-composer:focus-within {
    background: #181926;
    border: tall;
    border-top: tall #f7d794;
    border-left: tall #e0af68;
    border-bottom: tall #0d0e15;
    border-right: tall #12131d;
    tint: transparent;
}"""

new_th_chassis = """#cct-composer {
    background: #181926;
    border: heavy;
    border-top: heavy #6b7596;
    border-left: heavy #565f7c;
    border-bottom: heavy #24283b;
    border-right: heavy #2a2e42;
    tint: transparent;
    padding: 0;
    margin: 0 1 1 1;
    transition: border 120ms, tint 120ms;
}
#cct-composer:hover {
    tint: transparent;
}
#cct-composer:focus-within {
    background: #181926;
    border: heavy;
    border-top: heavy #f7d794;
    border-left: heavy #e0af68;
    border-bottom: heavy #24283b;
    border-right: heavy #2a2e42;
    tint: transparent;
}"""

if old_th_chassis in theme_code:
    theme_code = theme_code.replace(old_th_chassis, new_th_chassis, 1)

with open('calc_terminal/ui/theme_css.py', 'w', encoding='utf-8') as f:
    f.write(theme_code)

print("Updated border: heavy successfully!")
