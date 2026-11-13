# 1. Patch palette.py
with open("calc_terminal/ui/palette.py", "r", encoding="utf-8") as f:
    p_content = f.read()

p_norm = p_content.replace("\r\n", "\n")
t_pal = """            try:
                screen_h = getattr(getattr(self.app, 'size', None), 'height', 30)
                max_items = 4 if screen_h < 32 else (5 if screen_h < 40 else 7)
            except Exception:
                max_items = 5
            visible_rows = min(max_items, len(self._matches))
            self.styles.height = max(4, visible_rows + 2)
            self.scroll_home(animate=False)"""

r_pal = """            try:
                screen_h = getattr(getattr(self.app, 'size', None), 'height', 30)
                max_items = 5 if screen_h < 26 else (6 if screen_h < 34 else 8)
            except Exception:
                max_items = 6
            visible_rows = min(max_items, len(self._matches))
            self.styles.height = max(5, visible_rows + 2)
            self.styles.max_height = 12
            self.scroll_home(animate=False)"""

t_pal_w = """            is_compact = (palette_w < 70)
            for i, (item, desc) in enumerate(self._matches):
                classes = 'cct-cmd-row' + (' cct-cmd-row-selected' if i == self._selected else '')
                marker = '▶ ' if i == self._selected else '  '
                if item.startswith('/'):
                    cmd_pad = f'{item}  ' if is_compact else (f'{item:<12}' if len(item) < 12 else f'{item} ')
                    avail_desc = max(8, palette_w - len(cmd_pad) - 5)
                    disp_desc = (desc[:avail_desc - 1] + '…') if len(desc) > avail_desc else desc
                    self.mount(Static(f'{marker}[{accent} b]{cmd_pad}[/][dim]{disp_desc}[/dim]', classes=classes))"""

r_pal_w = """            try:
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
                    self.mount(Static(f'{marker}[{accent} b]{cmd_pad}[/][dim]{disp_desc}[/dim]', classes=classes))"""

assert t_pal in p_norm, "Target pal not found"
p_norm = p_norm.replace(t_pal, r_pal, 1)
if t_pal_w in p_norm:
    p_norm = p_norm.replace(t_pal_w, r_pal_w, 1)

if "\r\n" in p_content:
    p_norm = p_norm.replace("\n", "\r\n")

with open("calc_terminal/ui/palette.py", "w", encoding="utf-8") as f:
    f.write(p_norm)
print("SUCCESS: palette.py updated")

# 2. Patch command_palette.py
with open("calc_terminal/ui/command_palette.py", "r", encoding="utf-8") as f:
    cp_content = f.read()

cp_norm = cp_content.replace("\r\n", "\n")
t_cp = """            is_compact = (palette_w < 70)
            for i, (item, desc) in enumerate(self._matches):
                is_sel = (i == self._selected)
                classes = 'cct-cmd-row' + (' cct-cmd-row-selected' if is_sel else '')
                bar = f'[{accent} b]▶[/] ' if is_sel else '  '
                if item.startswith('/'):
                    color = category_color(item)
                    cmd_label = f'{item}  ' if is_compact else (f'{item:<12}' if len(item) < 12 else f'{item} ')
                    avail_desc = max(8, palette_w - len(cmd_label) - 5)
                    disp_desc = (desc[:avail_desc - 1] + '…') if len(desc) > avail_desc else desc
                    self.mount(Static(f'{bar}[{color} b]{cmd_label}[/][dim]{disp_desc}[/dim]', classes=classes))"""

r_cp = """            try:
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
                    self.mount(Static(f'{bar}[{color} b]{cmd_label}[/][dim]{disp_desc}[/dim]', classes=classes))"""

assert t_cp in cp_norm, "Target cp not found"
cp_norm = cp_norm.replace(t_cp, r_cp, 1)

if "\r\n" in cp_content:
    cp_norm = cp_norm.replace("\n", "\r\n")

with open("calc_terminal/ui/command_palette.py", "w", encoding="utf-8") as f:
    f.write(cp_norm)
print("SUCCESS: command_palette.py updated")

# 3. Patch composer.py _on_palette_state_changed
with open("calc_terminal/ui/composer.py", "r", encoding="utf-8") as f:
    comp_content = f.read()

comp_norm = comp_content.replace("\r\n", "\n")
t_comp = """        def _on_palette_state_changed(self, is_open):
            if is_open:
                if self._explicit_height is None:
                    self.styles.height = "auto"
                    self.styles.max_height = "80%"
            else:
                if self._explicit_height is None:
                    self.styles.height = "auto"
                    self.styles.max_height = "75%" """

# Let's locate _on_palette_state_changed dynamically
idx = comp_norm.find("def _on_palette_state_changed(self, is_open):")
if idx != -1:
    end_idx = comp_norm.find("def _on_permission_panel_toggled", idx)
    r_comp = """        def _on_palette_state_changed(self, is_open):
            if is_open:
                self.styles.height = "auto"
                self.styles.max_height = "85%"
            else:
                if self._explicit_height is None:
                    self.styles.height = "auto"
                    self.styles.max_height = "32%"
                else:
                    self.styles.height = self._explicit_height
                    self.styles.max_height = "100%"
\n"""
    comp_norm = comp_norm[:idx] + r_comp + comp_norm[end_idx:]
    if "\r\n" in comp_content:
        comp_norm = comp_norm.replace("\n", "\r\n")
    with open("calc_terminal/ui/composer.py", "w", encoding="utf-8") as f:
        f.write(comp_norm)
    print("SUCCESS: composer.py updated")

