# scratch/fix_composer_max_height.py
with open('calc_terminal/ui/composer.py', 'r', encoding='utf-8') as f:
    code = f.read()

code = code.replace('self.styles.max_height = "55%"', 'self.styles.max_height = "42%"')

with open('calc_terminal/ui/composer.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("Fixed max_height in composer.py")

