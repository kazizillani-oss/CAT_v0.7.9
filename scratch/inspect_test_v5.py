import sys
with open('calc_terminal/tests/test_v5_3d_cursor_and_floating.py', 'r', encoding='utf-8') as f:
    text = f.read()

sys.stdout.buffer.write(text[:2000].encode('utf-8'))
