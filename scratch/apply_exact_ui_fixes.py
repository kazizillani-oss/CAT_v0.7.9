# scratch/apply_exact_ui_fixes.py
import re

# 1. Update app.py
with open('calc_terminal/ui/app.py', 'r', encoding='utf-8') as f:
    app_text = f.read()

# Target 1: composer borders & modes
old_composer_block = """#cct-composer {
    background: $surface;
    border: heavy $border;
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
    transition: border 120ms, tint 120ms, offset 90ms;
}
#cct-composer:hover {
    tint: transparent;
}
#cct-composer:focus-within {
    background: $surface;
    border: heavy $border-active;
    tint: transparent;
}

#cct-composer,
#cct-composer:focus-within,
#cct-composer.cct-mode-notebook,
#cct-composer.cct-mode-research,
#cct-composer.cct-mode-plan,
#cct-composer.cct-mode-build,
#cct-composer.cct-mode-debugger,
#cct-composer.cct-mode-agent {
    background: $surface;
}"""

new_composer_block = """#cct-composer {
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
}

#cct-composer,
#cct-composer:focus-within,
#cct-composer.cct-mode-notebook,
#cct-composer.cct-mode-research,
#cct-composer.cct-mode-plan,
#cct-composer.cct-mode-build,
#cct-composer.cct-mode-debugger,
#cct-composer.cct-mode-agent {
    background: #181926;
}"""

assert old_composer_block in app_text, "old_composer_block not found!"
app_text = app_text.replace(old_composer_block, new_composer_block)

# Target 2: input area background / highlight
old_input_block = """#cct-prompt-row {
    height: auto;
    min-height: 1;
    max-height: 100%;
    align-vertical: top;
    padding: 0 1;
    margin: 0;
    background: transparent;
    border: none;
}
#cct-prompt-row:focus-within {
    background: transparent;
    border: none;
}
#cct-prompt-glyph {
    width: 2;
    min-width: 2;
    max-width: 2;
    color: #e0af68;
    text-style: bold;
    content-align: left middle;
}
#cct-editor-stack {
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
}"""

new_input_block = """#cct-prompt-row {
    height: auto;
    min-height: 1;
    max-height: 100%;
    align-vertical: top;
    padding: 0 1;
    margin: 0;
    background: transparent;
    tint: transparent;
    border: none;
}
#cct-prompt-row:focus-within {
    background: transparent;
    tint: transparent;
    border: none;
}
#cct-prompt-glyph {
    width: 2;
    min-width: 2;
    max-width: 2;
    color: #e0af68;
    text-style: bold;
    content-align: left middle;
}
#cct-editor-stack {
    width: 1fr;
    height: 1fr;
    min-height: 1;
    max-height: 100%;
    background: transparent;
    tint: transparent;
    border: none;
    padding: 0;
    margin: 0;
    overflow: hidden;
}
#cct-editor-stack:focus-within {
    background: transparent;
    tint: transparent;
    border: none;
}
#cct-input, #cct-input:focus, ComposerInput, ComposerInput:focus,
#cct-input > .text-area--cursor-line, ComposerInput > .text-area--cursor-line {
    width: 1fr;
    height: 1fr;
    min-height: 1;
    max-height: 100%;
    background: transparent;
    border: none;
    color: $text;
    outline: none;
}"""

assert old_input_block in app_text, "old_input_block not found!"
app_text = app_text.replace(old_input_block, new_input_block)

