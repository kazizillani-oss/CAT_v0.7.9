import sys

for path in ['calc_terminal/ui/app.py', 'calc_terminal/ui/theme_css.py']:
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    for i, line in enumerate(text.splitlines()):
        if 'cct-header-explorer-btn' in line:
            sys.stdout.buffer.write(f"{path}:{i+1}: {line}\n".encode('utf-8'))

