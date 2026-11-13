import os
import re
from textual.css.stylesheet import Stylesheet
import calc_terminal.ui.theme_css as tc
from calc_terminal.ui.app import CCTApp

vars = tc.css_variables()
sheet = Stylesheet(variables=vars)
sheet.add_source(CCTApp.CSS, "CCTApp.CSS")
sheet.parse()
print(f"CCTApp.CSS parsed successfully: {len(sheet.rules)} rules")

count = 0
for f in os.listdir("calc_terminal/ui"):
    if f.endswith(".py"):
        p = os.path.join("calc_terminal/ui", f)
        txt = open(p, "r", encoding="utf-8").read()
        blocks = re.findall(r'(\b[A-Za-z0-9_]+\b)?.*?\bCSS\s*=\s*"""(.*?)"""', txt, re.DOTALL)
        for m in blocks:
            name = m[0] or f
            css = m[1]
            s = Stylesheet(variables=vars)
            s.add_source(css, f"{f}::{name}")
            s.parse()
            count += 1

print(f"All {count} UI CSS stylesheets parsed with 0 errors!")

