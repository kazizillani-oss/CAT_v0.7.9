import re
import glob

for p in glob.glob('CAT_v0.7.4/calc_terminal/**/*.py', recursive=True):
    with open(p, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    for idx, line in enumerate(lines):
        # find f-strings with backslash in expression
        for match in re.finditer(r'\{[^{}]*\\[^{}]*\}', line):
            if 'f"' in line or "f'" in line:
                print(f'{p}:{idx+1}: {line.strip()}')
