PATH = r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9\calc_terminal\ui\app.py"

with open(PATH, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Update Header CSS
old_header = """#cct-header-top { height: 3; overflow: hidden; align: center middle; align-vertical: middle; }
#cct-header-left { width: auto; height: 3; align: left middle; align-vertical: middle; layout: horizontal; }
#cct-header-spacer-left { width: 1fr; height: 3; }
#cct-header-spacer-right { width: 1fr; height: 3; }

/* LEFT: clean menu button + logo */
.cct-menu-btn {
    width: 5; min-width: 5; height: 3; color: $text; content-align: center middle;
    background: $surface-alt;
    border: round $border;
    margin-right: 1;
    transition: color 120ms, border 120ms, background 120ms;
}
.cct-menu-btn:hover {
    color: $accent;
    background: $accent 24%;
    border: round $accent;
}
.cct-menu-btn.-active, .cct-menu-btn-active {
    color: $accent;
    background: $accent 30%;
    border: round $accent;
    text-style: none;
}
.cct-logo { width: auto; padding: 0 1; content-align: left middle; height: 3; text-style: bold; }

/* CENTER: Permission pill */
.cct-perm-pill {
    width: auto; content-align: center middle; height: 3;
    padding: 0 2; margin: 0;
    background: $surface-alt;
    border: round $border;
    text-style: bold;
    color: $text;
    transition: border 120ms, color 120ms, background 120ms;
}
.cct-perm-pill:hover {
    background: $accent 24%;
    border: round $accent;
    color: $text;
}
.cct-perm-pill.-active {
    background: $accent 35%;
    border: round $accent;
    color: $text;
}
.cct-perm-pill:focus, .cct-perm-pill-active {
    background: $accent 30%;
    border: round $accent;
    color: $text;
}

.cct-chat-title-pill {
    width: auto; max-width: 30; content-align: center middle; height: 3;
    padding: 0 2; margin: 0 1 0 1;
    background: $surface-alt;
    border: round $border;
    color: $text;
    text-style: bold;
    overflow: hidden;
    text-overflow: ellipsis;
    transition: border 120ms, color 120ms, background 120ms;
}
.cct-chat-title-pill:hover {
    background: $accent 18%;
    border: round $accent;
    color: $text;
}
.cct-chat-title-pill:focus, .cct-chat-title-pill.-active {
    background: $accent 28%;
    border: round $accent;
}

/* RIGHT: workspace path chip — cleanly aligned with permission pill */
#cct-header-right {
    width: auto; max-width: 32; content-align: center middle;
    padding: 0 2; height: 3;
    background: $surface-alt;
    border: round $border;
    overflow: hidden;
    text-overflow: ellipsis;
    text-style: bold;
    color: $text;
    transition: background 120ms, border 120ms, color 120ms;
}
#cct-header-right:hover {
    background: $accent 20%;
    border: round $accent;
    color: #ffffff;
}
.cct-menu-btn:focus { color: $accent; text-style: bold; border: round $accent; }"""

new_header = """#cct-header-top {
    height: 3; overflow: hidden;
    layout: horizontal;
    align: center middle; align-vertical: middle;
}
#cct-header-left {
    width: 1fr; height: 3;
    align: left middle; align-vertical: middle;
    layout: horizontal;
}
#cct-header-spacer-left { display: none; }
#cct-header-spacer-right { display: none; }
#cct-header-right-box {
    width: 1fr; height: 3;
    align: right middle; align-vertical: middle;
    layout: horizontal;
}

/* LEFT: 3D raised menu button + logo */
.cct-menu-btn {
    width: 5; min-width: 5; height: 3; color: $text; content-align: center middle;
    background: $surface;
    border-top: tall $surface-highlight;
    border-left: tall $surface-highlight;
    border-bottom: tall $surface-shadow;
    border-right: tall $surface-shadow;
    margin-right: 1;
    transition: color 120ms, border 120ms, background 120ms;
}
.cct-menu-btn:hover {
    color: $accent;
    background: $surface-alt;
    border-top: tall $accent-lighten-2;
    border-left: tall $accent-lighten-2;
    border-bottom: tall $accent;
    border-right: tall $accent;
}
.cct-menu-btn.-active, .cct-menu-btn-active {
    color: $accent;
    background: $surface-dark;
    border-top: tall $surface-shadow;
    border-left: tall $surface-shadow;
    border-bottom: tall $surface-highlight;
    border-right: tall $surface-highlight;
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
#cct-header-right:hover {
    background: $surface-alt;
    border-top: tall $accent-lighten-2;
    border-left: tall $accent-lighten-2;
    border-bottom: tall $accent;
    border-right: tall $accent;
    color: #ffffff;
}
.cct-menu-btn:focus { color: $accent; text-style: bold; border-top: tall $accent-lighten-2; border-left: tall $accent-lighten-2; }"""

assert old_header in code, "old_header not found"
code = code.replace(old_header, new_header)

# 2. Update SignOutModal CSS
old_signout = """                #signout-box {
                    width: 90%;
                    max-width: 48;
                    height: auto;
                    background: $surface;
                    border: round $accent;
                    padding: 1 2;
                    layout: vertical;
                    align: center middle;
                }
                #signout-title {
                    color: $accent;
                    text-style: bold;
                    text-align: center;
                    margin-bottom: 1;
                }
                #signout-prompt {
                    text-align: center;
                    margin-bottom: 1;
                    color: $text;
                }
                #signout-buttons {
                    height: 3;
                    width: 100%;
                    align: center middle;
                    layout: horizontal;
                }
                #signout-buttons Button {
                    margin: 0 1;
                    min-width: 12;
                    height: 3;
                }"""

new_signout = """                #signout-box {
                    width: 90%;
                    max-width: 48;
                    height: auto;
                    background: $surface;
                    border-top: tall $surface-highlight;
                    border-left: tall $surface-highlight;
                    border-bottom: tall $border;
                    border-right: tall $border;
                    padding: 1 2;
                    layout: vertical;
                    align: center middle;
                }
                #signout-title {
                    color: $accent;
                    text-style: bold;
                    text-align: center;
                    margin-bottom: 1;
                }
                #signout-prompt {
                    text-align: center;
                    margin-bottom: 1;
                    color: $text;
                }
                #signout-buttons {
                    height: auto;
                    min-height: 4;
                    width: 100%;
                    align: center middle;
                    layout: horizontal;
                }
                #signout-buttons Button {
                    margin: 0 1;
                    min-width: 12;
                    height: 3;
                    border-top: tall $surface-highlight;
                    border-left: tall $surface-highlight;
                    border-bottom: tall $surface-shadow;
                    border-right: tall $surface-shadow;
                    background: $surface;
                    color: $text;
                    text-style: bold;
                }
                #signout-buttons Button:hover {
                    border-top: tall $accent-lighten-2;
                    border-left: tall $accent-lighten-2;
                    border-bottom: tall $accent;
                    border-right: tall $accent;
                    background: $surface-alt;
                    color: #ffffff;
                }
                #signout-confirm {
                    background: $accent 35%;
                    color: #ffffff;
                    border-top: tall $accent-lighten-2;
                    border-left: tall $accent-lighten-2;
                    border-bottom: tall $surface-shadow;
                    border-right: tall $surface-shadow;
                }"""

assert old_signout in code, "old_signout not found"
code = code.replace(old_signout, new_signout)

# 3. Update QuitModal CSS
old_quit = """                #quit-box {
                    width: 90%;
                    max-width: 46;
                    height: auto;
                    background: $surface;
                    border: round $error;
                    padding: 1 2;
                    layout: vertical;
                    align: center middle;
                }
                #quit-title {
                    color: $error;
                    text-style: bold;
                    text-align: center;
                    margin-bottom: 1;
                }
                #quit-prompt {
                    text-align: center;
                    margin-bottom: 1;
                    color: $text;
                }
                #quit-buttons {
                    height: 3;
                    width: 100%;
                    align: center middle;
                    layout: horizontal;
                }
                #quit-buttons Button {
                    margin: 0 1;
                    min-width: 12;
                    height: 3;
                }"""

new_quit = """                #quit-box {
                    width: 90%;
                    max-width: 46;
                    height: auto;
                    background: $surface;
                    border-top: tall #ffa198;
                    border-left: tall #ffa198;
                    border-bottom: tall #c73859;
                    border-right: tall #c73859;
                    padding: 1 2;
                    layout: vertical;
                    align: center middle;
                }
                #quit-title {
                    color: $error;
                    text-style: bold;
                    text-align: center;
                    margin-bottom: 1;
                }
                #quit-prompt {
                    text-align: center;
                    margin-bottom: 1;
                    color: $text;
                }
                #quit-buttons {
                    height: auto;
                    min-height: 4;
                    width: 100%;
                    align: center middle;
                    layout: horizontal;
                }
                #quit-buttons Button {
                    margin: 0 1;
                    min-width: 12;
                    height: 3;
                    border-top: tall $surface-highlight;
                    border-left: tall $surface-highlight;
                    border-bottom: tall $surface-shadow;
                    border-right: tall $surface-shadow;
                    background: $surface;
                    color: $text;
                    text-style: bold;
                }
                #quit-buttons Button:hover {
                    border-top: tall $accent-lighten-2;
                    border-left: tall $accent-lighten-2;
                    border-bottom: tall $accent;
                    border-right: tall $accent;
                    background: $surface-alt;
                    color: #ffffff;
                }
                #quit-confirm {
                    background: #472635;
                    border-top: tall #ffa198;
                    border-left: tall #ffa198;
                    border-bottom: tall #c73859;
                    border-right: tall #c73859;
                    color: #ff7b72;
                }
                #quit-confirm:hover {
                    background: #612739;
                    color: #ffffff;
                }"""

assert old_quit in code, "old_quit not found"
code = code.replace(old_quit, new_quit)

with open(PATH, "w", encoding="utf-8") as f:
    f.write(code)

print("app.py updated successfully with 3D header, SignOut, and Quit.")

