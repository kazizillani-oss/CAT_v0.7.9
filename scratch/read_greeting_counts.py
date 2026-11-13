with open("calc_terminal/ui/cat_greeting.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i, l in enumerate(lines[:30]):
    print(f"{i+1:3d}: {l.rstrip()}")
print(f"Total lines: {len(lines)}")

