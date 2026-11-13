with open("calc_terminal/ui/cat_greeting.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_tail = [
    "    # Landscape mode: clean compact 2-line greeting WITHOUT 3D ASCII block art\n",
    "    # and WITHOUT awkward truncation (e.g. no slicing words into '...')\n",
    '    mode_part = f"[{accent_hex} b]{mode_icon} {mode_label} Mode[/] · " if mode_label else ""\n',
    '    line1 = f"  [{accent_hex} b]/\\_/\\ [/] {mode_part}[b]{data[\'period_icon\']} Routine {data[\'time_str\']}[/]  [{text_faint_hex}]{data[\'period_name\']}[/]"\n',
    '    line2 = f"  [{accent_hex} b](o.o)[/] [{accent_hex} b]{short_greeting}[/]"\n',
    '    return f"{line1}\\n{line2}"\n',
]

lines[486:] = new_tail

with open("calc_terminal/ui/cat_greeting.py", "w", encoding="utf-8") as f:
    f.writelines(lines)

print("SUCCESS: cat_greeting.py lines updated")

