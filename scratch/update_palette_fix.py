import sys

sys.stdout.reconfigure(encoding='utf-8')

# 1. Update command_palette.py
with open("calc_terminal/ui/command_palette.py", "r", encoding="utf-8", newline="") as f:
    cp_lines = f.readlines()

new_cp = []
skip = False
for line in cp_lines:
    if "def _redraw(self):" in line:
        skip = True
        new_cp.append(line)
        new_cp.append("            from . import theme_css\r\n")
        new_cp.append("            accent = theme_css.current_hex('accent')\r\n")
        new_cp.append("            for child in list(self.children):\r\n")
        new_cp.append("                child.remove()\r\n")
        new_cp.append("            try:\r\n")
        new_cp.append("                palette_w = self.size.width if (self.size and self.size.width > 0) else 0\r\n")
        new_cp.append("                if not palette_w and self.parent and self.parent.size:\r\n")
        new_cp.append("                    palette_w = self.parent.size.width - 4\r\n")
        new_cp.append("                if not palette_w:\r\n")
        new_cp.append("                    palette_w = 80\r\n")
        new_cp.append("            except Exception:\r\n")
        new_cp.append("                palette_w = 80\r\n")
        new_cp.append("            for i, (item, desc) in enumerate(self._matches):\r\n")
        new_cp.append("                is_sel = (i == self._selected)\r\n")
        new_cp.append("                classes = 'cct-cmd-row' + (' cct-cmd-row-selected' if is_sel else '')\r\n")
        new_cp.append("                bar = f'[{accent} b]▶[/] ' if is_sel else '  '\r\n")
        new_cp.append("                if item.startswith('/'):\r\n")
        new_cp.append("                    color = category_color(item)\r\n")
        new_cp.append("                    cmd_label = f'{item:<12}' if len(item) < 12 else f'{item} '\r\n")
        new_cp.append("                    avail_desc = max(8, palette_w - len(cmd_label) - 8)\r\n")
        new_cp.append("                    disp_desc = (desc[:avail_desc - 1] + '…') if len(desc) > avail_desc else desc\r\n")
        new_cp.append("                    self.mount(Static(f'{bar}[{color} b]{cmd_label}[/] [dim]{disp_desc}[/dim]', classes=classes))\r\n")
        new_cp.append("                else:\r\n")
        new_cp.append("                    avail_item = max(10, int(palette_w * 0.45))\r\n")
        new_cp.append("                    disp_item = (item[:avail_item - 1] + '…') if len(item) > avail_item else item\r\n")
        new_cp.append("                    avail_desc = max(8, palette_w - len(disp_item) - 10)\r\n")
        new_cp.append("                    disp_desc = (desc[:avail_desc - 1] + '…') if len(desc) > avail_desc else desc\r\n")
        new_cp.append("                    self.mount(Static(f'{bar}[{accent}]\\u2726[/] [b]{disp_item}[/]  [dim]{disp_desc}[/dim]', classes=classes))\r\n")
        continue
    if skip:
        if line.startswith("else:") or line.startswith("    CommandPalette = None"):
            skip = False
            new_cp.append(line)
        continue
    new_cp.append(line)

with open("calc_terminal/ui/command_palette.py", "w", encoding="utf-8", newline="") as f:
    f.writelines(new_cp)

print("Updated command_palette.py successfully")

# 2. Update palette.py
with open("calc_terminal/ui/palette.py", "r", encoding="utf-8", newline="") as f:
    pal_lines = f.readlines()

