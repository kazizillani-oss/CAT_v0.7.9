import glob
import re
from textual.css.stylesheet import Stylesheet
import calc_terminal.ui.theme_css as tc

vars_ = tc.css_variables()
errors = []

for f in sorted(glob.glob("calc_terminal/ui/*.py")):
    with open(f, "r", encoding="utf-8") as fh:
        src = fh.read()
    
    # find all DEFAULT_CSS or CSS blocks
    matches = re.findall(r'(?:DEFAULT_CSS|CSS)\s*=\s*"""(.*?)"""', src, re.DOTALL)
    for idx, css in enumerate(matches):
        sheet = Stylesheet(variables=vars_)
        sheet.add_source(css, f"{f}#block{idx}")
        try:
            sheet.parse()
        except Exception as e:
            errors.append((f, idx, str(e)))
            print(f"FAILED {f} block {idx}: {e}")

print(f"\nTotal errors: {len(errors)}")

