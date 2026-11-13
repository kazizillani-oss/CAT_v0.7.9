import re
from textual.css.stylesheet import Stylesheet
import calc_terminal.ui.theme_css as tc
from textual.css.tokenizer import TokenError

with open('calc_terminal/ui/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

content_test = content.replace('background: -highlight 25%;\n    color: #ffffff;\n    border-left: thick ;', 'background: $accent 18%;\n    color: #ffffff;\n    border-left: thick $accent;')

match = re.search(r'CSS\s*=\s*"""(.*?)"""', content_test, re.DOTALL)
css = match.group(1)

rules = css.split('}')
for idx, rule in enumerate(rules):
    test_block = rule.strip()
    if not test_block:
        continue
    test_block += '\n}'
    sheet = Stylesheet(variables=tc.css_variables())
    sheet.add_source(test_block, f'rule_{idx}')
    try:
        sheet.parse()
    except TokenError as te:
        print(f"FAILED on block {idx}:")
        print(test_block)
        print(f"Error: {te}")
        break
    except Exception as e:
        pass
