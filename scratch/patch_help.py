with open('calc_terminal/ui/app.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_block = '''            if word == "/help":
                lines = "\\n".join(f"- `{cmd}` \\u2014 {desc}" for cmd, desc in COMMANDS)
                self._system_note(lines, role="assistant")
                return'''

# Also check for literal em dash
if old_block not in text:
    old_block = '''            if word == "/help":
                lines = "\\n".join(f"- `{cmd}` — {desc}" for cmd, desc in COMMANDS)
                self._system_note(lines, role="assistant")
                return'''

new_block = '''            if word in ("/help", "/commands"):
                if arg and arg.strip().lower() in ("all", "full", "list"):
                    lines = "\\n".join(f"- `{cmd}` — {desc}" for cmd, desc in COMMANDS)
                    self._system_note(lines, role="assistant")
                    return
                card = (
                    "### ⚡ CAT Commands & Quick Reference\\n\\n"
                    f"Type `/` in the chat composer to search and run all **{len(COMMANDS)} commands** with real-time autocompletion.\\n\\n"
                    "**Core Commands:**\\n"
                    "- `/model` — Switch AI provider and model\\n"
                    "- `/mode` or `/kitties` — Switch Kitty agent persona & mode\\n"
                    "- `/open` — Open workspace folder or project\\n"
                    "- `/extensions` — Manage extensions, tools & skills\\n"
                    "- `/browser` — Launch integrated CAT browser\\n"
                    "- `/settings` — Manage user preferences and profile\\n"
                    "- `/mascot` — Open Page Mascot Studio\\n"
                    "- `/checkpoint` — Create or rollback workspace snapshot\\n\\n"
                    "*Type `/help all` to display all commands in chat, or use `/` for instant fuzzy search.*"
                )
                self._system_note(card, role="assistant")
                return'''

if old_block in text:
    text = text.replace(old_block, new_block, 1)
    with open('calc_terminal/ui/app.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("SUCCESS: Patched /help and /commands in app.py")
else:
    print("NOT FOUND! Searching for line containing word == '/help'...")
    idx = text.find('if word == "/help":')
    if idx != -1:
        print("Context around word == '/help':")
        print(repr(text[idx:idx+150]))

