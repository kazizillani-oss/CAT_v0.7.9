import sys, re

with open('calc_terminal/ui/app.py', 'r', encoding='utf-8') as f:
    app_text = f.read()

print("=== PORTRAIT RULES IN app.py ===")
for m in re.finditer(r'([^{}]*portrait[^{]*\{[^}]*\})', app_text, re.IGNORECASE):
    block = m.group(0)
    if 'header' in block or 'menu' in block or 'logo' in block or 'perm' in block:
        sys.stdout.buffer.write((block + '\n---\n').encode('utf-8'))

with open('calc_terminal/ui/theme_css.py', 'r', encoding='utf-8') as f:
    theme_text = f.read()

print("=== PORTRAIT RULES IN theme_css.py ===")
for m in re.finditer(r'([^{}]*portrait[^{]*\{[^}]*\})', theme_text, re.IGNORECASE):
    block = m.group(0)
    if 'header' in block or 'menu' in block or 'logo' in block or 'perm' in block:
        sys.stdout.buffer.write((block + '\n---\n').encode('utf-8'))

