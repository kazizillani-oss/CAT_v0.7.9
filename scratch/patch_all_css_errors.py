import re
import os

print("--- 1. Patching theme_css.py ---")
with open("calc_terminal/ui/theme_css.py", "r", encoding="utf-8") as f:
    tcss = f.read()

# Add aliases in css_variables()
var_anchor = 'out["accent-dark"] = out["accent-shadow"]'
if var_anchor in tcss and 'accent-lighten-2' not in tcss:
    var_extra = '''out["accent-dark"] = out["accent-shadow"]
    out["accent-lighten-2"] = out.get("accent-light", out.get("accent-highlight", "#89b4fa"))
    out["accent-lighten-1"] = out.get("accent-light", out.get("accent-highlight", "#89b4fa"))
    out["accent-darken-2"] = blend_hex(s_rgb, (0, 0, 0), 0.5)
    out["accent-darken-3"] = blend_hex(s_rgb, (0, 0, 0), 0.65)
    out["surface-darken-1"] = out.get("surface-dark", "#181825")
    out["surface-darken-2"] = blend_hex(s_rgb, (0, 0, 0), 0.5)'''
    tcss = tcss.replace(var_anchor, var_extra, 1)

# Replace hyphenated variable opacities in theme_css.py
replacements_tcss = [
    ("tint: $surface-highlight 6%;", "tint: $accent 6%;"),
    ("tint: $surface-highlight 8%;", "tint: $accent 8%;"),
    ("tint: $app-background 22%;", "tint: $border 22%;"),
    ("tint: $surface-dark 18%;", "tint: $border 18%;"),
    ("tint: $surface-highlight 3%;", "tint: $accent 3%;"),
    ("tint: $surface-highlight 4%;", "tint: $accent 4%;"),
    ("tint: $surface-highlight 5%;", "tint: $accent 5%;"),
    ("tint: $app-background 20%;", "tint: $border 20%;"),
    ("tint: $app-background 18%;", "tint: $border 18%;"),
    ("background: $surface-highlight 40%;", "background: $accent 20%;"),
    ("background: $surface-highlight 25%;", "background: $accent 18%;"),
    ("background: $app-background 65%;", "background: rgba(17, 17, 27, 0.65);"),
]
for src, dst in replacements_tcss:
    tcss = tcss.replace(src, dst)

with open("calc_terminal/ui/theme_css.py", "w", encoding="utf-8") as f:
    f.write(tcss)
print("theme_css.py updated successfully!")

print("--- 2. Patching memory_center.py ---")
with open("calc_terminal/ui/memory_center.py", "r", encoding="utf-8") as f:
    memcss = f.read()

memcss = memcss.replace("gap: 1;", "")
with open("calc_terminal/ui/memory_center.py", "w", encoding="utf-8") as f:
    f.write(memcss)
print("memory_center.py updated successfully!")

print("--- 3. Patching app.py ---")
with open("calc_terminal/ui/app.py", "r", encoding="utf-8") as f:
    appcss = f.read()

# Fix line 672 hover rule
appcss = appcss.replace(
    "background: -highlight 25%;\n    color: #ffffff;\n    border-left: thick ;",
    "background: $accent 18%;\n    color: #ffffff;\n    border-left: thick $accent;"
)
appcss = appcss.replace(
    "background: -highlight 25%;\r\n    color: #ffffff;\r\n    border-left: thick ;",
    "background: $accent 18%;\r\n    color: #ffffff;\r\n    border-left: thick $accent;"
)

