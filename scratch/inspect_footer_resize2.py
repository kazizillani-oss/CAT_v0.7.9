import sys

with open('calc_terminal/ui/footer.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for j in range(215, min(len(lines), 260)):
    sys.stdout.buffer.write(f"{j+1}: {lines[j]}".encode('utf-8'))

