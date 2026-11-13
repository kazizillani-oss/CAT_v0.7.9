import os

def main():
    p = "calc_terminal/app.py"
    with open(p, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    skip_until_def = False
    skip_function = False

    # Functions to remove:
    decomm_funcs = {
        "def cmd_atomsim(self):",
        "def cmd_orbitals(self):",
        "def cmd_orbitalgrid(self):",
        'def cmd_bonding(self, arg=""):',
        "def cmd_graph(self):",
        "def cmd_kinetics(self):",
        "def cmd_electrochemistry(self):",
        "def cmd_game(self):",
        "def cmd_sim3d(self):",
        "def cmd_gpu3d(self):",
    }

    unused_imports = {
        "from . import atomsim\n",
        "from . import graphs\n",
        "from . import sim3d\n",
        "from . import gpu3d\n",
        "from . import game\n",
    }

    i = 0
    while i < len(lines):
        line = lines[i]

        # Skip decommissioned imports
        if line in unused_imports:
            i += 1
            continue

        # Check for function start to remove
        matched_func = None
        for func in decomm_funcs:
            if line.strip() == func:
                matched_func = func
                break

        if matched_func:
            # Skip this function definition and its body until the next top-level or method definition (indent <= 4)
            i += 1
            while i < len(lines):
                next_line = lines[i]
                stripped = next_line.strip()
                # Check if this is the start of the next method or comment banner
                if (next_line.startswith("    def ") or next_line.startswith("    class ") or
                    next_line.startswith("def ") or next_line.startswith("class ") or
                    (stripped.startswith("#") and any(w in stripped for w in ["---", "===", "history", "shortcuts", "formulas", "bloch", "ai"]))):
                    break
                i += 1
            continue

        # Clean help text
        if 'Try /kinetics, /formulas' in line:
            new_lines.append(line.replace('Try /kinetics, /formulas', 'Try /formulas, /solve'))
            i += 1
            continue

        if 'Try /atomsim, /orbitals, /bonding' in line:
            new_lines.append(line.replace('Try /atomsim, /orbitals, /bonding, or /export', 'Try /formulas, /solve, or /export'))
            i += 1
            continue

        if 'Inside /atomsim and /orbitals live views:' in line:
            new_lines.append(line.replace('Inside /atomsim and /orbitals live views:', 'Inside live views:'))
            i += 1
            continue

        # Skip LIVE SIMULATIONS block in help
        if 'lines.append(theme.purple("LIVE SIMULATIONS", bold=True))' in line:
            # skip the next 5 lines
            i += 5
            continue

        # Skip LEARN BY PLAYING block in help
        if 'lines.append(theme.purple("LEARN BY PLAYING", bold=True))' in line:
            # skip the next 4 lines
            i += 4
            continue

        new_lines.append(line)
        i += 1

    with open(p, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    print("app.py cleaned successfully. Total lines:", len(new_lines))

if __name__ == "__main__":
    main()

