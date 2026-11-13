import sys
import re

def update_theme():
    with open('calc_terminal/ui/theme_css.py', 'r', encoding='utf-8') as f:
        text = f.read()

    # 1. cct-composer overflow
    idx = text.find('#cct-composer {\n    background: #181926;\n    border: heavy;')
    assert idx != -1, 'cct-composer in theme_css not found'
    end_idx = text.find('}', idx) + 1
    new_composer = """#cct-composer {
    background: #181926;
    border: heavy;
    border-top: heavy #6b7596;
    border-left: heavy #565f7c;
    border-bottom: heavy #24283b;
    border-right: heavy #2a2e42;
    tint: transparent;
    padding: 0;
    margin: 0 1 1 1;
    overflow: hidden;
    overflow-x: hidden;
    overflow-y: hidden;
    transition: border 120ms, tint 120ms;
}"""
    text = text[:idx] + new_composer + text[end_idx:]

    # 2. cct-right-controls
    rc_idx = text.find('#cct-right-controls {\n    width: auto;\n    min-width: 12;\n    max-width: 20;')
    assert rc_idx != -1, 'cct-right-controls in theme_css not found'
    rc_end = text.find('}', rc_idx) + 1
    new_rc = """#cct-right-controls {
    width: 9;
    min-width: 9;
    max-width: 9;
    height: 1;
    min-height: 1;
    max-height: 1;
    layout: horizontal;
    align-vertical: middle;
    align-horizontal: right;
    margin: 0;
    padding: 0;
    overflow-x: hidden;
    overflow-y: hidden;
    background: transparent;
}"""
    text = text[:rc_idx] + new_rc + text[rc_end:]

    # 3. Button.cct-icon-btn, Button#btn-permissions, Button#btn-attach, Button#btn-send
    btns_idx = text.find('Button.cct-icon-btn, .cct-icon-btn,\nButton.cct-icon-btn:ansi.-style-default,')
    assert btns_idx != -1, 'btns in theme_css not found'
    btns_end = text.find('/* Interrupt Button state during AI Streaming */', btns_idx)
    assert btns_end != -1, 'btns_end in theme_css not found'
    new_btns = """Button.cct-icon-btn, .cct-icon-btn,
Button.cct-icon-btn:ansi.-style-default,
Button.cct-icon-btn:ansi.-style-flat,
Button#btn-permissions,
Button#btn-permissions:ansi.-style-default {
    height: 1; min-height: 1; max-height: 1;
    min-width: 3; max-width: 3; width: 3; padding: 0; margin: 0;
    background: transparent; color: $text;
    border: none;
    text-style: bold;
    content-align: center middle;
    offset: 0 0;
}
Button#btn-attach,
Button#btn-attach:ansi.-style-default {
    height: 1; min-height: 1; max-height: 1;
    min-width: 3; max-width: 3; width: 3; padding: 0; margin: 0;
    background: transparent; color: $text;
    border: none;
    text-style: bold;
    content-align: center middle;
    offset: 0 0;
}
Button.cct-icon-btn:hover, Button#btn-permissions:hover, Button#btn-attach:hover {
    color: #ffffff; background: $accent 35%; text-style: bold;
    border: none;
}
Button.cct-icon-btn:focus, Button#btn-permissions:focus, Button#btn-attach:focus {
    color: $accent-highlight; background: $accent 20%; text-style: bold;
    border: none;
}
Button.cct-icon-btn.-active, Button#btn-permissions.-active, Button#btn-attach.-active {
    background: $accent; color: #ffffff;
    border: none;
    offset: 0 0;
}

Button.cct-icon-send, .cct-icon-send,
Button.cct-icon-send:ansi.-style-default,
Button.cct-icon-send:ansi.-style-flat,
Button#btn-send,
Button#btn-send:ansi.-style-default {
    height: 1; min-height: 1; max-height: 1;
    min-width: 3; max-width: 3; width: 3; padding: 0; margin: 0;
    background: #e0af68; color: #12131d;
    border: none;
    text-style: bold;
    content-align: center middle;
    offset: 0 0;
}
Button.cct-icon-send:hover, Button#btn-send:hover {
    color: #000000; background: #f7d794; text-style: bold;
    border: none;
}
Button.cct-icon-send:focus, Button#btn-send:focus {
    color: #12131d; background: #c68a4c; text-style: bold;
    border: none;
}
Button.cct-icon-send.-active, Button#btn-send.-active {
    background: #c68a4c; color: #12131d;
    border: none;
    offset: 0 0;
}

"""
    text = text[:btns_idx] + new_btns + text[btns_end:]

    # 4. AI Modes 3D Bevels
    modes_start = text.find('#cct-composer.cct-mode-notebook {')
    assert modes_start != -1, 'modes_start in theme_css not found'
    modes_end = text.find('/* 3D Toggle Switch */', modes_start)
    assert modes_end != -1, 'modes_end in theme_css not found'
    new_modes = """#cct-composer.cct-mode-notebook {
    border: heavy;
    border-top: heavy #a5c3ff;
    border-left: heavy #7aa2f7;
    border-bottom: heavy #1e2850;
    border-right: heavy #344882;
    tint: transparent;
}
#cct-composer.cct-mode-notebook:focus-within {
    border: heavy;
    border-top: heavy #bfd5ff;
    border-left: heavy #89b4fa;
    border-bottom: heavy #1e2850;
    border-right: heavy #344882;
    tint: transparent;
}
#cct-composer.cct-mode-notebook #cct-prompt-glyph {
    color: #7aa2f7;
}
#cct-composer.cct-mode-notebook Button#btn-send,
#cct-composer.cct-mode-notebook Button.cct-icon-send {
    background: #7aa2f7;
    color: #12131d;
}
#cct-composer.cct-mode-notebook Button#btn-send:hover,
#cct-composer.cct-mode-notebook Button.cct-icon-send:hover {
    background: #89b4fa;
    color: #000000;
}

#cct-composer.cct-mode-research {
    border: heavy;
    border-top: heavy #ff94cc;
    border-left: heavy #ff69b4;
    border-bottom: heavy #4d1030;
    border-right: heavy #7a1c4e;
    tint: transparent;
}
#cct-composer.cct-mode-research:focus-within {
    border: heavy;
    border-top: heavy #ffaecf;
    border-left: heavy #ff85c0;
    border-bottom: heavy #4d1030;
    border-right: heavy #7a1c4e;
    tint: transparent;
}
#cct-composer.cct-mode-research #cct-prompt-glyph {
    color: #ff69b4;
}
#cct-composer.cct-mode-research Button#btn-send,
#cct-composer.cct-mode-research Button.cct-icon-send {
    background: #ff69b4;
    color: #12131d;
}
#cct-composer.cct-mode-research Button#btn-send:hover,
#cct-composer.cct-mode-research Button.cct-icon-send:hover {
    background: #ff85c0;
    color: #000000;
}

#cct-composer.cct-mode-plan {
    border: heavy;
    border-top: heavy #bfe88e;
    border-left: heavy #9ece6a;
    border-bottom: heavy #233b12;
    border-right: heavy #416124;
    tint: transparent;
}
#cct-composer.cct-mode-plan:focus-within {
    border: heavy;
    border-top: heavy #cdf59f;
    border-left: heavy #a6e3a1;
    border-bottom: heavy #233b12;
    border-right: heavy #416124;
    tint: transparent;
}
#cct-composer.cct-mode-plan #cct-prompt-glyph {
    color: #9ece6a;
}
#cct-composer.cct-mode-plan Button#btn-send,
#cct-composer.cct-mode-plan Button.cct-icon-send {
    background: #9ece6a;
    color: #12131d;
}
#cct-composer.cct-mode-plan Button#btn-send:hover,
#cct-composer.cct-mode-plan Button.cct-icon-send:hover {
    background: #a6e3a1;
    color: #000000;
}

#cct-composer.cct-mode-build {
    border: heavy;
    border-top: heavy #f7d794;
    border-left: heavy #e0af68;
    border-bottom: heavy #5c3d14;
    border-right: heavy #8c5d20;
    tint: transparent;
}
#cct-composer.cct-mode-build:focus-within {
    border: heavy;
    border-top: heavy #ffeaa7;
    border-left: heavy #fab387;
    border-bottom: heavy #5c3d14;
    border-right: heavy #8c5d20;
    tint: transparent;
}
#cct-composer.cct-mode-build #cct-prompt-glyph {
    color: #e0af68;
}
#cct-composer.cct-mode-build Button#btn-send,
#cct-composer.cct-mode-build Button.cct-icon-send {
    background: #e0af68;
    color: #12131d;
}
#cct-composer.cct-mode-build Button#btn-send:hover,
#cct-composer.cct-mode-build Button.cct-icon-send:hover {
    background: #f7d794;
    color: #000000;
}

#cct-composer.cct-mode-debugger {
    border: heavy;
    border-top: heavy #ff5978;
    border-left: heavy #dc143c;
    border-bottom: heavy #450612;
    border-right: heavy #6e0d20;
    tint: transparent;
}
#cct-composer.cct-mode-debugger:focus-within {
    border: heavy;
    border-top: heavy #ffa1b2;
    border-left: heavy #f38ba8;
    border-bottom: heavy #450612;
    border-right: heavy #6e0d20;
    tint: transparent;
}
#cct-composer.cct-mode-debugger #cct-prompt-glyph {
    color: #dc143c;
}
#cct-composer.cct-mode-debugger Button#btn-send,
#cct-composer.cct-mode-debugger Button.cct-icon-send {
    background: #dc143c;
    color: #ffffff;
}
#cct-composer.cct-mode-debugger Button#btn-send:hover,
#cct-composer.cct-mode-debugger Button.cct-icon-send:hover {
    background: #f38ba8;
    color: #000000;
}

#cct-composer.cct-mode-agent {
    border: heavy;
    border-top: heavy #d8c2ff;
    border-left: heavy #bb9af7;
    border-bottom: heavy #302054;
    border-right: heavy #543b8a;
    tint: transparent;
}
#cct-composer.cct-mode-agent:focus-within {
    border: heavy;
    border-top: heavy #ebd5ff;
    border-left: heavy #cba6f7;
    border-bottom: heavy #302054;
    border-right: heavy #543b8a;
    tint: transparent;
}
#cct-composer.cct-mode-agent #cct-prompt-glyph {
    color: #bb9af7;
}
#cct-composer.cct-mode-agent Button#btn-send,
#cct-composer.cct-mode-agent Button.cct-icon-send {
    background: #bb9af7;
    color: #12131d;
}
#cct-composer.cct-mode-agent Button#btn-send:hover,
#cct-composer.cct-mode-agent Button.cct-icon-send:hover {
    background: #cba6f7;
    color: #000000;
}

"""
    text = text[:modes_start] + new_modes + text[modes_end:]

    # 5. cmdpalette in theme_css
    cmd_start = text.find('/* Clean Elevated Command Palette */\n#cct-cmdpalette {\n    background: $surface;\n    border: round $border;')
    assert cmd_start != -1, 'cmdpalette in theme_css not found'
    cmd_end = text.find('text-style: bold;\n}', cmd_start) + len('text-style: bold;\n}')
    new_cmd = """/* Clean Elevated Command Palette */
#cct-cmdpalette {
    background: #14151f;
    border-top: solid #3b4261;
    border-left: solid #2e344e;
    border-bottom: solid #0e0f17;
    border-right: solid #181926;
    tint: transparent;
    margin-left: 1;
    margin-right: 1;
    margin-top: 0;
    margin-bottom: 0;
    width: 1fr;
    max-height: 8;
    height: auto;
    display: none;
    padding: 0;
    scrollbar-size: 1 1;
    scrollbar-gutter: auto;
    scrollbar-color: #e0af68 transparent;
    scrollbar-background: transparent;
}
#cct-cmdpalette.open { display: block; }
.cct-cmd-row {
    height: 1; min-height: 1; max-height: 1;
    padding: 0 1; color: $text-muted; width: 100%;
    border-left: thick transparent;
    border-right: none;
    transition: background 60ms, color 60ms, border-left 60ms;
}
.cct-cmd-row:hover {
    background: #1c1d2d; color: #ffffff;
    border-left: thick #3b4261;
}
.cct-cmd-row-selected {
    background: #24283b; color: #ffffff;
    border-left: thick #e0af68;
    border-right: none;
    text-style: bold;
}"""
    text = text[:cmd_start] + new_cmd + text[cmd_end:]

    with open('calc_terminal/ui/theme_css.py', 'w', encoding='utf-8', newline='') as f:
        f.write(text)
    print("theme_css.py updated successfully!")


