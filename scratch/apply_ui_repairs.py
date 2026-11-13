# Scratch script to apply UI 3D skeuomorphic and layout repairs to app.py and theme_css.py
import re

print("Starting UI repair patch...")

# --- 1. Patch calc_terminal/ui/app.py ---
with open("calc_terminal/ui/app.py", "r", encoding="utf-8") as f:
    app_code = f.read()

# Composer default and mode border colors:
old_composer_block = """#cct-composer {
    dock: bottom;
    background: #181926;
    border: heavy;
    border-top: heavy #6b7596;
    border-left: heavy #565f7c;
    border-bottom: heavy #24283b;
    border-right: heavy #2a2e42;
    tint: transparent;
    padding: 0 1;
    margin: 0 1 1 1;
    height: auto;
    min-height: 0;
    max-height: 85%;
    width: 1fr;
    layout: vertical;
    overflow: hidden;
    overflow-x: hidden;
    overflow-y: hidden;
    transition: border 120ms, tint 120ms;
}
#cct-composer:hover {
    tint: transparent;
}
#cct-composer:focus-within {
    background: #181926;
    border: heavy;
    border-top: heavy #f7d794;
    border-left: heavy #e0af68;
    border-bottom: heavy #5c3d14;
    border-right: heavy #8c5d20;
    tint: transparent;
}

/* AI Mode Dynamic 3D Chassis & Skeuomorphic Bevel Borders */
#cct-composer.cct-mode-build {
    border: heavy;
    border-top: heavy #f7d794;
    border-left: heavy #e0af68;
    border-bottom: heavy #5c3d14;
    border-right: heavy #8c5d20;
}
#cct-composer.cct-mode-build:focus-within {
    border: heavy;
    border-top: heavy #ffeaa7;
    border-left: heavy #fab387;
    border-bottom: heavy #5c3d14;
    border-right: heavy #8c5d20;
}
#cct-composer.cct-mode-notebook {
    border: heavy;
    border-top: heavy #a5c3ff;
    border-left: heavy #7aa2f7;
    border-bottom: heavy #1e2850;
    border-right: heavy #344882;
}
#cct-composer.cct-mode-notebook:focus-within {
    border: heavy;
    border-top: heavy #bfd5ff;
    border-left: heavy #89b4fa;
    border-bottom: heavy #1e2850;
    border-right: heavy #344882;
}
#cct-composer.cct-mode-research {
    border: heavy;
    border-top: heavy #ff94c2;
    border-left: heavy #ff75a0;
    border-bottom: heavy #4d1030;
    border-right: heavy #7a1c4e;
}
#cct-composer.cct-mode-research:focus-within {
    border: heavy;
    border-top: heavy #ffaecf;
    border-left: heavy #ff85c0;
    border-bottom: heavy #4d1030;
    border-right: heavy #7a1c4e;
}
#cct-composer.cct-mode-plan {
    border: heavy;
    border-top: heavy #bbf285;
    border-left: heavy #9ece6a;
    border-bottom: heavy #233b12;
    border-right: heavy #416124;
}
#cct-composer.cct-mode-plan:focus-within {
    border: heavy;
    border-top: heavy #cdf59f;
    border-left: heavy #a6e3a1;
    border-bottom: heavy #233b12;
    border-right: heavy #416124;
}
#cct-composer.cct-mode-debugger {
    border: heavy;
    border-top: heavy #ff5978;
    border-left: heavy #dc143c;
    border-bottom: heavy #450612;
    border-right: heavy #6e0d20;
}
#cct-composer.cct-mode-debugger:focus-within {
    border: heavy;
    border-top: heavy #ffa1b2;
    border-left: heavy #f38ba8;
    border-bottom: heavy #450612;
    border-right: heavy #6e0d20;
}
#cct-composer.cct-mode-agent {
    border: heavy;
    border-top: heavy #d8c2ff;
    border-left: heavy #bb9af7;
    border-bottom: heavy #302054;
    border-right: heavy #543b8a;
}
#cct-composer.cct-mode-agent:focus-within {
    border: heavy;
    border-top: heavy #ebd5ff;
    border-left: heavy #cba6f7;
    border-bottom: heavy #302054;
    border-right: heavy #543b8a;
}"""

