with open("calc_terminal/mcp.py", "r", encoding="utf-8", errors="replace") as f:
    for i, l in enumerate(f):
        if l.startswith("def ") or l.startswith("class "):
            print(f"{i+1:4d}: {l.strip()}")

