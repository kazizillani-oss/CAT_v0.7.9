# scratch/fix_composer_min_height.py
with open('calc_terminal/ui/composer.py', 'r', encoding='utf-8') as f:
    code = f.read()

old_block = """                else:
                    editor.styles.min_height = 1
                    avail = int(self.screen.size.height * 0.6) - 5
                    editor_max = max(2, min(10, avail))
                    editor.styles.max_height = editor_max
                    stack.styles.min_height = 1
                    stack.styles.max_height = editor_max
                    row.styles.min_height = 1"""

new_block = """                else:
                    editor.styles.min_height = 2
                    avail = int(self.screen.size.height * 0.6) - 5
                    editor_max = max(2, min(10, avail))
                    editor.styles.max_height = editor_max
                    stack.styles.min_height = 2
                    stack.styles.max_height = editor_max
                    row.styles.min_height = 2"""

assert old_block in code, "old_block not found in composer.py"
code = code.replace(old_block, new_block, 1)

with open('calc_terminal/ui/composer.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Updated min_height to 2 in composer.py")

