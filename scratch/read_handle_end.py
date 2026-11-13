with open("calc_terminal/ui/app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i in range(8319, 8345):
    print(f"{i+1:4d}: {lines[i].rstrip()}")

