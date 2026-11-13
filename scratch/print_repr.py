with open("calc_terminal/ui/app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i in range(1298, 1330):
    print(f"{i+1:4d}: {repr(lines[i])}")

