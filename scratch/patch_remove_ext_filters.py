import re

with open('calc_terminal/ui/extensions_panel.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Remove #ext-filters CSS
pattern_css = r'\s*#ext-filters\s*\{[^}]*\}\s*\.ext-filter-btn\s*\{[^}]*\}\s*\.ext-filter-btn:hover\s*\{[^}]*\}\s*\.ext-filter-btn\.active\s*\{[^}]*\}'
text = re.sub(pattern_css, '', text)

# 2. Remove compose filters buttons
pattern_compose = r'\s*with Horizontal\(id="ext-filters"\):(?:\s*yield Button\([^)]+\))+'
text = re.sub(pattern_compose, '', text)

# 3. Simplify _filtered
pattern_filtered = r'ftype = None if self\._current_filter in \([^\)]+\) else self\._current_filter\s*all_exts = ext_mgr\.list_extensions\(component_type=ftype\) if ext_mgr else \[\](?:\s*elif?[^\n]+\s*all_exts = [^\n]+)*'
text = re.sub(pattern_filtered, 'all_exts = ext_mgr.list_extensions(component_type=None) if ext_mgr else []', text)

with open('calc_terminal/ui/extensions_panel.py', 'w', encoding='utf-8') as f:
    f.write(text)

print('Successfully removed ext-filters tab bar from extensions_panel.py!')

