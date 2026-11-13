import os, sys

def search_file(filepath, keywords):
    print(f"=== Searching in {filepath} ===")
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        for kw in keywords:
            if kw.lower() in line.lower():
                print(f"{i+1:4d}: {line.rstrip()[:120]}")
                break

if __name__ == "__main__":
    search_file("calc_terminal/ui/theme_css.py", ["#cct-brandheader", "cct-perm-pill", "cct-menubutton", "is-portrait", "is-floating", "ready", "cct-empty"])