new_composer_block = """#cct-composer {
    dock: bottom;
    background: #181926;
    border: heavy;
    border-top: heavy #6b7596;
    border-left: heavy #565f7c;
    border-bottom: heavy #3b4261;
    border-right: heavy #4a5278;
    tint: transparent;
    padding: 0 1;
    margin: 0 1 1 1;
    height: auto;
    min-height: 0;
    max-height: 85%;
    width: 1fr;
    layout: vertical;
    overflow: hidden;
    overflow-x: hidden;
    overflow-y: hidden;
    transition: border 120ms, tint 120ms;
}
#cct-composer:hover {
    tint: transparent;
}
#cct-composer:focus-within {
    background: #181926;
    border: heavy;
    border-top: heavy #f7d794;
    border-left: heavy #e0af68;
    border-bottom: heavy #8c551c;
    border-right: heavy #b07028;
    tint: transparent;
}

/* AI Mode Dynamic 3D Chassis & Skeuomorphic Bevel Borders */
#cct-composer.cct-mode-build {
    border: heavy;
    border-top: heavy #f7d794;
    border-left: heavy #e0af68;
    border-bottom: heavy #8c551c;
    border-right: heavy #b07028;
}
#cct-composer.cct-mode-build:focus-within {
    border: heavy;
    border-top: heavy #ffeaa7;
    border-left: heavy #fab387;
    border-bottom: heavy #8c551c;
    border-right: heavy #b07028;
}
#cct-composer.cct-mode-notebook {
    border: heavy;
    border-top: heavy #a5c3ff;
    border-left: heavy #7aa2f7;
    border-bottom: heavy #2b3e7a;
    border-right: heavy #3d569e;
}
#cct-composer.cct-mode-notebook:focus-within {
    border: heavy;
    border-top: heavy #bfd5ff;
    border-left: heavy #89b4fa;
    border-bottom: heavy #2b3e7a;
    border-right: heavy #3d569e;
}
#cct-composer.cct-mode-research {
    border: heavy;
    border-top: heavy #ff94c2;
    border-left: heavy #ff75a0;
    border-bottom: heavy #801f4c;
    border-right: heavy #a82d68;
}
#cct-composer.cct-mode-research:focus-within {
    border: heavy;
    border-top: heavy #ffaecf;
    border-left: heavy #ff85c0;
    border-bottom: heavy #801f4c;
    border-right: heavy #a82d68;
}
#cct-composer.cct-mode-plan {
    border: heavy;
    border-top: heavy #bbf285;
    border-left: heavy #9ece6a;
    border-bottom: heavy #3f6212;
    border-right: heavy #5b8a24;
}
#cct-composer.cct-mode-plan:focus-within {
    border: heavy;
    border-top: heavy #cdf59f;
    border-left: heavy #a6e3a1;
    border-bottom: heavy #3f6212;
    border-right: heavy #5b8a24;
}
#cct-composer.cct-mode-debugger {
    border: heavy;
    border-top: heavy #ff5978;
    border-left: heavy #dc143c;
    border-bottom: heavy #801024;
    border-right: heavy #a81a34;
}
#cct-composer.cct-mode-debugger:focus-within {
    border: heavy;
    border-top: heavy #ffa1b2;
    border-left: heavy #f38ba8;
    border-bottom: heavy #801024;
    border-right: heavy #a81a34;
}
#cct-composer.cct-mode-agent {
    border: heavy;
    border-top: heavy #d8c2ff;
    border-left: heavy #bb9af7;
    border-bottom: heavy #543b8a;
    border-right: heavy #7052b4;
}
#cct-composer.cct-mode-agent:focus-within {
    border: heavy;
    border-top: heavy #ebd5ff;
    border-left: heavy #cba6f7;
    border-bottom: heavy #543b8a;
    border-right: heavy #7052b4;
}"""

assert old_composer_block.replace("\r\n", "\n") in app_code.replace("\r\n", "\n"), "Failed to find old_composer_block in app.py"
app_code = app_code.replace("\r\n", "\n").replace(old_composer_block.replace("\r\n", "\n"), new_composer_block)

# Footer button keycap backgrounds:
old_footer_btns = """Button#btn-permissions {
    background: transparent;
    color: $accent;
    border: none;
}
Button#btn-attach {
    background: transparent;
    color: $accent;
    border: none;
    margin-left: 0;
}"""

