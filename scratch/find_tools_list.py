import sys
sys.stdout.reconfigure(encoding='utf-8')

with open("calc_terminal/agent.py", "r", encoding="utf-8", errors="replace") as f:
    for i, l in enumerate(f):
        if "TOOLS =" in l or "TOOL_SPECS =" in l or "DEFAULT_TOOLS =" in l or "def get_tools" in l:
            print(f"Line {i+1}: {l.strip()[:100]}")