# Fix lines 1303-1422 (3D header buttons & chips)
old_header_css = """/* LEFT: 3D raised menu button + logo */
.cct-menu-btn {
    width: 5; min-width: 5; height: 3; color: ; content-align: center middle;
    background: ;
    border-top: solid #7a7f9a;
    border-left: solid #6c7086;
    border-bottom: solid #11111b;
    border-right: solid #181825;
    margin-right: 1;
    transition: color 120ms, border 120ms, background 120ms;
}
.cct-menu-btn:hover {
    color: ;
    background: -alt;
    border-top: solid -lighten-2;
    border-left: solid ;
    border-bottom: solid #11111b;
    border-right: solid #181825;
}
.cct-menu-btn.-active, .cct-menu-btn-active, .cct-menu-btn:focus {
    color: ;
    background: -dark;
    border-top: solid #11111b;
    border-left: solid #181825;
    border-bottom: solid #7a7f9a;
    border-right: solid #6c7086;
    text-style: none;
}
.cct-logo { width: auto; padding: 0 1; content-align: left middle; height: 3; text-style: bold; }

/* CENTER: 3D raised Permission pill - dead centered */
.cct-perm-pill {
    width: auto; content-align: center middle; height: 3;
    padding: 0 2; margin: 0;
    background: ;
    border-top: solid #7a7f9a;
    border-left: solid #6c7086;
    border-bottom: solid #11111b;
    border-right: solid #181825;
    text-style: bold;
    color: ;
    transition: border 120ms, color 120ms, background 120ms;
}
.cct-perm-pill:hover {
    background: -alt;
    border-top: solid -lighten-2;
    border-left: solid ;
    border-bottom: solid #11111b;
    border-right: solid #181825;
    color: #ffffff;
}
.cct-perm-pill.-active, .cct-perm-pill:focus, .cct-perm-pill-active {
    background: -dark;
    border-top: solid #11111b;
    border-left: solid #181825;
    border-bottom: solid #7a7f9a;
    border-right: solid #6c7086;
    color: ;
}

.cct-chat-title-pill {
    width: auto; max-width: 30; content-align: center middle; height: 3;
    padding: 0 2; margin: 0 1 0 1;
    background: ;
    border-top: solid #7a7f9a;
    border-left: solid #6c7086;
    border-bottom: solid #11111b;
    border-right: solid #181825;
    color: ;
    text-style: bold;
    overflow: hidden;
    text-overflow: ellipsis;
    transition: border 120ms, color 120ms, background 120ms;
}
.cct-chat-title-pill:hover {
    background: -alt;
    border-top: solid -lighten-2;
    border-left: solid ;
    border-bottom: solid #11111b;
    border-right: solid #181825;
    color: #ffffff;
}
.cct-chat-title-pill:focus, .cct-chat-title-pill.-active {
    background: -dark;
    border-top: solid #11111b;
    border-left: solid #181825;
    border-bottom: solid #7a7f9a;
    border-right: solid #6c7086;
}

/* RIGHT: 3D raised workspace path chip — cleanly aligned with permission pill */
#cct-header-right {
    width: auto; max-width: 32; content-align: center middle;
    padding: 0 2; height: 3;
    background: ;
    border-top: solid #7a7f9a;
    border-left: solid #6c7086;
    border-bottom: solid #11111b;
    border-right: solid #181825;
    overflow: hidden;
    text-overflow: ellipsis;
    text-style: bold;
    color: ;
    transition: background 120ms, border 120ms, color 120ms;
}
#cct-header-right:hover {
    background: -alt;
    border-top: solid -lighten-2;
    border-left: solid ;
    border-bottom: solid #11111b;
    border-right: solid #181825;
    color: #ffffff;
}
#cct-header-right:focus, #cct-header-right.-active {
    background: -dark;
    border-top: solid #11111b;
    border-left: solid #181825;
    border-bottom: solid #7a7f9a;
    border-right: solid #6c7086;
}"""

new_header_css = """/* LEFT: 3D raised menu button + logo */
.cct-menu-btn {
    width: 5; min-width: 5; height: 3; color: $text; content-align: center middle;
    background: $surface;
    border-top: solid #7a7f9a;
    border-left: solid #6c7086;
    border-bottom: solid #11111b;
    border-right: solid #181825;
    margin-right: 1;
    transition: color 120ms, border 120ms, background 120ms;
}
.cct-menu-btn:hover {
    color: $accent;
    background: $surface-alt;
    border-top: solid #ffffff;
    border-left: solid $accent-highlight;
    border-bottom: solid #11111b;
    border-right: solid #181825;
}
.cct-menu-btn.-active, .cct-menu-btn-active, .cct-menu-btn:focus {
    color: $accent;
    background: $surface-dark;
    border-top: solid #11111b;
    border-left: solid #181825;
    border-bottom: solid #7a7f9a;
    border-right: solid #6c7086;
    text-style: none;
}
.cct-logo { width: auto; padding: 0 1; content-align: left middle; height: 3; text-style: bold; }

/* CENTER: 3D raised Permission pill - dead centered */
.cct-perm-pill {
    width: auto; content-align: center middle; height: 3;
    padding: 0 2; margin: 0;
    background: $surface;
    border-top: solid #7a7f9a;
    border-left: solid #6c7086;
    border-bottom: solid #11111b;
    border-right: solid #181825;
    text-style: bold;
    color: $text;
    transition: border 120ms, color 120ms, background 120ms;
}
.cct-perm-pill:hover {
    background: $surface-alt;
    border-top: solid #ffffff;
    border-left: solid $accent-highlight;
    border-bottom: solid #11111b;
    border-right: solid #181825;
    color: #ffffff;
}
.cct-perm-pill.-active, .cct-perm-pill:focus, .cct-perm-pill-active {
    background: $surface-dark;
    border-top: solid #11111b;
    border-left: solid #181825;
    border-bottom: solid #7a7f9a;
    border-right: solid #6c7086;
    color: $accent;
}

.cct-chat-title-pill {
    width: auto; max-width: 30; content-align: center middle; height: 3;
    padding: 0 2; margin: 0 1 0 1;
    background: $surface;
    border-top: solid #7a7f9a;
    border-left: solid #6c7086;
    border-bottom: solid #11111b;
    border-right: solid #181825;
    color: $text;
    text-style: bold;
    overflow: hidden;
    text-overflow: ellipsis;
    transition: border 120ms, color 120ms, background 120ms;
}
.cct-chat-title-pill:hover {
    background: $surface-alt;
    border-top: solid #ffffff;
    border-left: solid $accent-highlight;
    border-bottom: solid #11111b;
    border-right: solid #181825;
    color: #ffffff;
}
.cct-chat-title-pill:focus, .cct-chat-title-pill.-active {
    background: $surface-dark;
    border-top: solid #11111b;
    border-left: solid #181825;
    border-bottom: solid #7a7f9a;
    border-right: solid #6c7086;
}

/* RIGHT: 3D raised workspace path chip — cleanly aligned with permission pill */
#cct-header-right {
    width: auto; max-width: 32; content-align: center middle;
    padding: 0 2; height: 3;
    background: $surface;
    border-top: solid #7a7f9a;
    border-left: solid #6c7086;
    border-bottom: solid #11111b;
    border-right: solid #181825;
    overflow: hidden;
    text-overflow: ellipsis;
    text-style: bold;
    color: $text;
    transition: background 120ms, border 120ms, color 120ms;
}
#cct-header-right:hover {
    background: $surface-alt;
    border-top: solid #ffffff;
    border-left: solid $accent-highlight;
    border-bottom: solid #11111b;
    border-right: solid #181825;
    color: #ffffff;
}
#cct-header-right:focus, #cct-header-right.-active {
    background: $surface-dark;
    border-top: solid #11111b;
    border-left: solid #181825;
    border-bottom: solid #7a7f9a;
    border-right: solid #6c7086;
}"""

