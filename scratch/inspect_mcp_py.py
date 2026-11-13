import os

with open("calc_terminal/mcp.py", "r", encoding="utf-8", errors="replace") as f:
    lines = f.readlines()
for i, l in enumerate(lines[:100]):
    if l.startswith("def ") or l.startswith("class ") or l.strip().startswith("#"):
        print(f"{i+1:3d}: {l.strip()[:90]}")

