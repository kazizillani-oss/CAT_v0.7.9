with open('calc_terminal/ui/header.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('self.styles.height = 2', 'self.styles.height = 4')

# Clean up the if-else if both branches now set height = 4
old_check = """                    if not self.has_class("is-portrait"):
                        self.styles.height = 4
                    else:
                        self.styles.height = 4"""

new_check = """                    self.styles.height = 4"""

text = text.replace(old_check, new_check)

with open('calc_terminal/ui/header.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Updated header.py successfully!")

