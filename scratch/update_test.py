with open('calc_terminal/tests/test_platform_expansion_complete.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_block = '''        self.assertIn(".cct-menu-btn {\\n    width: 5; min-width: 5; height: 3; color: $text; content-align: center middle;\\n    background: $surface;\\n    border: round #3c4252;", app_code)
        self.assertIn(".cct-perm-pill {\\n    width: auto; content-align: center middle; height: 3;\\n    padding: 0 2; margin: 0;\\n    background: $surface;\\n    border: round #3c4252;", app_code)
        self.assertIn("#cct-header-right {\\n    width: auto; max-width: 32; content-align: center middle;\\n    padding: 0 2; height: 3;\\n    background: $surface;\\n    border: round #3c4252;", app_code)'''

new_block = '''        self.assertIn(".cct-menu-btn {\\n    width: 5; min-width: 5; height: 3; color: $text; content-align: center middle;\\n    background: #252839;\\n    border-top: solid #5a6585;", app_code)
        self.assertIn(".cct-perm-pill {\\n    width: auto; content-align: center middle; height: 3;\\n    padding: 0 2; margin: 0;\\n    background: #252839;\\n    border-top: solid #5a6585;", app_code)
        self.assertIn("#cct-header-right {\\n    width: auto; max-width: 32; content-align: center middle;\\n    padding: 0 2; height: 3;\\n    background: #252839;\\n    border-top: solid #5a6585;", app_code)'''

if old_block in text:
    text = text.replace(old_block, new_block)
    with open('calc_terminal/tests/test_platform_expansion_complete.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Updated test_13 in test_platform_expansion_complete.py')
else:
    print('Error: old_block not found')
