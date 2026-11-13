with open('calc_terminal/ui/theme_css.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re
matches = re.findall(r'([^{}]*(?:prompt|editor-stack|cct-input|ComposerInput)[^{]*\{[^}]*\})', text)
for m in matches:
    print("Match in theme_css.py:")
    print(m)
    print("---")

