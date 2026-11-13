with open(r'calc_terminal/tests/test_cli_safety.py', 'r', encoding='utf-8') as f:
    c = f.read()
c = c.replace('"tag_name": "v0.8.0.0"', '"tag_name": "v0.9.0.0"')
c = c.replace('tag/v0.8.0.0', 'tag/v0.9.0.0')
with open(r'calc_terminal/tests/test_cli_safety.py', 'w', encoding='utf-8') as f:
    f.write(c)

with open(r'calc_terminal/tests/test_blank_screen_and_editor_responsiveness.py', 'r', encoding='utf-8') as f:
    c = f.read()
c = c.replace('self.assertEqual(identity.APP_VERSION, "0.8.0b1")', 'self.assertEqual(identity.APP_VERSION, __version__)')
c = c.replace('self.assertEqual(__version__, "0.8.0b1")', 'self.assertEqual(__version__, "0.8.9.01")')
with open(r'calc_terminal/tests/test_blank_screen_and_editor_responsiveness.py', 'w', encoding='utf-8') as f:
    f.write(c)

print('Updated tests successfully')

