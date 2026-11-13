import sys
sys.stdout.reconfigure(encoding='utf-8')

with open("calc_terminal/ui/extensions_panel.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i in range(750, min(860, len(lines))):
    print(f"{i+1:3d}: {lines[i].rstrip()}")

