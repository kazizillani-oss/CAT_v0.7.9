with open('calc_terminal/ui/app.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re
matches = re.findall(r'([^{}]*menu-btn[^{]*\{[^}]*\})', text)
for m in matches:
    print(m)
    print("---")