# Target 3: Header square border ONLY on menu button
old_header_block = """/* LEFT: 3D raised menu button + logo */
.cct-menu-btn {
    width: 7; min-width: 7; max-width: 7;
    height: 3; min-height: 3; max-height: 3;
    color: $text; content-align: center middle;
    background: $surface;
    border: heavy;
    border-top: heavy #6b7596;
    border-left: heavy #565f7c;
    border-bottom: heavy #0e0f17;
    border-right: heavy #13141f;
    margin-right: 1;
    transition: color 120ms, border 120ms, background 120ms;
}
.cct-menu-btn:hover {
    color: $accent;
    background: $surface-alt;
    border: heavy;
    border-top: heavy $accent-lighten-2;
    border-left: heavy $accent-lighten-2;
    border-bottom: heavy $accent;
    border-right: heavy $accent;
}
.cct-menu-btn.-active, .cct-menu-btn-active {
    color: $accent;
    background: $surface-dark;
    border: heavy;
    border-top: heavy #0e0f17;
    border-left: heavy #13141f;
    border-bottom: heavy #6b7596;
    border-right: heavy #565f7c;
    text-style: none;
}
.cct-logo { width: auto; padding: 0 1; content-align: left middle; height: 3; text-style: bold; }

/* CENTER: 3D raised Permission pill - dead centered */
.cct-perm-pill {
    width: auto; content-align: center middle; height: 3;
    padding: 0 2; margin: 0;
    background: $surface;
    border-top: tall $surface-highlight;
    border-left: tall $surface-highlight;
    border-bottom: tall $surface-shadow;
    border-right: tall $surface-shadow;
    text-style: bold;
    color: $text;
    transition: border 120ms, color 120ms, background 120ms;
}
.cct-perm-pill:hover {
    background: $surface-alt;
    border-top: tall $accent-lighten-2;
    border-left: tall $accent-lighten-2;
    border-bottom: tall $accent;
    border-right: tall $accent;
    color: #ffffff;
}
.cct-perm-pill.-active {
    background: $surface-dark;
    border-top: tall $surface-shadow;
    border-left: tall $surface-shadow;
    border-bottom: tall $surface-highlight;
    border-right: tall $surface-highlight;
    color: $accent;
}
.cct-perm-pill:focus, .cct-perm-pill-active {
    background: $surface-dark;
    border-top: tall $surface-shadow;
    border-left: tall $surface-shadow;
    border-bottom: tall $surface-highlight;
    border-right: tall $surface-highlight;
    color: $accent;
}

.cct-chat-title-pill {
    width: auto; max-width: 30; content-align: center middle; height: 3;
    padding: 0 2; margin: 0 1 0 1;
    background: $surface;
    border-top: tall $surface-highlight;
    border-left: tall $surface-highlight;
    border-bottom: tall $surface-shadow;
    border-right: tall $surface-shadow;
    color: $text;
    text-style: bold;
    overflow: hidden;
    text-overflow: ellipsis;
    transition: border 120ms, color 120ms, background 120ms;
}
.cct-chat-title-pill:hover {
    background: $surface-alt;
    border-top: tall $accent-lighten-2;
    border-left: tall $accent-lighten-2;
    border-bottom: tall $accent;
    border-right: tall $accent;
    color: #ffffff;
}
.cct-chat-title-pill:focus, .cct-chat-title-pill.-active {
    background: $surface-dark;
    border-top: tall $surface-shadow;
    border-left: tall $surface-shadow;
    border-bottom: tall $surface-highlight;
    border-right: tall $surface-highlight;
}

/* RIGHT: 3D raised workspace path chip — cleanly aligned with permission pill */
#cct-header-right {
    width: auto; max-width: 32; content-align: center middle;
    padding: 0 2; height: 3;
    background: $surface;
    border-top: tall $surface-highlight;
    border-left: tall $surface-highlight;
    border-bottom: tall $surface-shadow;
    border-right: tall $surface-shadow;
    overflow: hidden;
    text-overflow: ellipsis;
    text-style: bold;
    color: $text;
    transition: background 120ms, border 120ms, color 120ms;
}
#cct-brandheader .cct-perm-pill,
#cct-brandheader #cct-header-right {
    border-top: tall #6b7596;
    border-left: tall #565f7c;
    border-bottom: tall #0e0f17;
    border-right: tall #13141f;
}"""

