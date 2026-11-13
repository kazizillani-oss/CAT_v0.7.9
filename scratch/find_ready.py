import os

for root, dirs, files in os.walk("calc_terminal"):
    for f in files:
        if f.endswith(".py"):
            p = os.path.join(root, f)
            with open(p, "r", encoding="utf-8", errors="replace") as file:
                lines = file.readlines()
                for i, l in enumerate(lines):
                    if "READY" in l or "ready" in l.lower() and "banner" in l.lower():
                        if "figlet" in l.lower() or "ascii" in l.lower() or "card" in l.lower() or "block" in l.lower() or "ready" in l:
                            print(f"{p}:{i+1}: {l.strip()[:100]}")

