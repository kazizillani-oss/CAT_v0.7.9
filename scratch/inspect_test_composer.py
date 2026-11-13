import sys
with open('calc_terminal/tests/test_composer_3d_and_dialog_fixes.py', 'r', encoding='utf-8') as f:
    text = f.read()

sys.stdout.buffer.write(text.encode('utf-8'))

