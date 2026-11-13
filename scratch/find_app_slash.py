import sys
sys.stdout.reconfigure(encoding='utf-8')

with open("calc_terminal/ui/app.py", "r", encoding="utf-8", errors="replace") as f:
    for i, l in enumerate(f):
        if "commandexecuted" in l.lower() or "handle_slash" in l.lower() or "run_command" in l.lower():
            if "def " in l or "class " in l or "@" in l or "post_message" in l:
                print(f"{i+1:4d}: {l.strip()}")

