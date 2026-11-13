import sys
sys.stdout.reconfigure(encoding='utf-8')

for p in ["calc_terminal/agent.py", "calc_terminal/ui/app.py"]:
    print(f"=== {p} ===")
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        for i, l in enumerate(f):
            if "install" in l.lower() and ("tool" in l.lower() or "skill" in l.lower() or "package" in l.lower()):
                if "def " in l or "class " in l or "if " in l:
                    print(f"{i+1:4d}: {l.strip()[:100]}")

