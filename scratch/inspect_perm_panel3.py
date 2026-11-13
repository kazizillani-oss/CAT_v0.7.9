import sys

with open('calc_terminal/ui/permission_panel.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i in range(120, min(len(lines), 200)):
    sys.stdout.buffer.write(f"{i+1}: {lines[i]}".encode('utf-8'))

