with open('scratch/test_composer_w50.svg', 'r', encoding='utf-8') as f:
    text = f.read()

import re
chars = re.findall(r'<text[^>]*x="([0-9\.]+)"[^>]*y="([0-9\.]+)"[^>]*>(.*?)</text>', text)
left_chars = [c for c in chars if float(c[0]) < 25]
for x, y, ch in sorted(left_chars, key=lambda c: float(c[1])):
    print(f'y={float(y):5.1f}, x={float(x):4.1f}: {ch}')

