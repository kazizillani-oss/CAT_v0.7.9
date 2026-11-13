path = "calc_terminal/ui/composer.py"
with open(path, "r", encoding="utf-8") as f:
    txt = f.read()
target = 'self.styles.max_height = "55%"'
replacement = 'self.styles.max_height = "42%"'
if target in txt:
    txt = txt.replace(target, replacement, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(txt)
    print("SUCCESS: Updated composer palette max_height to 42%")
else:
    print("Target not found")

