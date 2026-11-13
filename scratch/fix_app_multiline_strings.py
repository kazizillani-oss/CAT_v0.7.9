with open('calc_terminal/ui/app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    if 'self._system_note(f"📊 Project Architecture Summary:' in line:
        new_lines.append('                self._system_note(f"📊 Project Architecture Summary:\\n• Files: {summ[\'total_files\']} ({ext_str})\\n• Total Lines: {summ[\'total_lines\']:,}\\n• Classes: {summ[\'total_classes\']} | Functions: {summ[\'total_functions\']}")\n')
        # Skip until the line ending with '}")'
        while i < len(lines) and '}")' not in lines[i]:
            i += 1
        i += 1
        continue
    elif 'self._system_note(f"⚠️ Detected' in line and not line.endswith(')\n'):
        # Check if multiline
        accum = line
        while i + 1 < len(lines) and ')' not in lines[i]:
            i += 1
            accum += lines[i]
        # Cleanly format with \n
        new_lines.append('                    msg = f"⚠️ Detected {len(findings)} Potential Secrets:\\n" + "\\n".join(f"• [{f[\'severity\']}] {f[\'type\']} at {f[\'file\']}:{f[\'line\']} ({f[\'masked\']})" for f in findings[:8])\n                    self._system_note(msg)\n')
        i += 1
        continue
    new_lines.append(line)
    i += 1

with open('calc_terminal/ui/app.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Cleaned up multiline f-strings in app.py!")

