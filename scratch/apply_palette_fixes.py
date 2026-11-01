import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9"

# 1. Update palette.py
path_pal = os.path.join(ROOT, "calc_terminal/ui/palette.py")
with open(path_pal, "r", encoding="utf-8") as f:
    c_pal = f.read()

target_open = '''            try:
                screen_h = getattr(getattr(self.app, 'size', None), 'height', 30)
                max_rows = 5 if screen_h < 40 else 7
            except Exception:
                max_rows = 6
            self.styles.height = min(max_rows, max(3, len(self._matches)))'''

replace_open = '''            try:
                screen_h = getattr(getattr(self.app, 'size', None), 'height', 30)
                max_items = 4 if screen_h < 32 else (5 if screen_h < 40 else 7)
            except Exception:
                max_items = 5
            visible_rows = min(max_items, len(self._matches))
            self.styles.height = max(4, visible_rows + 2)'''

assert target_open in c_pal, "target_open not found in palette.py"
c_pal = c_pal.replace(target_open, replace_open, 1)

target_redraw_pal = '''            for i, (item, desc) in enumerate(self._matches):
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
                    self.mount(Static(f'{marker}[{accent}]\u2726[/] {disp_item}  [dim]{disp_desc}[/dim]', classes=classes))'''

replace_redraw_pal = '''            is_compact = (palette_w < 70)
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
                    self.mount(Static(f'{marker}[{accent}]\u2726[/] {disp_item} [dim]{disp_desc}[/dim]', classes=classes))'''

assert target_redraw_pal in c_pal, "target_redraw_pal not found in palette.py"
c_pal = c_pal.replace(target_redraw_pal, replace_redraw_pal, 1)

with open(path_pal, "w", encoding="utf-8") as f:
    f.write(c_pal)
print("Updated calc_terminal/ui/palette.py")

# 2. Update command_palette.py
path_cmd = os.path.join(ROOT, "calc_terminal/ui/command_palette.py")
with open(path_cmd, "r", encoding="utf-8") as f:
    c_cmd = f.read()

target_redraw_cmd = '''            for i, (item, desc) in enumerate(self._matches):
                is_sel = (i == self._selected)
                classes = 'cct-cmd-row' + (' cct-cmd-row-selected' if is_sel else '')
                bar = f'[{accent} b]▶[/] ' if is_sel else '  '
                if item.startswith('/'):
                    color = category_color(item)
                    cmd_label = f'{item:<12}' if len(item) < 12 else f'{item} '
                    avail_desc = max(8, palette_w - len(cmd_label) - 8)
                    disp_desc = (desc[:avail_desc - 1] + '…') if len(desc) > avail_desc else desc
                    self.mount(Static(f'{bar}[{color} b]{cmd_label}[/] [dim]{disp_desc}[/dim]', classes=classes))
                else:
                    avail_item = max(10, int(palette_w * 0.45))
                    disp_item = (item[:avail_item - 1] + '…') if len(item) > avail_item else item
                    avail_desc = max(8, palette_w - len(disp_item) - 10)
                    disp_desc = (desc[:avail_desc - 1] + '…') if len(desc) > avail_desc else desc
                    self.mount(Static(f'{bar}[{accent}]\u2726[/] [b]{disp_item}[/]  [dim]{disp_desc}[/dim]', classes=classes))'''

replace_redraw_cmd = '''            is_compact = (palette_w < 70)
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
                    self.mount(Static(f'{bar}[{accent}]\u2726[/] [b]{disp_item}[/] [dim]{disp_desc}[/dim]', classes=classes))'''

assert target_redraw_cmd in c_cmd, "target_redraw_cmd not found in command_palette.py"
c_cmd = c_cmd.replace(target_redraw_cmd, replace_redraw_cmd, 1)

with open(path_cmd, "w", encoding="utf-8") as f:
    f.write(c_cmd)
print("Updated calc_terminal/ui/command_palette.py")

