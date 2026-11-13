import os

def check_palette(path):
    print(f"=== {path} ===")
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    for i, l in enumerate(lines):
        if "cct-cmdpalette" in l or "cct-cmd-row" in l:
            print(f"{i+1:4d}: {l.strip()[:100]}")

check_palette("calc_terminal/ui/theme_css.py")
check_palette("calc_terminal/ui/app.py")

