import sys
sys.stdout.reconfigure(encoding='utf-8')

with open("calc_terminal/ui/app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i in range(8350, min(8385, len(lines))):
    print(f"{i+1:4d}: {lines[i].rstrip()}")

