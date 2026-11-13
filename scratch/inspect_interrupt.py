import sys

with open('calc_terminal/ui/composer.py', 'r', encoding='utf-8') as f:
    text = f.read()

for line in text.splitlines():
    if 'cct-btn-interrupt' in line or 'btn-stop' in line:
        sys.stdout.buffer.write((line + '\n').encode('utf-8'))

