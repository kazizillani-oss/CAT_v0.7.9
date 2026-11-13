import sys
sys.stdout.reconfigure(encoding='utf-8')

with open("calc_terminal/ui/app.py", "r", encoding="utf-8", errors="replace") as f:
    lines = f.readlines()
for i in range(7911, 8375):
    l = lines[i].strip()
    if l.startswith("if word") or l.startswith("elif word") or "in word" in l or l.startswith("if parts[0]") or l.startswith("elif parts[0]"):
        print(f"{i+1:4d}: {l}")

