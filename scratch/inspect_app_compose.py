import sys

with open('calc_terminal/ui/app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, l in enumerate(lines):
    if 'def compose(' in l:
        for j in range(i, min(len(lines), i + 45)):
            sys.stdout.buffer.write(f"{j+1}: {lines[j]}".encode('utf-8'))
        break

