import sys
sys.stdout.reconfigure(encoding='utf-8')

with open("calc_terminal/ui/app.py", "r", encoding="utf-8", errors="replace") as f:
    for i, l in enumerate(f):
        if "from ..app import" in l or "from .. import app" in l or "App()" in l:
            print(f"{i+1:4d}: {l.strip()[:100]}")

