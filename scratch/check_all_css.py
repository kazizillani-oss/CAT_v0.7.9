import os
import re
from textual.css.parse import parse
from calc_terminal.ui import theme_css

vars_map = theme_css.css_variables()
# Also add standard textual variables
for v in ["app-background", "surface", "surface-alt", "surface-darken-1", "surface-darken-2",
          "surface-lighten-1", "surface-lighten-2", "text", "text-muted", "text-faint", "text-disabled",
          "background", "panel", "panel-darken-1", "panel-lighten-1", "border", "border-blurred",
          "accent", "accent-darken-1", "accent-lighten-1", "primary", "secondary", "warning",
          "error", "success", "info"]:
    if v not in vars_map:
        vars_map[v] = "#181926"

errors = []
for root, dirs, files in os.walk('calc_terminal'):
    for f in files:
        if f.endswith('.py'):
            p = os.path.join(root, f)
            with open(p, 'r', encoding='utf-8', errors='ignore') as fp:
                content = fp.read()
            # find CSS = """...""" or CSS = '''...'''
            for m in re.finditer(r'CSS\s*=\s*(?:"""(.*?)"""|\'\'\'(.*?)\'\'\')', content, re.DOTALL):
                css_str = m.group(1) or m.group(2)
                try:
                    list(parse('', css_str, ('test', 'test'), vars_map))
                except Exception as e:
                    errors.append((p, str(e)))

print(f'Total CSS parse errors found: {len(errors)}')
for p, err in errors:
    print(f'{p}: {err}')

