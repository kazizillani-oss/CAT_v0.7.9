import sys

p_palette = r"calc_terminal/ui/palette.py"
with open(p_palette, "r", encoding="utf-8") as f:
    text = f.read()

target = """        def on_click(self, event):
            try:
                for i, child in enumerate(self.children):
                    if child == event.widget or child in getattr(event.widget, "ancestors", []):
                        self._selected = i
                        self._redraw()
                        if self.parent and hasattr(self.parent, "on_palette_selected"):
                            self.parent.on_palette_selected(self.selected_command())
                        break
            except Exception:
                pass

        def move(self, delta):
            if not self._matches:
                return
            self._selected = (self._selected + delta) % len(self._matches)
            self._redraw()
            self._scroll_selected_into_view()

        def move_page(self, direction):
            if not self._matches:
                return
            last = len(self._matches) - 1
            self._selected = max(0, min(last, self._selected + direction * PAGE_SIZE))
            self._redraw()
            self._scroll_selected_into_view()

        def selected_command(self):
            if not self._matches:
                return None
            return self._matches[self._selected][0]

        def _scroll_selected_into_view(self):
            try:
                rows = list(self.query(".cct-cmd-row"))
                if 0 <= self._selected < len(rows):
                    self.scroll_to_widget(rows[self._selected], animate=True)
            except Exception:
                pass

        def _redraw(self):
            from . import theme_css
            accent = theme_css.current_hex('accent')
            for child in list(self.children):
                child.remove()
            try:
                palette_w = self.size.width if (self.size and self.size.width > 0) else 0
                if not palette_w and self.parent and self.parent.size:
                    palette_w = self.parent.size.width - 4
                if not palette_w:
                    palette_w = 80
            except Exception:
                palette_w = 80
            try:
                if not palette_w and hasattr(self.app, 'size') and self.app.size:
                    palette_w = self.app.size.width - 4
            except Exception:
                pass
            is_compact = (palette_w < 55)
            for i, (item, desc) in enumerate(self._matches):
                classes = 'cct-cmd-row' + (' cct-cmd-row-selected' if i == self._selected else '')
                marker = '▶ ' if i == self._selected else '  '
                if item.startswith('/'):
                    cmd_pad = f'{item} ' if is_compact else (f'{item:<14}' if len(item) < 14 else f'{item} ')
                    avail_desc = max(16, palette_w - len(cmd_pad) - 4)
                    disp_desc = (desc[:avail_desc - 1] + '…') if len(desc) > avail_desc else desc
                    self.mount(Static(f'{marker}[{accent} b]{cmd_pad}[/][dim]{disp_desc}[/dim]', classes=classes))
                else:
                    avail_item = max(10, int(palette_w * (0.35 if is_compact else 0.45)))
                    disp_item = (item[:avail_item - 1] + '…') if len(item) > avail_item else item
                    avail_desc = max(8, palette_w - len(disp_item) - 8)
                    disp_desc = (desc[:avail_desc - 1] + '…') if len(desc) > avail_desc else desc
                    self.mount(Static(f'{marker}[{accent}]✦[/] {disp_item} [dim]{disp_desc}[/dim]', classes=classes))"""

replacement = """        def _get_palette_width(self):
            palette_w = 0
            try:
                palette_w = self.size.width if (self.size and self.size.width > 0) else 0
            except Exception:
                palette_w = 0
            if not palette_w and self.parent and getattr(self.parent, "size", None):
                palette_w = max(0, self.parent.size.width - 4)
            if not palette_w and hasattr(self, "app") and getattr(self.app, "size", None):
                palette_w = max(0, self.app.size.width - 4)
            return palette_w or 80

        def _format_row_markup(self, i, palette_w, is_compact):
            from . import theme_css
            accent = theme_css.current_hex('accent')
            item, desc = self._matches[i]
            is_sel = (i == self._selected)
            marker = '▶ ' if is_sel else '  '
            color = self._get_item_color(item, accent)
            if item.startswith('/'):
                cmd_pad = f'{item} ' if is_compact else (f'{item:<14}' if len(item) < 14 else f'{item} ')
                avail_desc = max(16, palette_w - len(cmd_pad) - 4)
                disp_desc = (desc[:avail_desc - 1] + '…') if len(desc) > avail_desc else desc
                return f'{marker}[{color} b]{cmd_pad}[/][dim]{disp_desc}[/dim]'
            else:
                avail_item = max(10, int(palette_w * (0.35 if is_compact else 0.45)))
                disp_item = (item[:avail_item - 1] + '…') if len(item) > avail_item else item
                avail_desc = max(8, palette_w - len(disp_item) - 8)
                disp_desc = (desc[:avail_desc - 1] + '…') if len(desc) > avail_desc else desc
                return f'{marker}[{accent}]✦[/] [b]{disp_item}[/] [dim]{disp_desc}[/dim]'

        def _get_item_color(self, item, default_accent):
            return default_accent

        def select_index(self, index, scroll=True):
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
                self._scroll_selected_into_view()

        def on_mouse_move(self, event):
            try:
                target = getattr(event, "widget", None)
                for i, child in enumerate(self.children):
                    if child is target or child in getattr(target, "ancestors", []):
                        if self._selected != i:
                            self.select_index(i, scroll=False)
                        break
            except Exception:
                pass

        def on_click(self, event):
            try:
                target = getattr(event, "widget", None)
                for i, child in enumerate(self.children):
                    if child is target or child in getattr(target, "ancestors", []):
                        self.select_index(i, scroll=False)
                        if self.parent and hasattr(self.parent, "on_palette_selected"):
                            self.parent.on_palette_selected(self.selected_command())
                        break
            except Exception:
                pass

        def move(self, delta):
            if not self._matches:
                return
            new_idx = (self._selected + delta) % len(self._matches)
            self.select_index(new_idx, scroll=True)

        def move_page(self, direction):
            if not self._matches:
                return
            last = len(self._matches) - 1
            new_idx = max(0, min(last, self._selected + direction * PAGE_SIZE))
            self.select_index(new_idx, scroll=True)

        def selected_command(self):
            if not self._matches:
                return None
            return self._matches[self._selected][0]

        def _scroll_selected_into_view(self):
            try:
                rows = list(self.query(".cct-cmd-row"))
                if 0 <= self._selected < len(rows):
                    self.scroll_to_widget(rows[self._selected], animate=True)
            except Exception:
                pass

        def _redraw(self):
            for child in list(self.children):
                child.remove()
            palette_w = self._get_palette_width()
            is_compact = (palette_w < 55)
            for i in range(len(self._matches)):
                classes = 'cct-cmd-row' + (' cct-cmd-row-selected' if i == self._selected else '')
                markup = self._format_row_markup(i, palette_w, is_compact)
                self.mount(Static(markup, classes=classes))"""

text_n = text.replace('\r\n', '\n')
target_n = target.replace('\r\n', '\n')
replacement_n = replacement.replace('\r\n', '\n')

if target_n in text_n:
    text_n = text_n.replace(target_n, replacement_n)
    with open(p_palette, "w", encoding="utf-8") as f:
        f.write(text_n)
    print("Successfully patched calc_terminal/ui/palette.py")
else:
    print("Error: Target block not found in calc_terminal/ui/palette.py")

