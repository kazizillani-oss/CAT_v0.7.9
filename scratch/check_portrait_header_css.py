with open("calc_terminal/ui/app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i in range(2230, 2275):
    if i < len(lines):
        print(f"{i+1:4d}: {lines[i].rstrip()}")

