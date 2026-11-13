import sys
from textual.css.parse import parse
from pathlib import Path
import re

mock_vars = """
$app-background: #000000;
$surface: #000000;
$surface-alt: #000000;
$surface-darken-1: #000000;
$surface-darken-2: #000000;
$surface-lighten-1: #000000;
$surface-lighten-2: #000000;
$background: #000000;
$border: #000000;
$text: #ffffff;
$text-muted: #888888;
$text-faint: #444444;
$primary: #0000ff;
$secondary: #00ff00;
$accent: #ff0000;
$warning: #ffff00;
$error: #ff0000;
$success: #00ff00;
"""

for p in sorted(Path('calc_terminal').rglob('*.py')):
    text = p.read_text(encoding='utf-8')
    matches = re.findall(r'(?:DEFAULT_CSS|CSS)\s*=\s*(?:f?\"\"\"(.*?)\"\"\"|f?\'\'\'(.*?)\'\'\')', text, re.DOTALL)
    for i, m in enumerate(matches):
        css = m[0] or m[1]
        try:
            css_clean = re.sub(r'\{[a-zA-Z0-9_]+\}', 'red', css)
            full_css = mock_vars + "\n" + css_clean
            list(parse('', full_css, (str(p), str(p))))
        except Exception as e:
            print(f"SYNTAX ERROR in {p} (block {i}): {e}")
