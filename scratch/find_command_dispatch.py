import sys, os
sys.stdout.reconfigure(encoding='utf-8')

for path in ["calc_terminal/commands_registry.py", "calc_terminal/app.py"]:
    print(f"=== {path} ===")
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for i, l in enumerate(f):
            if "def handle_command" in l or "def execute_command" in l or "def dispatch_command" in l or "CommandExecuted" in l:
                print(f"{i+1:4d}: {l.strip()}")