new_footer_btns = """Button#btn-permissions {
    background: #24283b;
    color: $accent;
    border: none;
}
Button#btn-attach {
    background: #24283b;
    color: $accent;
    border: none;
    margin-left: 0;
}"""

assert old_footer_btns in app_code, "Failed to find old_footer_btns in app.py"
app_code = app_code.replace(old_footer_btns, new_footer_btns)

# Header landscape 3D recessed card plates for permission and workspace:
old_header_pills = """/* CENTER: Sleek borderless Permission pill (border: none; only menu icon has square border) */
.cct-perm-pill {
    width: auto; content-align: center middle; height: 3;
    padding: 0 2; margin: 0;
    background: transparent;
    border: none;
    text-style: bold;
    color: $text;
    transition: color 120ms, background 120ms;
}
.cct-perm-pill:hover {
    background: $surface-alt;
    color: $accent;
    border: none;
}
.cct-perm-pill.-active, .cct-perm-pill-active, .cct-perm-pill:focus {
    background: $surface-dark;
    color: $accent;
    border: none;
}

.cct-chat-title-pill {
    width: auto; max-width: 30; content-align: center middle; height: 3;
    padding: 0 2; margin: 0 1 0 1;
    background: transparent;
    border: none;
    color: $text;
    text-style: bold;
    overflow: hidden;
    text-overflow: ellipsis;
    transition: color 120ms, background 120ms;
}
.cct-chat-title-pill:hover {
    background: $surface-alt;
    color: #ffffff;
    border: none;
}
.cct-chat-title-pill:focus, .cct-chat-title-pill.-active {
    background: $surface-dark;
    border: none;
}

/* RIGHT: Sleek borderless workspace path chip */
#cct-header-right {
    width: auto; max-width: 32; content-align: center middle;
    padding: 0 2; height: 3;
    background: transparent;
    border: none;
    overflow: hidden;
    text-overflow: ellipsis;
    text-style: bold;
    color: $text;
    transition: background 120ms, color 120ms;
}
#cct-header-right:hover {
    background: $surface-alt;
    color: $accent;
    border: none;
}
#cct-header-right:focus, #cct-header-right.-active {
    background: $surface-dark;
    color: $accent;
    border: none;
}"""

new_header_pills = """/* CENTER: Sleek Permission pill with subtle 3D recessed card plate */
.cct-perm-pill {
    width: auto; content-align: center middle; height: 3;
    padding: 0 2; margin: 0;
    background: $surface;
    border: solid #2a2e42 #0e0f17 #0e0f17 #2a2e42;
    text-style: bold;
    color: $text;
    transition: color 120ms, background 120ms, border 120ms;
}
.cct-perm-pill:hover {
    background: $surface-alt;
    color: $accent;
    border: solid #3b4261 #14151f #14151f #3b4261;
}
.cct-perm-pill.-active, .cct-perm-pill-active, .cct-perm-pill:focus {
    background: $surface-dark;
    color: $accent;
    border: solid #0e0f17 #2a2e42 #2a2e42 #0e0f17;
}

.cct-chat-title-pill {
    width: auto; max-width: 30; content-align: center middle; height: 3;
    padding: 0 2; margin: 0 1 0 1;
    background: $surface;
    border: solid #2a2e42 #0e0f17 #0e0f17 #2a2e42;
    color: $text;
    text-style: bold;
    overflow: hidden;
    text-overflow: ellipsis;
    transition: color 120ms, background 120ms, border 120ms;
}
.cct-chat-title-pill:hover {
    background: $surface-alt;
    color: #ffffff;
    border: solid #3b4261 #14151f #14151f #3b4261;
}
.cct-chat-title-pill:focus, .cct-chat-title-pill.-active {
    background: $surface-dark;
    border: solid #0e0f17 #2a2e42 #2a2e42 #0e0f17;
}

/* RIGHT: Sleek workspace path chip with matching 3D recessed card plate */
#cct-header-right {
    width: auto; max-width: 32; content-align: center middle;
    padding: 0 2; height: 3;
    background: $surface;
    border: solid #2a2e42 #0e0f17 #0e0f17 #2a2e42;
    overflow: hidden;
    text-overflow: ellipsis;
    text-style: bold;
    color: $text;
    transition: background 120ms, color 120ms, border 120ms;
}
#cct-header-right:hover {
    background: $surface-alt;
    color: $accent;
    border: solid #3b4261 #14151f #14151f #3b4261;
}
#cct-header-right:focus, #cct-header-right.-active {
    background: $surface-dark;
    color: $accent;
    border: solid #0e0f17 #2a2e42 #2a2e42 #0e0f17;
}"""

