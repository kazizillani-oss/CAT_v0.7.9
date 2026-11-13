import sys

with open('calc_terminal/ui/resizers.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, l in enumerate(lines[30:70]):
    sys.stdout.buffer.write(f"{i+31}: {l}".encode('utf-8'))

