import glob
import re

for f in sorted(glob.glob('calc_terminal/tests/*.py')):
    with open(f, 'r', encoding='utf-8') as fh:
        for idx, line in enumerate(fh, 1):
            if any(k in line for k in ['styles.border', 'border_top', 'border_bottom', 'border_left', 'border_right', 'assert "border', "assert 'border"]):
                print(f"{f}:{idx}: {line.strip()}")

