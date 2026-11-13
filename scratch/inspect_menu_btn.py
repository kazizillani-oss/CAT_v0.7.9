with open("calc_terminal/ui/app.py", "r", encoding="utf-8") as f:
    text = f.read()

idx = text.find(".cct-menu-btn {")
print("Found .cct-menu-btn { at:", idx)
print(text[idx-60:idx+400])

