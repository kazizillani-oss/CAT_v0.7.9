with open('calc_terminal/ui/app.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Locate from '/* LEFT: Rounded clean menu button + logo (matches Image 5) */' to '/* --------------------------------------------------------------- sidebar -- */'
start_marker = "/* LEFT: Rounded clean menu button + logo (matches Image 5) */"
end_marker = "/* --------------------------------------------------------------- sidebar -- */"

idx_start = text.find(start_marker)
idx_end = text.find(end_marker)

assert idx_start != -1, "start_marker not found"
assert idx_end != -1, "end_marker not found"

clean_header_css = """/* LEFT: Rounded clean menu button + logo (matches Image 5) */
.cct-menu-btn {
    width: 5; min-width: 5; height: 3; color: $text; content-align: center middle;
    background: $surface;
    border: round #3c4252;
    margin-right: 1;
    transition: color 120ms, border 120ms, background 120ms;
}
.cct-menu-btn:hover {
    color: $accent;
    background: $surface-alt;
    border: round $accent;
}
.cct-menu-btn.-active, .cct-menu-btn-active, .cct-menu-btn:focus {
    color: $accent;
    background: $surface-dark;
    border: round $accent;
    text-style: none;
}
.cct-logo { width: auto; padding: 0 1; content-align: left middle; height: 3; text-style: bold; }

/* CENTER: Rounded clean Permission pill (matches Image 5) */
.cct-perm-pill {
    width: auto; content-align: center middle; height: 3;
    padding: 0 2; margin: 0;
    background: $surface;
    border: round #3c4252;
    text-style: bold;
    color: $text;
    transition: border 120ms, color 120ms, background 120ms;
}
.cct-perm-pill:hover {
    background: $surface-alt;
    border: round $accent;
    color: #ffffff;
}
.cct-perm-pill.-active, .cct-perm-pill:focus, .cct-perm-pill-active {
    background: $surface-dark;
    border: round $accent;
    color: $accent;
}

.cct-chat-title-pill {
    width: auto; max-width: 30; content-align: center middle; height: 3;
    padding: 0 2; margin: 0 1 0 1;
    background: $surface;
    border: round #3c4252;
    color: $text;
    text-style: bold;
    overflow: hidden;
    text-overflow: ellipsis;
    transition: border 120ms, color 120ms, background 120ms;
}
.cct-chat-title-pill:hover {
    background: $surface-alt;
    border: round $accent;
    color: #ffffff;
}
.cct-chat-title-pill:focus, .cct-chat-title-pill.-active {
    background: $surface-dark;
    border: round $accent;
}

/* RIGHT: Rounded clean workspace path chip (matches Image 5) */
#cct-header-right {
    width: auto; max-width: 32; content-align: center middle;
    padding: 0 2; height: 3;
    background: $surface;
    border: round #3c4252;
    overflow: hidden;
    text-overflow: ellipsis;
    text-style: bold;
    color: $text;
    transition: background 120ms, border 120ms, color 120ms;
}
#cct-header-right:hover {
    background: $surface-alt;
    border: round $accent;
    color: #ffffff;
}
#cct-header-right:focus, #cct-header-right.-active {
    background: $surface-dark;
    border: round $accent;
}

"""

text = text[:idx_start] + clean_header_css + text[idx_end:]

with open('calc_terminal/ui/app.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Successfully restored full variables in app.py!")

