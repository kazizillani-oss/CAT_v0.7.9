import sys

with open('calc_terminal/ui/header.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i in range(1155, min(len(lines), 1215)):
    sys.stdout.buffer.write(f"{i+1}: {lines[i]}".encode('utf-8'))

