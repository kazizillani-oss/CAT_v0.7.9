import sys
sys.stdout.reconfigure(encoding='utf-8')

with open("calc_terminal/app.py", "r", encoding="utf-8", errors="replace") as f:
    for i, l in enumerate(f):
        if "/solve" in l or "/calculator" in l or "/kinetics" in l or "/orbitals" in l:
            print(f"{i+1:4d}: {l.strip()[:100]}")

