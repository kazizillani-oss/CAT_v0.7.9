# scratch/update_palette.py
import re

with open('calc_terminal/ui/palette.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Update CommandPaletteRow to disable text selection and focus
old_row = """    class CommandPaletteRow(Static):
        def __init__(self, markup, index, palette_ref, **kwargs):"""

new_row = """    class CommandPaletteRow(Static):
        ALLOW_SELECT = False
        can_focus = False

        def __init__(self, markup, index, palette_ref, **kwargs):"""

assert old_row in code, "old_row not found"
code = code.replace(old_row, new_row, 1)

# 2. Update select_index to safely filter CommandPaletteRow
old_select = """        def select_index(self, index, scroll=True):
            if not self._matches or not (0 <= index < len(self._matches)):
                return
            if self._selected == index:
                return
            old_idx = self._selected
            self._selected = index
            children = list(self.children)
            if len(children) == len(self._matches):
                palette_w = self._get_palette_width()
                is_compact = (palette_w < 55)
                if 0 <= old_idx < len(children):
                    children[old_idx].remove_class("cct-cmd-row-selected")
                    children[old_idx].update(self._format_row_markup(old_idx, palette_w, is_compact))
                if 0 <= index < len(children):
                    children[index].add_class("cct-cmd-row-selected")
                    children[index].update(self._format_row_markup(index, palette_w, is_compact))
            else:
                self._redraw()
            if scroll:
                self._scroll_selected_into_view()"""

new_select = """        def select_index(self, index, scroll=True):
            if not self._matches or not (0 <= index < len(self._matches)):
                return
            if self._selected == index:
                return
            old_idx = self._selected
            self._selected = index
            children = [c for c in self.children if isinstance(c, CommandPaletteRow)]
            if len(children) == len(self._matches):
                palette_w = self._get_palette_width()
                is_compact = (palette_w < 55)
                if 0 <= old_idx < len(children):
                    children[old_idx].remove_class("cct-cmd-row-selected")
                    children[old_idx].update(self._format_row_markup(old_idx, palette_w, is_compact))
                if 0 <= index < len(children):
                    children[index].add_class("cct-cmd-row-selected")
                    children[index].update(self._format_row_markup(index, palette_w, is_compact))
            else:
                self._redraw()
            if scroll:
                self._scroll_selected_into_view()"""

assert old_select in code, "old_select not found"
code = code.replace(old_select, new_select, 1)

with open('calc_terminal/ui/palette.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("palette.py updated successfully!")

