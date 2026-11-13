with open("calc_terminal/ui/app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i, l in enumerate(lines):
    if "def _run_in_suspended_terminal" in l:
        print(f"Line {i+1}: {l.strip()}")

