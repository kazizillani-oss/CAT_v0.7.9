import sys

with open('calc_terminal/ui/workspace.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, l in enumerate(lines):
    if 'class WorkspaceShell' in l:
        for j in range(i, min(len(lines), i + 65)):
            sys.stdout.buffer.write(f"{j+1}: {lines[j]}".encode('utf-8'))
        break

