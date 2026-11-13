with open("calc_terminal/cli_commands.py", "r", encoding="utf-8", errors="replace") as f:
    for i in range(80):
        l = f.readline()
        if not l: break
        print(f"{i+1:3d}: {l.rstrip()}")

