with open("calc_terminal/ui/composer.py", "r", encoding="utf-8", errors="replace") as f:
    lines = f.readlines()
for i, l in enumerate(lines):
    if "_apply_compact_height" in l or "set_explicit_height" in l:
        print(f"{i+1:4d}: {l.strip()[:100]}")

