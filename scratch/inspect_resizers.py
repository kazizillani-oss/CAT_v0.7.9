import sys

with open('calc_terminal/ui/resizers.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, l in enumerate(lines[:30]):
    sys.stdout.buffer.write(f"{i+1}: {l}".encode('utf-8'))