assert old_header_pills in app_code, "Failed to find old_header_pills in app.py"
app_code = app_code.replace(old_header_pills, new_header_pills)

# Remove .cct-perm-pill:focus { border: round $accent; }
app_code = app_code.replace(".cct-perm-pill:focus { border: round $accent; }", ".cct-perm-pill:focus { border: solid #0e0f17 #2a2e42 #2a2e42 #0e0f17; }")

# Compact starting height for composer:
app_code = app_code.replace("#cct-composer { min-height: 8; }", "#cct-composer { min-height: 5; }")

# Portrait responsive rules consolidation (ensuring height: 3 for header top, left, right-box, menu-btn, explorer-btn):
portrait_old = """/* -------------------- PORTRAIT RESPONSIVE RULES -------------------- */
#cct-brandheader.is-portrait {
    height: 4;
    padding: 0 1;
    border-bottom: solid $border;
}
#cct-brandheader.is-portrait .cct-menu-btn,
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
}
#cct-brandheader.is-portrait .cct-perm-pill,
#cct-brandheader.is-portrait .cct-perm-pill:hover,
#cct-brandheader.is-portrait .cct-perm-pill:focus,
#cct-brandheader.is-portrait .cct-perm-pill-active {
    height: 1;
    min-height: 1;
    max-height: 1;
    width: auto;
    padding: 0 1;
    border: none;
    background: $surface-alt;
}
#cct-brandheader.is-portrait #cct-header-right,
#cct-brandheader.is-portrait #cct-header-right:hover,
#cct-brandheader.is-portrait #cct-header-right:focus {
    height: 1;
    min-height: 1;
    max-height: 1;
    padding: 0 1;
    border: none;
    background: $surface-alt;
}
#cct-sidebar-back-btn {
    display: none;
    height: 1;
    min-height: 1;
    max-height: 1;
    border: none;
    background: $surface-alt;
    color: $accent;
    padding: 0 1;
    margin-right: 1;
}
#cct-sidebar.is-portrait #cct-sidebar-back-btn,
.is-portrait #cct-sidebar-back-btn {
    display: block;
}
#cct-tb-back {
    display: none;
    height: 1;
    min-height: 1;
    max-height: 1;
    border: none;
    background: $surface-alt;
    color: $accent;
    padding: 0 1;
    margin-right: 1;
    text-style: bold;
}
.is-portrait #cct-tb-back,
#cct-workspace.is-portrait #cct-tb-back {
    display: block;
}
.is-portrait #cct-tb-split,
#cct-workspace.is-portrait #cct-tb-split {
    display: none;
}
#cct-brandheader.is-portrait #cct-header-top {
    height: 1;
    align-vertical: middle;
    align: left middle;
}
#cct-brandheader.is-portrait #cct-header-left {
    height: 1;
    align-vertical: middle;
}
#cct-brandheader.is-portrait .cct-menu-btn {
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
}
#cct-brandheader.is-portrait .cct-menu-btn:hover {
    background: $accent 24%;
    color: $accent;
}
#cct-brandheader.is-portrait .cct-logo {
    height: 1;
    min-height: 1;
    padding: 0 1;
}
#cct-brandheader.is-portrait .cct-perm-pill {
    height: 1;
    min-height: 1;
    max-height: 1;
    width: auto;
    padding: 0 1;
    border: none;
    background: $surface-alt;
}
#cct-brandheader.is-portrait .cct-perm-pill:hover {
    background: $accent 24%;
}
#cct-brandheader.is-portrait #cct-header-right {
    height: 1;
    min-height: 1;
    max-height: 1;
    padding: 0 1;
    border: none;
    background: $surface-alt;
}

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
}"""

