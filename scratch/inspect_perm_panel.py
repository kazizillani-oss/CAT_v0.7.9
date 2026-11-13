import sys

with open('calc_terminal/ui/permission_panel.py', 'r', encoding='utf-8') as f:
    text = f.read()

print("permission_panel.py length:", len(text))
for line in text.splitlines():
    if 'DEFAULT_CSS' in line or 'border' in line or 'class PermissionsSettingsPanel' in line:
        sys.stdout.buffer.write((line[:120] + '\n').encode('utf-8'))

