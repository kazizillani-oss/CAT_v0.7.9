import sys

sys.stdout.reconfigure(encoding='utf-8')

with open("calc_terminal/ui/footer.py", "r", encoding="utf-8", newline="") as f:
    lines = f.readlines()

new_lines = []
in_mode_markup = False
in_resize = False

for line in lines:
    if "def _mode_badge_markup(self, mode_key):" in line:
        in_mode_markup = True
        new_lines.append(line)
        new_lines.append("            accent = ai_modes.accent_hex(mode_key)\r\n")
        new_lines.append("            m = ai_modes.meta(mode_key)\r\n")
        new_lines.append("            raw_icon = m.get('icon', '')\r\n")
        new_lines.append("            if raw_icon in ('🛠️', '🛠'):\r\n")
        new_lines.append("                raw_icon = '🔨'\r\n")
        new_lines.append("            clean_icon = raw_icon.replace('\\ufe0f', '')\r\n")
        new_lines.append("            safe_icon = _safe_glyph(clean_icon, '[B]')\r\n")
        new_lines.append("            try:\r\n")
        new_lines.append("                gs, ge = ai_modes.gradient(mode_key)\r\n")
        new_lines.append("                bar = ''.join(f'[{_hex_blend(gs, ge, t)}]\\u25ae[/]'\r\n")
        new_lines.append("                              for t in (0.0, 0.33, 0.66, 1.0))\r\n")
        new_lines.append("                return f'{bar} [{gs} b]{safe_icon}[/] [{ge} b]{m[\"label\"]}[/]'\r\n")
        new_lines.append("            except Exception:\r\n")
        new_lines.append("                return f'[{accent} b]{safe_icon} {m[\"label\"]}[/]'\r\n")
        continue

    if in_mode_markup:
        if "def compose(self):" in line:
            in_mode_markup = False
            new_lines.append(line)
        continue

    if "def on_resize(self, event=None):" in line:
        in_resize = True
        new_lines.append(line)
        new_lines.append('            """Responsive footer collapse at narrow viewports: ensures send button never gets pushed off and controls never clip."""\r\n')
        new_lines.append('            w = (event.size.width if event else None) or (self.size.width if self.size else 80)\r\n')
        new_lines.append('            try:\r\n')
        new_lines.append('                center = self.query_one("#cct-center-status", Static)\r\n')
        new_lines.append('                center.display = (w >= 80)\r\n')
        new_lines.append('                center.update(self._status_text(w))\r\n')
        new_lines.append('            except Exception:\r\n')
        new_lines.append('                pass\r\n')
        new_lines.append('            try:\r\n')
        new_lines.append('                model_badge = self.query_one("#badge-model", _Badge)\r\n')
        new_lines.append('                sep = self.query_one(".cct-badge-sep", Static)\r\n')
        new_lines.append('                if w < 55:\r\n')
        new_lines.append('                    model_badge.display = False\r\n')
        new_lines.append('                    sep.display = False\r\n')
        new_lines.append('                elif w < 75:\r\n')
        new_lines.append('                    model_badge.display = True\r\n')
        new_lines.append('                    sep.display = True\r\n')
        new_lines.append('                    clean = self._shorten_model_label(self._model_label, w)\r\n')
        new_lines.append('                    if len(clean) > 10:\r\n')
        new_lines.append('                        clean = clean[:9] + "…"\r\n')
        new_lines.append('                    model_badge.update(clean)\r\n')
        new_lines.append('                else:\r\n')
        new_lines.append('                    model_badge.display = True\r\n')
        new_lines.append('                    sep.display = True\r\n')
        new_lines.append('                    display_label = self._shorten_model_label(self._model_label, w)\r\n')
        new_lines.append('                    model_badge.update(display_label)\r\n')
        new_lines.append('            except Exception:\r\n')
        new_lines.append('                pass\r\n')
        continue

    if in_resize:
        if "class StatusLine" in line:
            in_resize = False
            new_lines.append(line)
        continue

    new_lines.append(line)

with open("calc_terminal/ui/footer.py", "w", encoding="utf-8", newline="") as f:
    f.writelines(new_lines)

print("Updated footer.py line-by-line successfully")
