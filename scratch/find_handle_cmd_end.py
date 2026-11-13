import sys
sys.stdout.reconfigure(encoding='utf-8')

with open("calc_terminal/ui/app.py", "r", encoding="utf-8", errors="replace") as f:
    lines = f.readlines()
for i in range(7912, len(lines)):
    l = lines[i]
    if l.startswith("        def ") and not l.startswith("        def _handle_command"):
        print(f"End of _handle_command at line {i+1}: {l.strip()}")
        break
    if "unknown command" in l.lower() or "commands_registry" in l.lower() or "execute_command" in l.lower():
        print(f"{i+1:4d}: {l.strip()}")

