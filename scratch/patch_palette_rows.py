with open("calc_terminal/ui/palette.py", "r", encoding="utf-8") as f:
    text = f.read()

target = """    class CommandPalette(VerticalScroll):"""

replacement = """    class CommandPaletteRow(Static):
        def __init__(self, markup, index, palette_ref, **kwargs):
            super().__init__(markup, **kwargs)
            self.index = index
            self.palette_ref = palette_ref

        def on_enter(self, event):
            if self.palette_ref:
                self.palette_ref.select_index(self.index, scroll=False)

        def on_click(self, event):
            if self.palette_ref:
                self.palette_ref.select_index(self.index, scroll=False)
                if self.palette_ref.parent and hasattr(self.palette_ref.parent, "on_palette_selected"):
                    self.palette_ref.parent.on_palette_selected(self.palette_ref.selected_command())

    class CommandPalette(VerticalScroll):"""

text = text.replace(target, replacement, 1)

target_mount = "self.mount(Static(markup, classes=classes))"
replacement_mount = "self.mount(CommandPaletteRow(markup, i, self, classes=classes))"
text = text.replace(target_mount, replacement_mount, 1)

with open("calc_terminal/ui/palette.py", "w", encoding="utf-8") as f:
    f.write(text)
print("Updated palette.py with CommandPaletteRow!")

