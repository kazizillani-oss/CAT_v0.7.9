with open("calc_terminal/ui/app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i in range(7910, 8360):
    if "Unknown command" in lines[i]:
        print(f"Line {i+1}: {lines[i].strip()}")

