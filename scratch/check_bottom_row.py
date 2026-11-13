import re

for path in ['calc_terminal/ui/app.py', 'calc_terminal/ui/theme_css.py']:
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    m = re.search(r'#cct-bottom-row\s*\{[^}]+\}', text)
    if m:
        print(f"=== {path} ===")
        print(m.group(0))
    else:
        print(f"=== {path}: #cct-bottom-row NOT found ===")

