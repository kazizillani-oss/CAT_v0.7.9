import os

path = "calc_terminal/ui/workspace.py"
with open(path, "r", encoding="utf-8") as f:
    txt = f.read()

target = """            is_port = self.is_portrait()
            self.set_class(is_port, "is-portrait")
            if self.explorer:
                self.explorer.set_class(is_port, "is-portrait")
                if is_port and self.explorer.display and self.explorer.width > 0:
                    self.explorer.styles.width = "100%"
                    main.display = False
                    return
                else:
                    main.display = True
            else:
                main.display = True"""

replacement = """            is_port = self.is_portrait()
            self.set_class(is_port, "is-portrait")
            if self.explorer:
                self.explorer.set_class(is_port, "is-portrait")
                if is_port and getattr(self, "_explorer_manually_opened", False) and self.explorer.display:
                    self.explorer.styles.width = "100%"
                    main.display = False
                    return
                elif is_port:
                    self.explorer.display = False
                    self.explorer.width = 0
                    main.display = True
                else:
                    main.display = True
            else:
                main.display = True"""

if target in txt:
    txt = txt.replace(target, replacement, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(txt)
    print("SUCCESS: Patched workspace.py portrait handling")
else:
    print("ERROR: Target not found in workspace.py")

