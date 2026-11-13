import glob, sys

for p in ['calc_terminal/ui/app.py', 'calc_terminal/ui/theme_css.py', 'calc_terminal/ui/composer.py', 'calc_terminal/tests/test_composer_3d_and_dialog_fixes.py']:
    with open(p, 'r', encoding='utf-8') as f:
        text = f.read()
    for i, l in enumerate(text.splitlines()):
        if 'COMPOSER_MIN_HEIGHT' in l or 'min_height' in l or 'min-height: 8' in l:
            sys.stdout.buffer.write(f"{p}:{i+1}: {l}\n".encode('utf-8'))

