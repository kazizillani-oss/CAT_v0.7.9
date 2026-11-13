with open('calc_terminal/tests/test_composer_3d_and_dialog_fixes.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re
matches = re.findall(r'def test_[a-zA-Z0-9_]+\([^)]*\):.*?(?=def test_|\Z)', text, re.DOTALL)
for m in matches:
    first_line = m.strip().splitlines()[0]
    print(first_line)
    for line in m.splitlines():
        if 'assert' in line and ('#' in line or 'border' in line or 'height' in line or 'width' in line):
            print("  ", line.strip())

