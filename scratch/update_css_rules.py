import sys

sys.stdout.reconfigure(encoding='utf-8')

# 1. Update app.py
with open("calc_terminal/ui/app.py", "r", encoding="utf-8") as f:
    app_text = f.read()

app_text = app_text.replace("\r\n", "\n")

target_marker = "#cct-dash-columns.mode-portrait-single {"
assert target_marker in app_text, "target_marker not found in app.py"

extra_css = """#cct-header-explorer-btn {
    display: none;
    height: 1;
    min-height: 1;
    max-height: 1;
    border: none;
    background: transparent;
    color: $accent;
    padding: 0 1;
    min-width: 4;
}
#cct-header-explorer-btn:hover {
    background: $accent 35%;
    color: #ffffff;
}
#cct-brandheader.is-portrait #cct-header-explorer-btn,
.is-portrait #cct-header-explorer-btn {
    display: block;
}
#cct-brandheader.is-portrait #cct-header-right-box {
    height: 1;
    min-height: 1;
    max-height: 1;
    width: auto;
    layout: horizontal;
    align: right middle;
}
#cct-tb-close {
    height: 1;
    min-height: 1;
    max-height: 1;
    border: none;
    background: $surface-alt;
    color: $text-muted;
    padding: 0 1;
    min-width: 7;
    text-style: bold;
}
#cct-tb-close:hover {
    color: $error;
    background: $surface-highlight 25%;
}
.is-portrait #cct-cmdpalette,
#cct-workspace.is-portrait #cct-cmdpalette {
    margin-left: 1;
    margin-right: 1;
    padding: 0;
}

"""

app_text = app_text.replace(target_marker, extra_css + target_marker)

with open("calc_terminal/ui/app.py", "w", encoding="utf-8", newline="\r\n") as f:
    f.write(app_text)

print("Updated app.py successfully")

# 2. Update theme_css.py
with open("calc_terminal/ui/theme_css.py", "r", encoding="utf-8") as f:
    theme_text = f.read()

theme_text = theme_text.replace("\r\n", "\n")

theme_extra_css = """
#cct-header-explorer-btn {
    display: none;
    height: 1;
    min-height: 1;
    max-height: 1;
    border: none;
    background: transparent;
    color: $accent;
    padding: 0 1;
    min-width: 4;
}
#cct-header-explorer-btn:hover {
    background: $accent 35%;
    color: #ffffff;
}
#cct-brandheader.is-portrait #cct-header-explorer-btn,
.is-portrait #cct-header-explorer-btn {
    display: block;
}
#cct-brandheader.is-portrait #cct-header-right-box {
    height: 1;
    min-height: 1;
    max-height: 1;
    width: auto;
    layout: horizontal;
    align: right middle;
}
#cct-tb-close {
    height: 1;
    min-height: 1;
    max-height: 1;
    border: none;
    background: $surface-alt;
    color: $text-muted;
    padding: 0 1;
    min-width: 7;
    text-style: bold;
}
#cct-tb-close:hover {
    color: $error;
    background: $surface-highlight 25%;
}
.is-portrait #cct-cmdpalette,
#cct-workspace.is-portrait #cct-cmdpalette {
    margin-left: 1;
    margin-right: 1;
    padding: 0;
}
"""

theme_marker = "/* AI Mode Dynamic 3D Chassis & Skeuomorphic Accent Theming */"
assert theme_marker in theme_text, "theme_marker not found in theme_css.py"
theme_text = theme_text.replace(theme_marker, theme_extra_css + "\n" + theme_marker)

with open("calc_terminal/ui/theme_css.py", "w", encoding="utf-8", newline="\r\n") as f:
    f.write(theme_text)

print("Updated theme_css.py successfully")

