import os

for root, dirs, files in os.walk('calc_terminal/ui'):
    for f in files:
        if f.endswith('.py'):
            p = os.path.join(root, f)
            with open(p, 'r', encoding='utf-8') as pyf:
                for i, l in enumerate(pyf, 1):
                    if 'cct-modal-close-btn' in l:
                        print(f"{f}:{i}: {l.strip()[:80]}")

