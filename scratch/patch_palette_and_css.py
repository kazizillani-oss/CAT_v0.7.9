import os

# 1. Patch palette.py for on_mouse_move cursor tracking
path_pal = "calc_terminal/ui/palette.py"
with open(path_pal, "r", encoding="utf-8") as f:
    txt_pal = f.read()

target_row = """    class CommandPaletteRow(Static):
        def __init__(self, markup, index, palette_ref, **kwargs):
            super().__init__(markup, **kwargs)
            self.index = index
            self.palette_ref = palette_ref

        def on_enter(self, event):
            if self.palette_ref:
                self.palette_ref.select_index(self.index, scroll=False)

        def on_click(self, event):"""

replacement_row = """    class CommandPaletteRow(Static):
        def __init__(self, markup, index, palette_ref, **kwargs):
            super().__init__(markup, **kwargs)
            self.index = index
            self.palette_ref = palette_ref

        def on_enter(self, event):
            if self.palette_ref:
                self.palette_ref.select_index(self.index, scroll=False)

        def on_mouse_move(self, event):
            if self.palette_ref:
                self.palette_ref.select_index(self.index, scroll=False)

        def on_click(self, event):"""

if target_row in txt_pal:
    txt_pal = txt_pal.replace(target_row, replacement_row, 1)
    with open(path_pal, "w", encoding="utf-8") as f:
        f.write(txt_pal)
    print("SUCCESS: Patched palette.py cursor tracking")
else:
    print("WARNING: target_row not found in palette.py")

# 2. Patch theme_css.py for clean row width without black box
path_theme = "calc_terminal/ui/theme_css.py"
with open(path_theme, "r", encoding="utf-8") as f:
    txt_theme = f.read()

target_row_css = """.cct-cmd-row {
    height: 1; min-height: 1; max-height: 1;
    padding: 0 1; color: $text-muted; width: 100%;
    border-left: thick transparent;
    border-right: thick transparent;
    transition: background 60ms, color 60ms, border-left 60ms;
}"""

replacement_row_css = """.cct-cmd-row {
    height: 1; min-height: 1; max-height: 1;
    padding: 0 1; color: $text-muted; width: 100%;
    border-left: thick transparent;
    border-right: none;
    transition: background 60ms, color 60ms, border-left 60ms;
}"""

if target_row_css in txt_theme:
    txt_theme = txt_theme.replace(target_row_css, replacement_row_css, 1)
    with open(path_theme, "w", encoding="utf-8") as f:
        f.write(txt_theme)
    print("SUCCESS: Patched theme_css.py row borders")
else:
    print("WARNING: target_row_css not found in theme_css.py")

