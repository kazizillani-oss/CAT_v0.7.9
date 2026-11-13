import sys
sys.stdout.reconfigure(encoding='utf-8')

with open("calc_terminal/agent.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i in range(1800, 1850):
    print(f"{i+1:4d}: {lines[i].rstrip()}")

