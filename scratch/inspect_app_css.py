with open("calc_terminal/ui/app.py", "r", encoding="utf-8", errors="replace") as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if "cct-brandheader" in line or "cct-perm-pill" in line or "cct-header" in line or "cct-menubutton" in line:
        print(f"{i+1:4d}: {line.rstrip()[:120]}")

