import re

for w in [100, 50]:
    with open(f"scratch/prototype_{w}.svg", encoding="utf-8") as f:
        svg = f.read()
    print(f"=== WIDTH {w} ===")
    lines_dict = {}
    for match in re.finditer(r'<text[^>]*clip-path="url\(#[^)]+-line-(\d+)\)"[^>]*>(.*?)</text>', svg):
        line_idx = int(match.group(1))
        text_content = match.group(2)
        lines_dict.setdefault(line_idx, []).append(text_content)
    for idx in sorted(lines_dict.keys())[14:22]:
        line = "".join(lines_dict[idx]).encode("ascii", errors="replace").decode("ascii")
        print(f'{idx}: "{line}"')
