import sys
sys.stdout.reconfigure(encoding='utf-8')

with open("calc_terminal/ui/app.py", "r", encoding="utf-8", errors="replace") as f:
    for i, l in enumerate(f):
        if "def _handle_command" in l:
            print(f"{i+1:4d}: {l.strip()}")

