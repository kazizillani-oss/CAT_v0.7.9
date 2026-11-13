import sys
sys.stdout.reconfigure(encoding='utf-8')

with open("calc_terminal/agents/builtin_agents.py", "r", encoding="utf-8", errors="replace") as f:
    for i, l in enumerate(f):
        if "tools=" in l.lower() or "tools:" in l.lower() or "capabilities=" in l.lower():
            print(f"Line {i+1}: {l.strip()[:100]}")

