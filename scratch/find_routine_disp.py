import sys
sys.stdout.reconfigure(encoding='utf-8')

with open("calc_terminal/ui/cat_greeting.py", "r", encoding="utf-8", errors="replace") as f:
    for i, l in enumerate(f):
        if "def get_cat_routine_display" in l:
            print(f"Line {i+1}: {l.strip()}")