def update_header():
    with open('calc_terminal/ui/header.py', 'r', encoding='utf-8') as f:
        text = f.read()

    # 1. NavPanel #cct-navmenu-box 3D bevel
    old_nav = """        #cct-navmenu-box {
            margin-top: 4; margin-left: 1;
            width: 44; height: auto;
            max-height: 88%;
            background: #1e2030;
            border-top: solid #7a7f9a;
            border-left: solid #6c7086;
            border-bottom: solid #11111b;
            border-right: solid #181825;
            padding: 1 0;
            opacity: 1; offset-y: 0;
            overflow-y: auto;
            scrollbar-gutter: stable;
            scrollbar-size: 1 1;
            scrollbar-color: $border $surface;
        }
        NavPanel.is-portrait #cct-navmenu-box,
        #cct-navmenu-box.is-portrait {
            margin-top: 4; margin-left: 0; margin-right: 0;
            width: 94%; max-width: 48;
            border-top: solid #7a7f9a;
            border-left: solid #6c7086;
            border-bottom: solid #11111b;
            border-right: solid #181825;
        }"""

    new_nav = """        #cct-navmenu-box {
            margin-top: 4; margin-left: 1;
            width: 46; height: auto;
            max-height: 88%;
            background: #181926;
            border: heavy;
            border-top: heavy #8b92b2;
            border-left: heavy #6e7594;
            border-bottom: heavy #0c0d14;
            border-right: heavy #141520;
            padding: 1 0;
            opacity: 1; offset-y: 0;
            overflow-y: auto;
            scrollbar-gutter: stable;
            scrollbar-size: 1 1;
            scrollbar-color: #e0af68 transparent;
        }
        NavPanel.is-portrait #cct-navmenu-box,
        #cct-navmenu-box.is-portrait {
            margin-top: 4; margin-left: 0; margin-right: 0;
            width: 94%; max-width: 48;
            border: heavy;
            border-top: heavy #8b92b2;
            border-left: heavy #6e7594;
            border-bottom: heavy #0c0d14;
            border-right: heavy #141520;
        }"""
    assert old_nav in text, 'old_nav in header.py not found'
    text = text.replace(old_nav, new_nav)

    # 2. PermissionModeMenu #cct-permmenu-box 3D bevel
    old_perm = """        #cct-permmenu-box {
            width: auto;
            max-width: 48;
            height: auto;
            background: $surface;
            border: round $accent;
            padding: 1 1;
            opacity: 1; offset-y: 0;
        }
        #cct-permmenu-box.open { opacity: 1; offset-y: 0; }
        .cct-permmenu-title {
            color: $accent;
            text-style: bold;
            padding: 0 1 1 1;
            border-bottom: solid $border;
            margin-bottom: 1;
        }
        .cct-permmenu-row {
            height: 3;
            padding: 0 1;
            background: $surface;
            border-left: thick $surface;
            border-right: thick $surface;
        }
        .cct-permmenu-row:hover {
            background: $surface-alt;
            color: $accent;
            border-left: thick $accent;
            border-right: thick $surface-alt;
        }
        .cct-permmenu-row-selected {
            background: $surface-highlight;
            border-left: thick $accent;
            border-right: thick $surface-highlight;
            text-style: bold;
        }
        .cct-permmenu-row-focused {
            background: $surface-alt;
            border-left: thick $accent;
            border-right: thick $surface-alt;
        }"""

    new_perm = """        #cct-permmenu-box {
            width: auto;
            max-width: 48;
            height: auto;
            background: #181926;
            border: heavy;
            border-top: heavy #8b92b2;
            border-left: heavy #6e7594;
            border-bottom: heavy #0c0d14;
            border-right: heavy #141520;
            padding: 1 1;
            opacity: 1; offset-y: 0;
        }
        #cct-permmenu-box.open { opacity: 1; offset-y: 0; }
        .cct-permmenu-title {
            color: #e0af68;
            text-style: bold;
            padding: 0 1 1 1;
            border-bottom: solid #3b4261;
            margin-bottom: 1;
        }
        .cct-permmenu-row {
            height: 3;
            padding: 0 1;
            margin: 0 0 1 0;
            background: #1e2030;
            border-top: solid #3b4261;
            border-left: solid #2e344e;
            border-bottom: solid #0e0f17;
            border-right: solid #181926;
        }
        .cct-permmenu-row:hover {
            background: #24283b;
            border-top: solid #f7d794;
            border-left: solid #e0af68;
            border-bottom: solid #0e0f17;
            border-right: solid #181926;
            color: #ffffff;
        }
        .cct-permmenu-row-selected {
            background: #24283b;
            border-top: solid #ffeaa7;
            border-left: solid #fab387;
            border-bottom: solid #0e0f17;
            border-right: solid #181926;
            color: #ffffff;
            text-style: bold;
        }
        .cct-permmenu-row-focused {
            background: #24283b;
            border-top: solid #f7d794;
            border-left: solid #e0af68;
            border-bottom: solid #0e0f17;
            border-right: solid #181926;
            color: #ffffff;
        }"""
    assert old_perm in text, 'old_perm in header.py not found'
    text = text.replace(old_perm, new_perm)

    with open('calc_terminal/ui/header.py', 'w', encoding='utf-8', newline='') as f:
        f.write(text)
    print("header.py updated successfully!")

if __name__ == '__main__':
    update_theme()
    update_header()

