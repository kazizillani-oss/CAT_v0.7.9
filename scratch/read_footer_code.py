import sys

with open('calc_terminal/ui/footer.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'class ComposerFooter' in line:
        for j in range(i, min(len(lines), i + 70)):
            sys.stdout.buffer.write(f"{j+1}: {lines[j]}".encode('utf-8'))
        break
