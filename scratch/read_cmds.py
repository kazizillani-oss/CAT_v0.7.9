with open("calc_terminal/commands_data.py", "r", encoding="utf-8", errors="replace") as f:
    for i in range(50):
        l = f.readline()
        if not l: break
        print(f"{i+1:3d}: {l.rstrip()}")

