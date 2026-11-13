import os

def clean_runtime():
    p = "calc_terminal/web/cat_runtime.py"
    with open(p, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    skip = 0
    for line in lines:
        if skip > 0:
            skip -= 1
            continue
        if 'if base in ("/atomsim"' in line:
            skip = 3
            continue
        if 'if base in ("/orbitals"' in line:
            skip = 3
            continue
        if 'if base in ("/graph"' in line:
            skip = 4
            continue
        if 'if base in ("/bonding"' in line:
            skip = 3
            continue
        new_lines.append(line)

    with open(p, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print("Cleaned cat_runtime.py")

def clean_thinking():
    p = "calc_terminal/ui/thinking.py"
    with open(p, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        if any(cmd in line for cmd in ['"/orbitals"', '"/atomsim"', '"/sim3d"', '"/graph"']):
            continue
        new_lines.append(line)

    with open(p, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print("Cleaned thinking.py")

if __name__ == "__main__":
    clean_runtime()
    clean_thinking()

