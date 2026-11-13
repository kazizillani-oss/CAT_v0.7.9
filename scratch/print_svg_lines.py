with open("scratch/3d_input_area_and_header_verified.svg", "r", encoding="utf-8") as f:
    svg = f.read()

import re
lines = {}
for m in re.finditer(r'clip-path="url\(#terminal-[0-9]+-line-([0-9]+)\)"[^>]*>(.*?)</text>', svg):
    line_no = int(m.group(1))
    text = m.group(2)
    lines.setdefault(line_no, []).append(text)

for k in sorted(lines.keys()):
    combined = "".join(lines[k]).replace("&#160;", " ")
    print(f"Line {k:2d}: {combined}")