new_header_block = """/* LEFT: 3D raised menu button + logo (ONLY main menu icon has square shape border) */
.cct-menu-btn {
    width: 7; min-width: 7; max-width: 7;
    height: 3; min-height: 3; max-height: 3;
    color: $text; content-align: center middle;
    background: $surface;
    border: heavy;
    border-top: heavy #6b7596;
    border-left: heavy #565f7c;
    border-bottom: heavy #0e0f17;
    border-right: heavy #13141f;
    margin-right: 1;
    transition: color 120ms, border 120ms, background 120ms;
}
.cct-menu-btn:hover {
    color: $accent;
    background: $surface-alt;
    border: heavy;
    border-top: heavy $accent-lighten-2;
    border-left: heavy $accent-lighten-2;
    border-bottom: heavy $accent;
    border-right: heavy $accent;
}
.cct-menu-btn.-active, .cct-menu-btn-active {
    color: $accent;
    background: $surface-dark;
    border: heavy;
    border-top: heavy #0e0f17;
    border-left: heavy #13141f;
    border-bottom: heavy #6b7596;
    border-right: heavy #565f7c;
    text-style: none;
}
.cct-logo { width: auto; padding: 0 1; content-align: left middle; height: 3; text-style: bold; }

/* CENTER: Sleek borderless Permission pill (border: none; only menu icon has square border) */
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
}

#cct-header-explorer-btn,
.cct-header-tall-bevel {
    border-top: tall #6b7596;
    border-left: tall #565f7c;
    border-bottom: tall #0e0f17;
    border-right: tall #13141f;
}"""

assert old_header_block in app_text, "old_header_block not found!"
app_text = app_text.replace(old_header_block, new_header_block)

# Target 4: Permission Panel
old_perm_block = """#cct-perm-header {
    height: 1; min-height: 1; layout: horizontal; align-vertical: middle;
    margin-bottom: 1;
}
#cct-perm-title-box { width: auto; layout: horizontal; align-vertical: middle; }
#cct-perm-icon { color: $accent; text-style: bold; margin-right: 1; }
#cct-perm-title { color: $text; text-style: bold; }
#cct-perm-mode-btn {
    height: 1; min-height: 1; max-height: 1; padding: 0 1; margin-left: 2;
    background: $surface-alt; color: $text; text-style: bold;
    border: none;
    border-left: tall $surface-highlight;
    border-right: tall $surface-dark;
    content-align: center middle;
}
Button#cct-perm-mode-btn:hover {
    background: $accent 25%; color: $accent-highlight;
    border: none;
    border-left: tall #ffffff;
    border-right: tall $surface-dark;
}
Button#cct-perm-mode-btn.-active { offset: 0 0; }
#cct-perm-spacer { width: 1fr; }
Button#cct-perm-close {
    height: 1; min-height: 1; max-height: 1; width: 3; min-width: 3; padding: 0; margin: 0;
    color: $text-muted; background: transparent;
    border: none;
    border-left: tall $surface-highlight;
    border-right: tall $surface-dark;
    content-align: center middle;
}
Button#cct-perm-close:hover {
    color: $error; background: $error 20%; text-style: bold;
    border: none;
    border-left: tall #ffffff;
    border-right: tall $surface-dark;
}
Button#cct-perm-close.-active { offset: 0 0; }

#cct-perm-grid {
    height: auto; layout: horizontal;
}
.cct-perm-col {
    width: 1fr; height: auto; padding: 0 1;
}
.cct-perm-col-title {
    color: $accent; text-style: bold; height: 1; margin-bottom: 0;
}
.cct-perm-row {
    height: 1; min-height: 1; layout: horizontal; align-vertical: middle; margin-top: 1;
}
.cct-perm-label {
    width: 1fr; color: $text-muted; height: 1;
}"""

