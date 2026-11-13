import sys

with open('calc_terminal/ui/permission_panel.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i in range(min(120, len(lines))):
    sys.stdout.buffer.write(f"{i+1}: {lines[i]}".encode('utf-8'))

