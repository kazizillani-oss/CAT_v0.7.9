import sys
sys.stdout.reconfigure(encoding='utf-8')

with open("calc_terminal/tests/test_cat_greeting.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
for i in range(94, len(lines)):
    print(f"{i+1:3d}: {lines[i].rstrip()}")

