import ast

with open('calc_terminal/ui/app.py', 'r', encoding='utf-8') as f:
    text = f.read()

try:
    ast.parse(text)
    print("Clean AST parse! No syntax errors.")
except SyntaxError as e:
    print(f"Syntax error at line {e.lineno}: {e.msg}")
    lines = text.splitlines()
    for l in range(max(0, e.lineno - 5), min(len(lines), e.lineno + 5)):
        print(f"{l+1}: {repr(lines[l])}")

