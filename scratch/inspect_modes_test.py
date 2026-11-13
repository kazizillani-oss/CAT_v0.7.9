import sys

with open('calc_terminal/tests/test_composer_3d_and_dialog_fixes.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, l in enumerate(lines):
    if 'test_all_ai_modes' in l:
        for j in range(i, min(len(lines), i + 40)):
            sys.stdout.buffer.write(f"{j+1}: {lines[j]}".encode('utf-8'))
        break

