def patch_scrollbar(path):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    orig = content
    content = content.replace("scrollbar-color: $accent $surface;", "scrollbar-color: $accent transparent;\n    scrollbar-background: transparent;")
    content = content.replace("scrollbar-color-hover: $accent $surface;", "scrollbar-color-hover: $accent transparent;")
    if content != orig:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Updated scrollbar in {path}")
    else:
        print(f"No changes in {path}")

patch_scrollbar("calc_terminal/ui/app.py")
patch_scrollbar("calc_terminal/ui/theme_css.py")