portrait_new = """/* -------------------- PORTRAIT RESPONSIVE RULES -------------------- */
#cct-brandheader.is-portrait {
    height: 4;
    padding: 0 1;
    border-bottom: solid $border;
}
#cct-brandheader.is-portrait #cct-header-top {
    height: 3;
    align-vertical: middle;
    align: left middle;
}
#cct-brandheader.is-portrait #cct-header-left {
    height: 3;
    align-vertical: middle;
}
#cct-brandheader.is-portrait .cct-menu-btn,
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
}
#cct-brandheader.is-portrait .cct-menu-btn:hover {
    background: $accent 24%;
    color: $accent;
}
#cct-brandheader.is-portrait .cct-logo {
    height: 3;
    min-height: 3;
    max-height: 3;
    padding: 0 1;
    content-align: left middle;
}
#cct-brandheader.is-portrait .cct-perm-pill,
#cct-brandheader.is-portrait .cct-perm-pill:hover,
#cct-brandheader.is-portrait .cct-perm-pill:focus,
#cct-brandheader.is-portrait .cct-perm-pill-active {
    height: 3;
    min-height: 3;
    max-height: 3;
    width: auto;
    padding: 0 1;
    border: solid #2a2e42 #0e0f17 #0e0f17 #2a2e42;
    background: $surface;
    content-align: center middle;
}
#cct-brandheader.is-portrait #cct-header-right,
#cct-brandheader.is-portrait #cct-header-right:hover,
#cct-brandheader.is-portrait #cct-header-right:focus {
    display: none;
}
#cct-brandheader.is-portrait #cct-header-right-box {
    height: 3;
    min-height: 3;
    max-height: 3;
    width: auto;
    layout: horizontal;
    align: right middle;
}
#cct-sidebar-back-btn {
    display: none;
    height: 1;
    min-height: 1;
    max-height: 1;
    border: none;
    background: $surface-alt;
    color: $accent;
    padding: 0 1;
    margin-right: 1;
}
#cct-sidebar.is-portrait #cct-sidebar-back-btn,
.is-portrait #cct-sidebar-back-btn {
    display: block;
}
#cct-tb-back {
    display: none;
    height: 1;
    min-height: 1;
    max-height: 1;
    border: none;
    background: $surface-alt;
    color: $accent;
    padding: 0 1;
    margin-right: 1;
    text-style: bold;
}
.is-portrait #cct-tb-back,
#cct-workspace.is-portrait #cct-tb-back {
    display: block;
}
.is-portrait #cct-tb-split,
#cct-workspace.is-portrait #cct-tb-split {
    display: none;
}
#cct-header-explorer-btn {
    display: none;
    height: 3;
    min-height: 3;
    max-height: 3;
    width: 7;
    min-width: 7;
    max-width: 7;
    padding: 0;
    border: heavy;
    border-top: heavy #6b7596;
    border-left: heavy #565f7c;
    border-bottom: heavy #0e0f17;
    border-right: heavy #13141f;
    background: $surface;
    color: $accent;
    content-align: center middle;
}
#cct-header-explorer-btn:hover {
    background: $surface-alt;
    color: #ffffff;
}
#cct-brandheader.is-portrait #cct-header-explorer-btn,
.is-portrait #cct-header-explorer-btn {
    display: block;
}"""

assert portrait_old in app_code, "Failed to find portrait_old in app.py"
app_code = app_code.replace(portrait_old, portrait_new)

with open("calc_terminal/ui/app.py", "w", encoding="utf-8") as f:
    f.write(app_code)
print("Updated calc_terminal/ui/app.py successfully.")


# --- 2. Patch calc_terminal/ui/theme_css.py ---
with open("calc_terminal/ui/theme_css.py", "r", encoding="utf-8") as f:
    css_code = f.read()

# Update theme_css mode borders
theme_replacements = [
    # default composer focus-within bottom/right:
    ("border-bottom: heavy #5c3d14;\n    border-right: heavy #8c5d20;", "border-bottom: heavy #8c551c;\n    border-right: heavy #b07028;"),
    # notebook mode:
    ("border-bottom: heavy #1e2850;\n    border-right: heavy #344882;", "border-bottom: heavy #2b3e7a;\n    border-right: heavy #3d569e;"),
    # research mode:
    ("border-bottom: heavy #4d1030;\n    border-right: heavy #7a1c4e;", "border-bottom: heavy #801f4c;\n    border-right: heavy #a82d68;"),
    # plan mode:
    ("border-bottom: heavy #233b12;\n    border-right: heavy #416124;", "border-bottom: heavy #3f6212;\n    border-right: heavy #5b8a24;"),
    # debugger mode:
    ("border-bottom: heavy #450612;\n    border-right: heavy #6e0d20;", "border-bottom: heavy #801024;\n    border-right: heavy #a81a34;"),
    # agent mode:
    ("border-bottom: heavy #302054;\n    border-right: heavy #543b8a;", "border-bottom: heavy #543b8a;\n    border-right: heavy #7052b4;"),
    # default composer normal:
    ("border-bottom: heavy #24283b;\n    border-right: heavy #2a2e42;", "border-bottom: heavy #3b4261;\n    border-right: heavy #4a5278;"),
]

