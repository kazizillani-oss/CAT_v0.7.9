with open('calc_terminal/ui/theme_css.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re
matches = re.findall(r'([^{}]*(?:editor-stack|cct-input|ComposerInput|TextArea)[^{]*\{[^}]*\})', text)
for m in matches:
    print("Match:")
    print(m)
    print("---")

