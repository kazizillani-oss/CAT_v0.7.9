# Apply exact UI fixes to app.py and theme_css.py

with open('calc_terminal/ui/app.py', 'r', encoding='utf-8') as f:
    app_text = f.read()

# 1. In app.py: Remove box borders from #cct-header-explorer-btn and #cct-header-right:hover
old_block = """#cct-header-explorer-btn,
.cct-header-tall-bevel {
    border-top: tall #6b7596;
    border-left: tall #565f7c;
    border-bottom: tall #0e0f17;
    border-right: tall #13141f;
}

#cct-header-right:hover {
    background: $surface-alt;
    border-top: tall $accent-lighten-2;
    border-left: tall $accent-lighten-2;
    border-bottom: tall $accent;
    border-right: tall $accent;
    color: #ffffff;
}
.cct-menu-btn:focus { color: $accent; text-style: bold; border-top: tall $accent-lighten-2; border-left: tall $accent-lighten-2; }"""

new_block = """.cct-header-tall-bevel {
    border-top: tall #6b7596;
    border-left: tall #565f7c;
    border-bottom: tall #0e0f17;
    border-right: tall #13141f;
}

#cct-header-explorer-btn {
    border: none;
    background: transparent;
}
#cct-header-explorer-btn:hover {
    background: $surface-alt;
    border: none;
    color: #ffffff;
}

#cct-header-right:hover {
    background: $surface-alt;
    border: none;
    color: #ffffff;
}
.cct-menu-btn:focus { color: $accent; text-style: bold; border-top: heavy $accent-lighten-2; border-left: heavy $accent-lighten-2; border-bottom: heavy $accent; border-right: heavy $accent; }"""

assert old_block in app_text, "app.py old_block not found"
app_text = app_text.replace(old_block, new_block)

# 2. In app.py: Ensure portrait header menu button keeps square 7x3 geometry with heavy 3D bevel
old_portrait_menu = """#cct-brandheader.is-portrait .cct-menu-btn,
#cct-brandheader.is-portrait .cct-menu-btn:hover,
#cct-brandheader.is-portrait .cct-menu-btn:focus,
#cct-brandheader.is-portrait .cct-menu-btn-active {
    width: 3;
    min-width: 3;
    height: 1;
    min-height: 1;
    max-height: 1;
    padding: 0;
    border: none;
    background: $surface-alt;
    margin-right: 1;
}"""

new_portrait_menu = """#cct-brandheader.is-portrait .cct-menu-btn,
#cct-brandheader.is-portrait .cct-menu-btn:hover,
#cct-brandheader.is-portrait .cct-menu-btn:focus,
#cct-brandheader.is-portrait .cct-menu-btn-active {
    width: 7;
    min-width: 7;
    max-width: 7;
    height: 3;
    min-height: 3;
    max-height: 3;
    padding: 0;
    border: heavy;
    border-top: heavy #6b7596;
    border-left: heavy #565f7c;
    border-bottom: heavy #0e0f17;
    border-right: heavy #13141f;
    background: $surface;
    margin-right: 1;
}"""

if old_portrait_menu in app_text:
    app_text = app_text.replace(old_portrait_menu, new_portrait_menu)
    print("Updated portrait menu in app.py")

# Also check line 2422 duplicate in app.py:
old_portrait_menu2 = """#cct-brandheader.is-portrait .cct-menu-btn {
    width: 3;
    min-width: 3;
    height: 1;
    min-height: 1;
    padding: 0;
    border: none;
    background: $surface-alt;
    margin-right: 1;
}"""

new_portrait_menu2 = """#cct-brandheader.is-portrait .cct-menu-btn {
    width: 7;
    min-width: 7;
    max-width: 7;
    height: 3;
    min-height: 3;
    max-height: 3;
    padding: 0;
    border: heavy;
    border-top: heavy #6b7596;
    border-left: heavy #565f7c;
    border-bottom: heavy #0e0f17;
    border-right: heavy #13141f;
    background: $surface;
    margin-right: 1;
}"""

if old_portrait_menu2 in app_text:
    app_text = app_text.replace(old_portrait_menu2, new_portrait_menu2)
    print("Updated duplicate portrait menu in app.py")

with open('calc_terminal/ui/app.py', 'w', encoding='utf-8') as f:
    f.write(app_text)
print("Saved calc_terminal/ui/app.py")

# 3. In theme_css.py: Remove tall border from #cct-header-explorer-btn
with open('calc_terminal/ui/theme_css.py', 'r', encoding='utf-8') as f:
    theme_text = f.read()

old_theme_explorer = """#cct-header-explorer-btn {
    display: none;
    height: 3;
    min-height: 3;
    max-height: 3;
    width: 6;
    min-width: 6;
    max-width: 6;
    padding: 0;
    content-align: center middle;
    align: center middle;
    border: tall;
    border-top: tall #6b7596;
    border-left: tall #565f7c;
    border-bottom: tall #0e0f17;
    border-right: tall #13141f;
    background: transparent;
    color: $accent;
}
#cct-header-explorer-btn:hover {
    background: $accent 24%;
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-bottom: tall $accent-darken-3;
    border-right: tall $accent-darken-2;
    color: #ffffff;
}
#cct-header-explorer-btn:focus,
#cct-header-explorer-btn.-active {
    background: #12131c;
    border-top: tall #0e0f17;
    border-left: tall #13141f;
    border-bottom: tall #6b7596;
    border-right: tall #565f7c;
}"""

new_theme_explorer = """#cct-header-explorer-btn {
    display: none;
    height: 3;
    min-height: 3;
    max-height: 3;
    width: 5;
    min-width: 5;
    max-width: 5;
    padding: 0;
    content-align: center middle;
    align: center middle;
    border: none;
    background: transparent;
    color: $accent;
}
#cct-header-explorer-btn:hover {
    background: $surface-alt;
    border: none;
    color: #ffffff;
}
#cct-header-explorer-btn:focus,
#cct-header-explorer-btn.-active {
    background: $surface-dark;
    border: none;
}"""

assert old_theme_explorer in theme_text, "theme_css.py old_theme_explorer not found"
theme_text = theme_text.replace(old_theme_explorer, new_theme_explorer)

with open('calc_terminal/ui/theme_css.py', 'w', encoding='utf-8') as f:
    f.write(theme_text)
print("Saved calc_terminal/ui/theme_css.py")

