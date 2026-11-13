import sys

with open('calc_terminal/ui/footer.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'def on_resize' in line or 'def _compact' in line or 'def refresh' in line:
        for j in range(max(0, i-2), min(len(lines), i + 40)):
            sys.stdout.buffer.write(f"{j+1}: {lines[j]}".encode('utf-8'))
        break

