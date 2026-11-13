import re
from pathlib import Path

ext_panel_file = Path("calc_terminal/ui/extensions_panel.py")
content = ext_panel_file.read_text(encoding="utf-8")

# Let's verify the file content can be read
print(f"Current extensions_panel.py length: {len(content)} chars")

