import sys

with open('calc_terminal/ui/composer.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'class StickyComposer' in line:
        for j in range(i, min(len(lines), i + 60)):
            if 'def compose(' in lines[j]:
                for k in range(j, min(len(lines), j + 40)):
                    sys.stdout.buffer.write(f"{k+1}: {lines[k]}".encode('utf-8'))
                break
        break

