import sys
sys.stdout.reconfigure(encoding='utf-8')

import os

for root, dirs, files in os.walk("calc_terminal"):
    for f in files:
        if f.endswith(".py"):
            p = os.path.join(root, f)
            with open(p, "r", encoding="utf-8", errors="replace") as file:
                content = file.read()
                if "def handle_solve" in content or "word == \"/solve\"" in content or "word in (\"/solve\"" in content or "cmd == \"/solve\"" in content:
                    print(f"Found /solve handler in {p}")
                if "def handle_calculator" in content or "word == \"/calculator\"" in content or "cmd == \"/calculator\"" in content:
                    print(f"Found /calculator handler in {p}")

