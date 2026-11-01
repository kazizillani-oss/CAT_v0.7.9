import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9"

def fix_palette():
    p = os.path.join(ROOT, "calc_terminal/ui/palette.py")
    with open(p, "r", encoding="utf-8") as f:
        c = f.read().replace('\r\n', '\n')

    # Fix height
    old_h = """            try:
                screen_h = getattr(getattr(self.app, 'size', None), 'height', 30)
                max_rows = 5 if screen_h < 40 else 7
            except Exception:
                max_rows = 6
            self.styles.height = min(max_rows, max(3, len(self._matches)))"""

    new_h = """            try:
                screen_h = getattr(getattr(self.app, 'size', None), 'height', 30)
                max_items = 4 if screen_h < 32 else (5 if screen_h < 40 else 7)
            except Exception:
                max_items = 5
            visible_rows = min(max_items, len(self._matches))
            self.styles.height = max(4, visible_rows + 2)"""

    if old_h in c:
        c = c.replace(old_h, new_h, 1)
        print("Replaced height in palette.py")

    old_redraw = """            for i, (item, desc) in enumerate(self._matches):
                classes = 'cct-cmd-row' + (' cct-cmd-row-selected' if i == self._selected else '')
                marker = '▶ ' if i == self._selected else '  '
                if item.startswith('/'):
                    cmd_pad = f'{item:<12}' if len(item) < 12 else f'{item} '
                    avail_desc = max(8, palette_w - len(cmd_pad) - 8)
                    disp_desc = (desc[:avail_desc - 1] + '…') if len(desc) > avail_desc else desc
                    self.mount(Static(f'{marker}[{accent} b]{cmd_pad}[/]  [dim]{disp_desc}[/dim]', classes=classes))
                else:
                    avail_item = max(10, int(palette_w * 0.45))
                    disp_item = (item[:avail_item - 1] + '…') if len(item) > avail_item else item
                    avail_desc = max(8, palette_w - len(disp_item) - 10)
                    disp_desc = (desc[:avail_desc - 1] + '…') if len(desc) > avail_desc else desc
                    self.mount(Static(f'{marker}[{accent}]✦[/] {disp_item}  [dim]{disp_desc}[/dim]', classes=classes))"""

    new_redraw = """            is_compact = (palette_w < 70)
            for i, (item, desc) in enumerate(self._matches):
                classes = 'cct-cmd-row' + (' cct-cmd-row-selected' if i == self._selected else '')
                marker = '▶ ' if i == self._selected else '  '
                if item.startswith('/'):
                    cmd_pad = f'{item}  ' if is_compact else (f'{item:<12}' if len(item) < 12 else f'{item} ')
                    avail_desc = max(8, palette_w - len(cmd_pad) - 5)
                    disp_desc = (desc[:avail_desc - 1] + '…') if len(desc) > avail_desc else desc
                    self.mount(Static(f'{marker}[{accent} b]{cmd_pad}[/][dim]{disp_desc}[/dim]', classes=classes))
                else:
                    avail_item = max(10, int(palette_w * (0.35 if is_compact else 0.45)))
                    disp_item = (item[:avail_item - 1] + '…') if len(item) > avail_item else item
                    avail_desc = max(8, palette_w - len(disp_item) - 8)
                    disp_desc = (desc[:avail_desc - 1] + '…') if len(desc) > avail_desc else desc
                    self.mount(Static(f'{marker}[{accent}]✦[/] {disp_item} [dim]{disp_desc}[/dim]', classes=classes))"""

    # Replace character \u2726 or ✦ if present
    if "Static(f'{marker}[{accent} b]{cmd_pad}[/]  [dim]{disp_desc}[/dim]'" in c:
        # replace the loop directly
        idx1 = c.find("for i, (item, desc) in enumerate(self._matches):")
        idx2 = c.find("else:\n    CommandPalette = None")
        c = c[:idx1] + new_redraw.lstrip() + "\n" + c[idx2:]
        print("Replaced redraw in palette.py")

    with open(p, "w", encoding="utf-8") as f:
        f.write(c)

def fix_cmd_palette():
    p = os.path.join(ROOT, "calc_terminal/ui/command_palette.py")
    with open(p, "r", encoding="utf-8") as f:
        c = f.read().replace('\r\n', '\n')

    new_redraw_cmd = """            is_compact = (palette_w < 70)
            for i, (item, desc) in enumerate(self._matches):
                is_sel = (i == self._selected)
                classes = 'cct-cmd-row' + (' cct-cmd-row-selected' if is_sel else '')
                bar = f'[{accent} b]▶[/] ' if is_sel else '  '
                if item.startswith('/'):
                    color = category_color(item)
                    cmd_label = f'{item}  ' if is_compact else (f'{item:<12}' if len(item) < 12 else f'{item} ')
                    avail_desc = max(8, palette_w - len(cmd_label) - 5)
                    disp_desc = (desc[:avail_desc - 1] + '…') if len(desc) > avail_desc else desc
                    self.mount(Static(f'{bar}[{color} b]{cmd_label}[/][dim]{disp_desc}[/dim]', classes=classes))
                else:
                    avail_item = max(10, int(palette_w * (0.35 if is_compact else 0.45)))
                    disp_item = (item[:avail_item - 1] + '…') if len(item) > avail_item else item
                    avail_desc = max(8, palette_w - len(disp_item) - 8)
                    disp_desc = (desc[:avail_desc - 1] + '…') if len(desc) > avail_desc else desc
                    self.mount(Static(f'{bar}[{accent}]✦[/] [b]{disp_item}[/] [dim]{disp_desc}[/dim]', classes=classes))"""

    idx1 = c.find("for i, (item, desc) in enumerate(self._matches):")
    idx2 = c.find("else:\n    CommandPalette = None")
    if idx1 != -1 and idx2 != -1:
        c = c[:idx1] + new_redraw_cmd.lstrip() + "\n" + c[idx2:]
        print("Replaced redraw in command_palette.py")

    with open(p, "w", encoding="utf-8") as f:
        f.write(c)

fix_palette()
fix_cmd_palette()
print("Palette fixes applied successfully.")