# Normalize CRLF and replace
old_h_clean = old_header_css.replace("\r\n", "\n")
app_clean = appcss.replace("\r\n", "\n")
if old_h_clean in app_clean:
    app_clean = app_clean.replace(old_h_clean, new_header_css.replace("\r\n", "\n"))
    print("Replaced 3D header CSS in app.py successfully!")
else:
    print("Warning: old_header_css not found exactly in app.py, attempting regex/flexible replacement")
    # Search start and end
    p_start = app_clean.find("/* LEFT: 3D raised menu button + logo */")
    p_end = app_clean.find("/* --------------------------------------------------------------- sidebar -- */")
    if p_start != -1 and p_end != -1:
        app_clean = app_clean[:p_start] + new_header_css.replace("\r\n", "\n") + "\n\n" + app_clean[p_end:]
        print("Replaced 3D header block by slice in app.py!")

# Fix other broken variable opacities in app.py
app_replacements = [
    ("background: $surface-highlight 40%;", "background: $accent 20%;"),
    ("background: $surface-highlight 25%;", "background: $accent 18%;"),
    ("tint: $surface-highlight 6%;", "tint: $accent 6%;"),
    ("tint: $surface-highlight 3%;", "tint: $accent 3%;"),
    ("tint: $surface-highlight 4%;", "tint: $accent 4%;"),
    ("tint: $app-background 20%;", "tint: $border 20%;"),
    ("background: $app-background 75%;", "background: rgba(17, 17, 27, 0.75);"),
    ("background: $app-background 70%;", "background: rgba(17, 17, 27, 0.70);"),
    ("border-top: tall $accent-lighten-2;", "border-top: tall $accent-highlight;"),
    ("border-left: tall $accent-lighten-2;", "border-left: tall $accent-highlight;"),
]
for src, dst in app_replacements:
    app_clean = app_clean.replace(src, dst)

# Fix #cct-editor-stack height: 1fr -> height: auto;
app_clean = app_clean.replace(
    """#cct-editor-stack {
    width: 1fr;
    height: 1fr;
    min-height: 1;
    max-height: 100%;
    background: transparent;
    border: none;
    padding: 0;
}
#cct-input, #cct-input:focus, ComposerInput, ComposerInput:focus, #cct-editor-stack, #cct-editor-stack:focus {
    width: 1fr;
    height: 1fr;
    min-height: 1;
    max-height: 100%;
    background: transparent;
    border: none;
    color: $text;
    outline: none;
}""",
    """#cct-editor-stack {
    width: 1fr;
    height: auto;
    min-height: 1;
    max-height: 12;
    background: transparent;
    border: none;
    padding: 0;
}
#cct-input, #cct-input:focus, ComposerInput, ComposerInput:focus {
    width: 1fr;
    height: auto;
    min-height: 1;
    max-height: 12;
    background: transparent;
    border: none;
    color: $text;
    outline: none;
}"""
)

# Fix portrait header height strictly to 1 line
app_clean = app_clean.replace(
    """#cct-brandheader.is-portrait {
    height: 2;
    padding: 0 1;
    border-bottom: solid $border;
}""",
    """#cct-brandheader.is-portrait {
    height: 1;
    min-height: 1;
    max-height: 1;
    padding: 0 1;
    border-bottom: solid $border;
}"""
)

with open("calc_terminal/ui/app.py", "w", encoding="utf-8") as f:
    f.write(app_clean)
print("app.py updated successfully!")

