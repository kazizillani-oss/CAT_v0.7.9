import sys
import re
from collections import defaultdict

filename = sys.argv[1] if len(sys.argv) > 1 else 'scratch/test_agent_menu_render.svg'

with open(filename, 'r', encoding='utf-8') as f:
    text = f.read()

tags = re.findall(r'<text[^>]*y="([0-9\.]+)"[^>]*>(.*?)</text>', text)
lines = defaultdict(list)
for y, t in tags:
    clean = re.sub(r'<[^>]+>', '', t).replace('&#160;', ' ')
    lines[float(y)].append(clean)

for y in sorted(lines.keys())[:35]:
    row_text = ''.join(lines[y])
    if any(c.strip() for c in row_text):
        print(f'{y:5.1f}: {row_text}')
