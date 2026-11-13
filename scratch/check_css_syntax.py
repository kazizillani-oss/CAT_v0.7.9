import glob
import re
from textual.css.stylesheet import Stylesheet
import calc_terminal.ui.theme_css as tc

vars_ = tc.css_variables()
errors = []

for f in sorted(glob.glob('calc_terminal/**/*.py', recursive=True)):
    with open(f, 'r', encoding='utf-8', errors='ignore') as fh:
        src = fh.read()
    for m in re.finditer(r'([A-Za-z0-9_]*CSS)\s*=\s*(?:f?"""(.*?)"""|f?\'\'\'(.*?)\'\'\')', src, re.DOTALL):
        name = m.group(1)
        css = m.group(2) if m.group(2) is not None else m.group(3)
        # substitute any simple f-string expressions if needed
        # but let's test directly first
        sheet = Stylesheet(variables=vars_)
        sheet.add_source(css, f'{f}:{name}')
        try:
            sheet.parse()
        except Exception as e:
            errors.append((f, name, str(e)))
            print(f'FAILED {f} {name}: {e}')

print(f'\nTotal errors: {len(errors)}')

