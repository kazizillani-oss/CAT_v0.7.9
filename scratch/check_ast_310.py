import ast
import glob

print("Checking Python 3.10 AST compatibility...")
errors = 0
for p in glob.glob('CAT_v0.7.4/calc_terminal/**/*.py', recursive=True):
    with open(p, 'r', encoding='utf-8') as f:
        src = f.read()
    try:
        ast.parse(src, filename=p, feature_version=(3, 10))
    except SyntaxError as e:
        print(f"FAILED on 3.10: {p}:{e.lineno}: {e.msg} -> {e.text.strip() if e.text else ''}")
        errors += 1

print(f"Total 3.10 AST errors: {errors}")
