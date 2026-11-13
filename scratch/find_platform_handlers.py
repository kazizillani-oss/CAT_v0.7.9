with open('calc_terminal/ui/app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if any(k in line for k in ['word == "/db"', 'word == "/workflow"', 'word == "/cloud"', 'word == "/github"', 'word == "/deploy"']):
        print(f"{i+1}: {line.strip()[:100]}")

