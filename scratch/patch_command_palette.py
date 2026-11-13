with open(r"calc_terminal/ui/command_palette.py", "r", encoding="utf-8") as f:
    text = f.read()

target = """if TEXTUAL_AVAILABLE:
    from .palette import CommandPalette as _BaseCommandPalette

    class CommandPalette(_BaseCommandPalette):
        \"\"\"Same behavior as palette.CommandPalette (fuzzy match, live
        filter, arrow nav) — only `_redraw` changes, to paint each
        command in its category color instead of the flat accent color.
        \"\"\"

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
                is_sel = (i == self._selected)
                classes = 'cct-cmd-row' + (' cct-cmd-row-selected' if is_sel else '')
                bar = f'[{accent} b]▶[/] ' if is_sel else '  '
                if item.startswith('/'):
                    color = category_color(item)
                    cmd_label = f'{item} ' if is_compact else (f'{item:<14}' if len(item) < 14 else f'{item} ')
                    avail_desc = max(16, palette_w - len(cmd_label) - 4)
                    disp_desc = (desc[:avail_desc - 1] + '…') if len(desc) > avail_desc else desc
                    self.mount(Static(f'{bar}[{color} b]{cmd_label}[/][dim]{disp_desc}[/dim]', classes=classes))
                else:
                    avail_item = max(10, int(palette_w * (0.35 if is_compact else 0.45)))
                    disp_item = (item[:avail_item - 1] + '…') if len(item) > avail_item else item
                    avail_desc = max(8, palette_w - len(disp_item) - 8)
                    disp_desc = (desc[:avail_desc - 1] + '…') if len(desc) > avail_desc else desc
                    self.mount(Static(f'{bar}[{accent}]✦[/] [b]{disp_item}[/] [dim]{disp_desc}[/dim]', classes=classes))"""

replacement = """if TEXTUAL_AVAILABLE:
    from .palette import CommandPalette as _BaseCommandPalette

    class CommandPalette(_BaseCommandPalette):
        \"\"\"Same behavior as palette.CommandPalette (fuzzy match, live
        filter, arrow nav, cursor tracking) — paints each
        command in its category color instead of the flat accent color.
        \"\"\"

        def _get_item_color(self, item, default_accent):
            if item.startswith('/'):
                return category_color(item)
            return default_accent"""

text_n = text.replace('\r\n', '\n')
target_n = target.replace('\r\n', '\n')
replacement_n = replacement.replace('\r\n', '\n')

if target_n in text_n:
    text_n = text_n.replace(target_n, replacement_n)
    with open(r"calc_terminal/ui/command_palette.py", "w", encoding="utf-8") as f:
        f.write(text_n)
    print("Successfully patched calc_terminal/ui/command_palette.py")
else:
    print("Error: Target not found in command_palette.py")

