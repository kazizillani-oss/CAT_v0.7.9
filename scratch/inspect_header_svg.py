import sys

with open('scratch/live_header_landscape_verified.svg', 'r', encoding='utf-8') as f:
    text = f.read()

print("SVG length:", len(text))
for line in text.splitlines():
    if '<text' in line:
        sys.stdout.buffer.write((line[:120] + '\n').encode('utf-8'))
