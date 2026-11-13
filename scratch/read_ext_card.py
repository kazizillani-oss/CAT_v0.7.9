with open("calc_terminal/ui/extensions_panel.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i in range(55, 165):
    print(f"{i+1:3d}: {lines[i].rstrip()}")

