# scratch/fix_app_css_clean.py
with open('calc_terminal/ui/app.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace broken PowerShell interpolations
text = text.replace('color: ;\n    background: -alt;', 'color: $accent;\n    background: $surface-alt;')
text = text.replace('color: ;\n    border: none;', 'color: $accent;\n    border: none;')
text = text.replace('background:  30%;', 'background: $accent 30%;')
text = text.replace('background:  50%;', 'background: $accent 50%;')

with open('calc_terminal/ui/app.py', 'w', encoding='utf-8', newline='') as f:
    f.write(text)

print('Repaired app.py variables')

