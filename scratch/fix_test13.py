with open('calc_terminal/tests/test_platform_expansion_complete.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if 'self.assertIn(".cct-menu-btn {' in line:
        new_lines.append('        self.assertIn("border-top: tall #6b7596;", app_code)\n')
        new_lines.append('        self.assertIn(".cct-menu-btn {", app_code)\n')
        new_lines.append('        self.assertIn(".cct-perm-pill {", app_code)\n')
        new_lines.append('        self.assertIn("#cct-header-right {", app_code)\n')
        skip = True
    elif skip and ('self.assertIn(".cct-perm-pill {' in line or 'self.assertIn("#cct-header-right {' in line):
        continue
    else:
        skip = False
        new_lines.append(line)

with open('calc_terminal/tests/test_platform_expansion_complete.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Updated test_13 successfully!")

