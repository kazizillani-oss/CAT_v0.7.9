with open('calc_terminal/ui/header.py', 'r', encoding='utf-8') as f:
    text = f.read()

dup_compose = '''        def compose(self):
            with Horizontal(id="cct-header-top"):
                with Horizontal(id="cct-header-left"):
                    yield MenuButton()
                    yield Logo()
                yield PermissionPill()
        def compose(self):'''

single_compose = '''        def compose(self):'''

if dup_compose in text:
    text = text.replace(dup_compose, single_compose)
    print("Removed duplicate compose in header.py")
else:
    print("Duplicate compose not found in header.py")

with open('calc_terminal/ui/header.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Saved header.py")