new_perm_block = """#cct-perm-header {
    height: 1; min-height: 1; layout: horizontal; align-vertical: middle;
    margin-bottom: 1;
    border-bottom: solid #3b4261;
}
#cct-perm-title-box { width: auto; layout: horizontal; align-vertical: middle; }
#cct-perm-icon { color: #e0af68; text-style: bold; margin-right: 1; }
#cct-perm-title { color: $text; text-style: bold; }
#cct-perm-mode-btn {
    height: 1; min-height: 1; max-height: 1; padding: 0 1; margin-left: 2;
    background: #1e2030; color: #ffffff; text-style: bold;
    border-top: solid #3b4261;
    border-left: solid #2e344e;
    border-bottom: solid #0e0f17;
    border-right: solid #181926;
    content-align: center middle;
}
Button#cct-perm-mode-btn:hover {
    background: #24283b; color: #ffeaa7;
    border-top: solid #f7d794;
    border-left: solid #e0af68;
    border-bottom: solid #0e0f17;
    border-right: solid #181926;
}
Button#cct-perm-mode-btn.-active { offset: 0 0; }
#cct-perm-spacer { width: 1fr; }
Button#cct-perm-close {
    height: 1; min-height: 1; max-height: 1; width: 3; min-width: 3; padding: 0; margin: 0;
    color: $text-muted; background: transparent;
    border: none;
    border-left: tall #3b4261;
    border-right: tall #0e0f17;
    content-align: center middle;
}
Button#cct-perm-close:hover {
    color: $error; background: $error 20%; text-style: bold;
    border: none;
    border-left: tall #ffffff;
    border-right: tall #0e0f17;
}
Button#cct-perm-close.-active { offset: 0 0; }

#cct-perm-grid {
    height: auto; layout: horizontal;
}
.cct-perm-col {
    width: 1fr; height: auto; padding: 1 1; margin: 0 1;
    background: #14151f;
    border-top: solid #0e0f17;
    border-left: solid #141520;
    border-bottom: solid #3b4261;
    border-right: solid #2e344e;
}
.cct-perm-col-title {
    color: #e0af68; text-style: bold; height: 1; margin-bottom: 0;
    border-bottom: solid #24283b;
}
.cct-perm-row {
    height: 1; min-height: 1; layout: horizontal; align-vertical: middle; margin-top: 1;
}
.cct-perm-label {
    width: 1fr; color: $text-muted; height: 1;
}"""

assert old_perm_block in app_text, "old_perm_block not found!"
app_text = app_text.replace(old_perm_block, new_perm_block)

with open('calc_terminal/ui/app.py', 'w', encoding='utf-8') as f:
    f.write(app_text)
print("Successfully updated app.py!")

# 2. Update header.py
with open('calc_terminal/ui/header.py', 'r', encoding='utf-8') as f:
    header_text = f.read()

old_nav_rows = """.cct-navmenu-row {
            height: 1; padding: 0 2;
            background: $surface;
            color: $text;
            border-left: thick $surface;
            border-right: thick $surface;
        }
        .cct-navmenu-row:hover {
            background: $surface-alt;
            color: $text;
            border-left: thick $accent;
            border-right: thick $surface-alt;
            text-style: none;
        }
        .cct-navmenu-row-selected {
            background: $surface-highlight;
            color: $text;
            border-left: thick $accent;
            border-right: thick $surface-highlight;
            text-style: none;
        }"""

new_nav_rows = """.cct-navmenu-row {
            height: 1; padding: 0 2;
            background: #181926;
            color: $text;
            border-left: thick transparent;
            border-right: none;
            transition: background 60ms, color 60ms, border-left 60ms;
        }
        .cct-navmenu-row:hover {
            background: #1e2030;
            color: #ffffff;
            border-left: thick #3b4261;
        }
        .cct-navmenu-row-selected {
            background: #24283b;
            color: #ffffff;
            border-left: thick #e0af68;
            text-style: bold;
        }"""

if old_nav_rows in header_text:
    header_text = header_text.replace(old_nav_rows, new_nav_rows)

with open('calc_terminal/ui/header.py', 'w', encoding='utf-8') as f:
    f.write(header_text)
print("Successfully updated header.py!")