new_pal = []
skip_redraw = False
skip_open = False
for line in pal_lines:
    if "def open_for_query(self, query):" in line:
        skip_open = True
        new_pal.append(line)
        new_pal.append("            self._matches = SuggestionEngine.match(query)\r\n")
        new_pal.append("            if not self._matches:\r\n")
        new_pal.append("                self.close()\r\n")
        new_pal.append("                return\r\n")
        new_pal.append("            self._selected = min(self._selected, len(self._matches) - 1)\r\n")
        new_pal.append("            self._redraw()\r\n")
        new_pal.append("            self.add_class('open')\r\n")
        new_pal.append("            try:\r\n")
        new_pal.append("                screen_h = getattr(getattr(self.app, 'size', None), 'height', 30)\r\n")
        new_pal.append("                max_rows = 5 if screen_h < 40 else 7\r\n")
        new_pal.append("            except Exception:\r\n")
        new_pal.append("                max_rows = 6\r\n")
        new_pal.append("            self.styles.height = min(max_rows, max(3, len(self._matches)))\r\n")
        new_pal.append("            self.scroll_home(animate=False)\r\n")
        new_pal.append("            if self.parent and hasattr(self.parent, '_on_palette_state_changed'):\r\n")
        new_pal.append("                self.parent._on_palette_state_changed(True)\r\n")
        continue
    if skip_open:
        if "def close(self):" in line:
            skip_open = False
            new_pal.append(line)
        continue

    if "def _redraw(self):" in line:
        skip_redraw = True
        new_pal.append(line)
        new_pal.append("            from . import theme_css\r\n")
        new_pal.append("            accent = theme_css.current_hex('accent')\r\n")
        new_pal.append("            for child in list(self.children):\r\n")
        new_pal.append("                child.remove()\r\n")
        new_pal.append("            try:\r\n")
        new_pal.append("                palette_w = self.size.width if (self.size and self.size.width > 0) else 0\r\n")
        new_pal.append("                if not palette_w and self.parent and self.parent.size:\r\n")
        new_pal.append("                    palette_w = self.parent.size.width - 4\r\n")
        new_pal.append("                if not palette_w:\r\n")
        new_pal.append("                    palette_w = 80\r\n")
        new_pal.append("            except Exception:\r\n")
        new_pal.append("                palette_w = 80\r\n")
        new_pal.append("            for i, (item, desc) in enumerate(self._matches):\r\n")
        new_pal.append("                classes = 'cct-cmd-row' + (' cct-cmd-row-selected' if i == self._selected else '')\r\n")
        new_pal.append("                marker = '▶ ' if i == self._selected else '  '\r\n")
        new_pal.append("                if item.startswith('/'):\r\n")
        new_pal.append("                    cmd_pad = f'{item:<12}' if len(item) < 12 else f'{item} '\r\n")
        new_pal.append("                    avail_desc = max(8, palette_w - len(cmd_pad) - 8)\r\n")
        new_pal.append("                    disp_desc = (desc[:avail_desc - 1] + '…') if len(desc) > avail_desc else desc\r\n")
        new_pal.append("                    self.mount(Static(f'{marker}[{accent} b]{cmd_pad}[/]  [dim]{disp_desc}[/dim]', classes=classes))\r\n")
        new_pal.append("                else:\r\n")
        new_pal.append("                    avail_item = max(10, int(palette_w * 0.45))\r\n")
        new_pal.append("                    disp_item = (item[:avail_item - 1] + '…') if len(item) > avail_item else item\r\n")
        new_pal.append("                    avail_desc = max(8, palette_w - len(disp_item) - 10)\r\n")
        new_pal.append("                    disp_desc = (desc[:avail_desc - 1] + '…') if len(desc) > avail_desc else desc\r\n")
        new_pal.append("                    self.mount(Static(f'{marker}[{accent}]\\u2726[/] {disp_item}  [dim]{disp_desc}[/dim]', classes=classes))\r\n")
        continue
    if skip_redraw:
        if line.startswith("else:") or line.startswith("    CommandPalette = None"):
            skip_redraw = False
            new_pal.append(line)
        continue
    new_pal.append(line)

with open("calc_terminal/ui/palette.py", "w", encoding="utf-8", newline="") as f:
    f.writelines(new_pal)

print("Updated palette.py successfully")

