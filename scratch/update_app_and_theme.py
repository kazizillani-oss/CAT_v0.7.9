import sys
import re

def update_app():
    with open('calc_terminal/ui/app.py', 'r', encoding='utf-8') as f:
        text = f.read()

    # 1. composer
    idx = text.find('#cct-composer {\n    background: $surface;\n    border: heavy $border;')
    assert idx != -1, 'composer not found'
    end_idx = text.find('}', idx) + 1
    new_composer = """#cct-composer {
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
}"""
    text = text[:idx] + new_composer + text[end_idx:]

    # 2. cmdpalette
    p_start = text.find('#cct-cmdpalette {\n    background: $surface;\n    border: round $border;')
    assert p_start != -1, 'cmdpalette not found'
    p_end = text.find('text-style: bold;\n}', p_start) + len('text-style: bold;\n}')
    new_palette = """#cct-cmdpalette {
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
    height: 1;
    min-height: 1;
    max-height: 1;
    padding: 0 1;
    color: $text-muted;
    width: 1fr;
    border-left: thick transparent;
    transition: background 60ms, color 60ms, border-left 60ms;
}
.cct-cmd-row:hover {
    background: #1c1d2d;
    color: #ffffff;
    border-left: thick #3b4261;
}
.cct-cmd-row-selected {
    background: #24283b;
    color: #ffffff;
    border-left: thick #e0af68;
    border-right: none;
    text-style: bold;
}"""
    text = text[:p_start] + new_palette + text[p_end:]

    # 3. bottom-row
    b_start = text.find('#cct-bottom-row {\n    height: 1;\n    min-height: 1;\n    max-height: 1;\n    margin: 0;\n    padding: 0;\n')
    assert b_start != -1, 'bottom-row not found'
    b_end = text.find('}', b_start) + 1
    new_bottom = """#cct-bottom-row {
    height: 1;
    min-height: 1;
    max-height: 1;
    margin: 0;
    padding: 0 1;
    layout: horizontal;
    align-vertical: middle;
    border: none;
    background: transparent;
    overflow: hidden;
}"""
    text = text[:b_start] + new_bottom + text[b_end:]

    # 4. right-controls
    r_start = text.find('#cct-right-controls {\n    width: auto;\n    min-width: 9;\n')
    assert r_start != -1, 'right-controls not found'
    r_end = text.find('}', r_start) + 1
    new_right = """#cct-right-controls {
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
    overflow: hidden;
    background: transparent;
}"""
    text = text[:r_start] + new_right + text[r_end:]

    # 5. menu-btn
    m_start = text.find('.cct-menu-btn {\n    width: 5; min-width: 5; height: 3;')
    assert m_start != -1, 'menu-btn not found'
    m_end = text.find('.cct-menu-btn.-active, .cct-menu-btn-active {\n    color: $accent;\n    background: $surface-dark;\n    border-top: tall $surface-shadow;\n    border-left: tall $surface-shadow;\n    border-bottom: tall $surface-highlight;\n    border-right: tall $surface-highlight;\n    text-style: none;\n}') + len('.cct-menu-btn.-active, .cct-menu-btn-active {\n    color: $accent;\n    background: $surface-dark;\n    border-top: tall $surface-shadow;\n    border-left: tall $surface-shadow;\n    border-bottom: tall $surface-highlight;\n    border-right: tall $surface-highlight;\n    text-style: none;\n}')
    new_menu = """.cct-menu-btn {
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
}"""
    text = text[:m_start] + new_menu + text[m_end:]

    # 6. header borders
    old_hb = """#cct-brandheader .cct-menu-btn,
#cct-brandheader .cct-perm-pill,
#cct-brandheader #cct-header-right {
    border-top: tall #6b7596;
    border-left: tall #565f7c;
    border-bottom: tall #0e0f17;
    border-right: tall #13141f;
}"""
    new_hb = """#cct-brandheader .cct-perm-pill,
#cct-brandheader #cct-header-right {
    border-top: tall #6b7596;
    border-left: tall #565f7c;
    border-bottom: tall #0e0f17;
    border-right: tall #13141f;
}"""
    assert old_hb in text, 'old_hb not found'
    text = text.replace(old_hb, new_hb)

    # 7. perm-panel
    old_pp = """#cct-permission-panel {
    background: $surface; border: round $accent; margin: 0 1 1 1;
    padding: 1 2; height: auto; max-height: 14; display: none;
}"""
    new_pp = """#cct-permission-panel {
    background: #181926;
    border: heavy;
    border-top: heavy #8b92b2;
    border-left: heavy #6e7594;
    border-bottom: heavy #0c0d14;
    border-right: heavy #141520;
    margin: 0 1 1 1;
    padding: 1 2;
    height: auto;
    max-height: 14;
    display: none;
}"""
    assert old_pp in text, 'old_pp not found'
    text = text.replace(old_pp, new_pp)

    with open('calc_terminal/ui/app.py', 'w', encoding='utf-8', newline='') as f:
        f.write(text)
    print("app.py updated successfully!")

if __name__ == '__main__':
    update_app()

