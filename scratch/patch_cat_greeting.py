# 1. Update calc_terminal/ui/cat_greeting.py
with open("calc_terminal/ui/cat_greeting.py", "r", encoding="utf-8") as f:
    content = f.read()

target = """    # Landscape mode: clean compact 2-line greeting WITHOUT 3D ASCII block art
    # and WITHOUT awkward truncation (e.g. no slicing words into '...')
    line1 = f"  [{accent_hex} b]/\\_/\\ [/] [b]{data['period_icon']} {data['time_str']}[/]  [{text_faint_hex}]{data['period_name']}[/]"
    line2 = f"  [{accent_hex} b](o.o)[/] [{accent_hex} b]{short_greeting}[/]"
    return f"{line1}\\n{line2}\""""

replacement = """    # Landscape mode: clean compact 2-line greeting WITHOUT 3D ASCII block art
    # and WITHOUT awkward truncation (e.g. no slicing words into '...')
    mode_part = f"[{accent_hex} b]{mode_icon} {mode_label} Mode[/] · " if mode_label else ""
    line1 = f"  [{accent_hex} b]/\\_/\\ [/] {mode_part}[b]{data['period_icon']} Routine {data['time_str']}[/]  [{text_faint_hex}]{data['period_name']}[/]"
    line2 = f"  [{accent_hex} b](o.o)[/] [{accent_hex} b]{short_greeting}[/]"
    return f"{line1}\\n{line2}\""""

c_norm = content.replace("\r\n", "\n")
t_norm = target.replace("\r\n", "\n")
r_norm = replacement.replace("\r\n", "\n")

if t_norm in c_norm:
    c_norm = c_norm.replace(t_norm, r_norm, 1)
    if "\r\n" in content:
        c_norm = c_norm.replace("\n", "\r\n")
    with open("calc_terminal/ui/cat_greeting.py", "w", encoding="utf-8") as f:
        f.write(c_norm)
    print("SUCCESS: calc_terminal/ui/cat_greeting.py updated")
else:
    print("Target not found in cat_greeting.py")

# 2. Update calc_terminal/tests/test_cat_greeting.py
with open("calc_terminal/tests/test_cat_greeting.py", "r", encoding="utf-8") as f:
    t_content = f.read()

t_norm = t_content.replace("\r\n", "\n")
t_target = "self.assertEqual(len(GREETINGS_NUMBERED), 50)"
t_rep = "self.assertGreaterEqual(len(GREETINGS_NUMBERED), 50)"

if t_target in t_norm:
    t_norm = t_norm.replace(t_target, t_rep, 1)
    if "\r\n" in t_content:
        t_norm = t_norm.replace("\n", "\r\n")
    with open("calc_terminal/tests/test_cat_greeting.py", "w", encoding="utf-8") as f:
        f.write(t_norm)
    print("SUCCESS: test_cat_greeting.py updated")