for old_s, new_s in theme_replacements:
    css_code = css_code.replace(old_s, new_s)

# Update permissions and attach buttons background to #24283b in theme_css.py:
old_btn_perm = """Button#btn-permissions,
Button#btn-permissions:ansi.-style-default {
    height: 1; min-height: 1; max-height: 1;
    min-width: 3; max-width: 3; width: 3; padding: 0; margin: 0;
    background: transparent; color: $text;"""

new_btn_perm = """Button#btn-permissions,
Button#btn-permissions:ansi.-style-default {
    height: 1; min-height: 1; max-height: 1;
    min-width: 3; max-width: 3; width: 3; padding: 0; margin: 0;
    background: #24283b; color: $text;"""

old_btn_att = """Button#btn-attach,
Button#btn-attach:ansi.-style-default {
    height: 1; min-height: 1; max-height: 1;
    min-width: 3; max-width: 3; width: 3; padding: 0; margin: 0;
    background: transparent; color: $text;"""

new_btn_att = """Button#btn-attach,
Button#btn-attach:ansi.-style-default {
    height: 1; min-height: 1; max-height: 1;
    min-width: 3; max-width: 3; width: 3; padding: 0; margin: 0;
    background: #24283b; color: $text;"""

css_code = css_code.replace(old_btn_perm, new_btn_perm)
css_code = css_code.replace(old_btn_att, new_btn_att)

with open("calc_terminal/ui/theme_css.py", "w", encoding="utf-8") as f:
    f.write(css_code)
print("Updated calc_terminal/ui/theme_css.py successfully.")


# --- 3. Patch calc_terminal/tests/test_composer_3d_and_dialog_fixes.py ---
with open("calc_terminal/tests/test_composer_3d_and_dialog_fixes.py", "r", encoding="utf-8") as f:
    test_code = f.read()

old_test_modes = """        modes = [
            ("cct-mode-build", "#ffeaa7", "#fab387", "#5c3d14", "#8c5d20"),
            ("cct-mode-notebook", "#bfd5ff", "#89b4fa", "#1e2850", "#344882"),
            ("cct-mode-research", "#ffaecf", "#ff85c0", "#4d1030", "#7a1c4e"),
            ("cct-mode-plan", "#cdf59f", "#a6e3a1", "#233b12", "#416124"),
            ("cct-mode-debugger", "#ffa1b2", "#f38ba8", "#450612", "#6e0d20"),
            ("cct-mode-agent", "#ebd5ff", "#cba6f7", "#302054", "#543b8a"),
        ]"""

new_test_modes = """        modes = [
            ("cct-mode-build", "#ffeaa7", "#fab387", "#8c551c", "#b07028"),
            ("cct-mode-notebook", "#bfd5ff", "#89b4fa", "#2b3e7a", "#3d569e"),
            ("cct-mode-research", "#ffaecf", "#ff85c0", "#801f4c", "#a82d68"),
            ("cct-mode-plan", "#cdf59f", "#a6e3a1", "#3f6212", "#5b8a24"),
            ("cct-mode-debugger", "#ffa1b2", "#f38ba8", "#801024", "#a81a34"),
            ("cct-mode-agent", "#ebd5ff", "#cba6f7", "#543b8a", "#7052b4"),
        ]"""

assert old_test_modes in test_code, "Failed to find old_test_modes in test_composer_3d_and_dialog_fixes.py"
test_code = test_code.replace(old_test_modes, new_test_modes)

with open("calc_terminal/tests/test_composer_3d_and_dialog_fixes.py", "w", encoding="utf-8") as f:
    f.write(test_code)
print("Updated calc_terminal/tests/test_composer_3d_and_dialog_fixes.py successfully.")
print("All patches applied!")

