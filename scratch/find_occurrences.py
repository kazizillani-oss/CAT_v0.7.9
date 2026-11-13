import os

for root, dirs, files in os.walk("calc_terminal"):
    for f in files:
        if f.endswith((".py", ".tcss", ".css")):
            p = os.path.join(root, f)
            with open(p, "r", encoding="utf-8", errors="replace") as file:
                content = file.read()
                if "cct-perm-pill" in content or "cct-brandheader" in content:
                    print(f"Found in {p}")

