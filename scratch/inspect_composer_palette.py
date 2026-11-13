with open("calc_terminal/ui/composer.py", "r", encoding="utf-8", errors="replace") as f:
    lines = f.readlines()
for i, l in enumerate(lines):
    if "palette" in l.lower() or "cmdpalette" in l.lower():
        print(f"{i+1:4d}: {l.strip()[:100]}")

