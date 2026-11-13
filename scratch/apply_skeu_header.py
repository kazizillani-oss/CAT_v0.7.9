import sys

# 1. Update calc_terminal/ui/app.py
with open("calc_terminal/ui/app.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace landscape header styling
old_landscape = """/* LEFT: 3D Skeuomorphic menu button + logo */
.cct-menu-btn {
    width: 5; min-width: 5; height: 3; color: $text; content-align: center middle;
    background: #252839;
    border-top: solid #5a6585;
    border-left: solid #4a5270;
    border-bottom: solid #141520;
    border-right: solid #181926;
    margin-right: 1;
    transition: color 120ms, border 120ms, background 120ms;
}
.cct-menu-btn:hover {
    color: $accent;
    background: #2f3449;
    border-top: solid $accent-lighten-2;
    border-left: solid $accent;
    border-bottom: solid $accent-darken-3;
    border-right: solid $accent-darken-2;
}
.cct-menu-btn.-active, .cct-menu-btn-active, .cct-menu-btn:focus {
    color: $accent;
    background: #1a1b26;
    border-top: solid #141520;
    border-left: solid #181926;
    border-bottom: solid #5a6585;
    border-right: solid #4a5270;
    text-style: none;
}
.cct-logo { width: auto; padding: 0 1; content-align: left middle; height: 3; text-style: bold; }

/* CENTER: 3D Skeuomorphic Permission pill */
.cct-perm-pill {
    width: auto; content-align: center middle; height: 3;
    padding: 0 2; margin: 0;
    background: #252839;
    border-top: solid #5a6585;
    border-left: solid #4a5270;
    border-bottom: solid #141520;
    border-right: solid #181926;
    text-style: bold;
    color: $text;
    transition: border 120ms, color 120ms, background 120ms;
}
.cct-perm-pill:hover {
    background: #2f3449;
    border-top: solid $accent-lighten-2;
    border-left: solid $accent;
    border-bottom: solid $accent-darken-3;
    border-right: solid $accent-darken-2;
    color: #ffffff;
}
.cct-perm-pill.-active, .cct-perm-pill:focus, .cct-perm-pill-active {
    background: #1a1b26;
    border-top: solid #141520;
    border-left: solid #181926;
    border-bottom: solid #5a6585;
    border-right: solid #4a5270;
    color: $accent;
}

.cct-chat-title-pill {
    width: auto; max-width: 30; content-align: center middle; height: 3;
    padding: 0 2; margin: 0 1 0 1;
    background: #252839;
    border-top: solid #5a6585;
    border-left: solid #4a5270;
    border-bottom: solid #141520;
    border-right: solid #181926;
    color: $text;
    text-style: bold;
    overflow: hidden;
    text-overflow: ellipsis;
    transition: border 120ms, color 120ms, background 120ms;
}
.cct-chat-title-pill:hover {
    background: #2f3449;
    border-top: solid $accent-lighten-2;
    border-left: solid $accent;
    border-bottom: solid $accent-darken-3;
    border-right: solid $accent-darken-2;
    color: #ffffff;
}
.cct-chat-title-pill:focus, .cct-chat-title-pill.-active {
    background: #1a1b26;
    border-top: solid #141520;
    border-left: solid #181926;
    border-bottom: solid #5a6585;
    border-right: solid #4a5270;
}

/* RIGHT: 3D Skeuomorphic workspace path chip */
#cct-header-right {
    width: auto; max-width: 32; content-align: center middle;
    padding: 0 2; height: 3;
    background: #252839;
    border-top: solid #5a6585;
    border-left: solid #4a5270;
    border-bottom: solid #141520;
    border-right: solid #181926;
    overflow: hidden;
    text-overflow: ellipsis;
    text-style: bold;
    color: $text;
    transition: background 120ms, border 120ms, color 120ms;
}
#cct-header-right:hover {
    background: #2f3449;
    border-top: solid $accent-lighten-2;
    border-left: solid $accent;
    border-bottom: solid $accent-darken-3;
    border-right: solid $accent-darken-2;
    color: #ffffff;
}
#cct-header-right:focus, #cct-header-right.-active {
    background: #1a1b26;
    border-top: solid #141520;
    border-left: solid #181926;
    border-bottom: solid #5a6585;
    border-right: solid #4a5270;
}"""

new_landscape = """/* LEFT: 3D Skeuomorphic menu button + logo */
.cct-menu-btn {
    width: 5; min-width: 5; max-width: 5; height: 3; min-height: 3; max-height: 3;
    color: $text; content-align: center middle;
    background: transparent;
    border: tall;
    border-top: tall #6b7596;
    border-left: tall #565f7c;
    border-bottom: tall #0e0f17;
    border-right: tall #13141f;
    margin-right: 1;
    text-style: bold;
    transition: color 120ms, border 120ms, background 120ms;
}
.cct-menu-btn:hover {
    color: #ffffff;
    background: $accent 24%;
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-bottom: tall $accent-darken-3;
    border-right: tall $accent-darken-2;
}
.cct-menu-btn.-active, .cct-menu-btn-active, .cct-menu-btn:focus {
    color: $accent;
    background: #12131c;
    border-top: tall #0e0f17;
    border-left: tall #13141f;
    border-bottom: tall #6b7596;
    border-right: tall #565f7c;
    text-style: none;
}
.cct-logo { width: auto; padding: 0 1; content-align: left middle; height: 3; text-style: bold; }

/* CENTER: 3D Skeuomorphic Permission pill */
.cct-perm-pill {
    width: auto; content-align: center middle; height: 3; min-height: 3; max-height: 3;
    padding: 0 2; margin: 0;
    background: transparent;
    border: tall;
    border-top: tall #6b7596;
    border-left: tall #565f7c;
    border-bottom: tall #0e0f17;
    border-right: tall #13141f;
    text-style: bold;
    color: $text;
    transition: border 120ms, color 120ms, background 120ms;
}
.cct-perm-pill:hover {
    background: $accent 24%;
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-bottom: tall $accent-darken-3;
    border-right: tall $accent-darken-2;
    color: #ffffff;
}
.cct-perm-pill.-active, .cct-perm-pill:focus, .cct-perm-pill-active {
    background: #12131c;
    border-top: tall #0e0f17;
    border-left: tall #13141f;
    border-bottom: tall #6b7596;
    border-right: tall #565f7c;
    color: $accent;
}

.cct-chat-title-pill {
    width: auto; max-width: 30; content-align: center middle; height: 3; min-height: 3; max-height: 3;
    padding: 0 2; margin: 0 1 0 1;
    background: transparent;
    border: tall;
    border-top: tall #6b7596;
    border-left: tall #565f7c;
    border-bottom: tall #0e0f17;
    border-right: tall #13141f;
    color: $text;
    text-style: bold;
    overflow: hidden;
    text-overflow: ellipsis;
    transition: border 120ms, color 120ms, background 120ms;
}
.cct-chat-title-pill:hover {
    background: $accent 24%;
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-bottom: tall $accent-darken-3;
    border-right: tall $accent-darken-2;
    color: #ffffff;
}
.cct-chat-title-pill:focus, .cct-chat-title-pill.-active {
    background: #12131c;
    border-top: tall #0e0f17;
    border-left: tall #13141f;
    border-bottom: tall #6b7596;
    border-right: tall #565f7c;
}

/* RIGHT: 3D Skeuomorphic workspace path chip */
#cct-header-right {
    width: auto; max-width: 32; content-align: center middle;
    padding: 0 2; height: 3; min-height: 3; max-height: 3;
    background: transparent;
    border: tall;
    border-top: tall #6b7596;
    border-left: tall #565f7c;
    border-bottom: tall #0e0f17;
    border-right: tall #13141f;
    overflow: hidden;
    text-overflow: ellipsis;
    text-style: bold;
    color: $text;
    transition: background 120ms, border 120ms, color 120ms;
}
#cct-header-right:hover {
    background: $accent 24%;
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-bottom: tall $accent-darken-3;
    border-right: tall $accent-darken-2;
    color: #ffffff;
}
#cct-header-right:focus, #cct-header-right.-active {
    background: #12131c;
    border-top: tall #0e0f17;
    border-left: tall #13141f;
    border-bottom: tall #6b7596;
    border-right: tall #565f7c;
}"""

if old_landscape in content:
    content = content.replace(old_landscape, new_landscape)
    print("Replaced landscape header styling in app.py")
else:
    print("Warning: old_landscape not matched in app.py")

# Replace portrait header styling
old_portrait = """#cct-brandheader.is-portrait .cct-menu-btn,
#cct-brandheader.is-portrait .cct-menu-btn:hover,
#cct-brandheader.is-portrait .cct-menu-btn:focus,
#cct-brandheader.is-portrait .cct-menu-btn-active {
    width: 5;
    min-width: 5;
    height: 3;
    min-height: 3;
    max-height: 3;
    padding: 0;
    margin-right: 1;
    border-top: solid #5a6585;
    border-left: solid #4a5270;
    border-bottom: solid #141520;
    border-right: solid #181926;
    background: #252839;
    color: $text;
}
#cct-brandheader.is-portrait .cct-menu-btn:hover {
    color: $accent;
    background: #2f3449;
    border-top: solid $accent-lighten-2;
    border-left: solid $accent;
    border-bottom: solid $accent-darken-3;
    border-right: solid $accent-darken-2;
}
#cct-brandheader.is-portrait .cct-menu-btn:focus,
#cct-brandheader.is-portrait .cct-menu-btn-active {
    background: #1a1b26;
    border-top: solid #141520;
    border-left: solid #181926;
    border-bottom: solid #5a6585;
    border-right: solid #4a5270;
}
#cct-brandheader.is-portrait .cct-logo {
    height: 3;
    min-height: 3;
    max-height: 3;
    padding: 0 1;
    content-align: left middle;
    text-style: bold;
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
    margin: 0;
    border-top: solid #5a6585;
    border-left: solid #4a5270;
    border-bottom: solid #141520;
    border-right: solid #181926;
    background: #252839;
    color: $text;
    text-style: bold;
}
#cct-brandheader.is-portrait .cct-perm-pill:hover {
    background: #2f3449;
    border-top: solid $accent-lighten-2;
    border-left: solid $accent;
    border-bottom: solid $accent-darken-3;
    border-right: solid $accent-darken-2;
    color: #ffffff;
}
#cct-brandheader.is-portrait .cct-perm-pill:focus,
#cct-brandheader.is-portrait .cct-perm-pill-active {
    background: #1a1b26;
    border-top: solid #141520;
    border-left: solid #181926;
    border-bottom: solid #5a6585;
    border-right: solid #4a5270;
}
#cct-brandheader.is-portrait #cct-header-right-box {
    width: 1fr;
    height: 3;
    min-height: 3;
    max-height: 3;
    layout: horizontal;
    align: right middle;
    align-vertical: middle;
}
#cct-brandheader.is-portrait #cct-header-right {
    height: 3;
    min-height: 3;
    max-height: 3;
    padding: 0 1;
    border-top: solid #5a6585;
    border-left: solid #4a5270;
    border-bottom: solid #141520;
    border-right: solid #181926;
    background: #252839;
    color: $text;
}
#cct-header-explorer-btn {
    display: none;
    height: 3;
    min-height: 3;
    max-height: 3;
    width: 5;
    min-width: 5;
    padding: 0;
    content-align: center middle;
    border-top: solid #5a6585;
    border-left: solid #4a5270;
    border-bottom: solid #141520;
    border-right: solid #181926;
    background: #252839;
    color: $accent;
}
#cct-header-explorer-btn:hover {
    background: #2f3449;
    border-top: solid $accent-lighten-2;
    border-left: solid $accent;
    border-bottom: solid $accent-darken-3;
    border-right: solid $accent-darken-2;
    color: #ffffff;
}"""

new_portrait = """#cct-brandheader.is-portrait .cct-menu-btn,
#cct-brandheader.is-portrait .cct-menu-btn:hover,
#cct-brandheader.is-portrait .cct-menu-btn:focus,
#cct-brandheader.is-portrait .cct-menu-btn-active {
    width: 5;
    min-width: 5;
    max-width: 5;
    height: 3;
    min-height: 3;
    max-height: 3;
    padding: 0;
    margin-right: 1;
    border: tall;
    border-top: tall #6b7596;
    border-left: tall #565f7c;
    border-bottom: tall #0e0f17;
    border-right: tall #13141f;
    background: transparent;
    color: $text;
    text-style: bold;
}
#cct-brandheader.is-portrait .cct-menu-btn:hover {
    color: #ffffff;
    background: $accent 24%;
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-bottom: tall $accent-darken-3;
    border-right: tall $accent-darken-2;
}
#cct-brandheader.is-portrait .cct-menu-btn:focus,
#cct-brandheader.is-portrait .cct-menu-btn-active {
    background: #12131c;
    border-top: tall #0e0f17;
    border-left: tall #13141f;
    border-bottom: tall #6b7596;
    border-right: tall #565f7c;
}
#cct-brandheader.is-portrait .cct-logo {
    height: 3;
    min-height: 3;
    max-height: 3;
    padding: 0 1;
    content-align: left middle;
    text-style: bold;
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
    margin: 0;
    border: tall;
    border-top: tall #6b7596;
    border-left: tall #565f7c;
    border-bottom: tall #0e0f17;
    border-right: tall #13141f;
    background: transparent;
    color: $text;
    text-style: bold;
}
#cct-brandheader.is-portrait .cct-perm-pill:hover {
    background: $accent 24%;
    border-top: tall #ffffff;
    border-left: tall $accent-highlight;
    border-bottom: tall $accent-darken-3;
    border-right: tall $accent-darken-2;
    color: #ffffff;
}
#cct-brandheader.is-portrait .cct-perm-pill:focus,
#cct-brandheader.is-portrait .cct-perm-pill-active {
    background: #12131c;
    border-top: tall #0e0f17;
    border-left: tall #13141f;
    border-bottom: tall #6b7596;
    border-right: tall #565f7c;
}
#cct-brandheader.is-portrait #cct-header-right-box {
    width: 1fr;
    height: 3;
    min-height: 3;
    max-height: 3;
    layout: horizontal;
    align: right middle;
    align-vertical: middle;
    background: transparent;
    border: none;
}
#cct-brandheader.is-portrait #cct-header-right {
    height: 3;
    min-height: 3;
    max-height: 3;
    padding: 0 1;
    border: tall;
    border-top: tall #6b7596;
    border-left: tall #565f7c;
    border-bottom: tall #0e0f17;
    border-right: tall #13141f;
    background: transparent;
    color: $text;
}
#cct-header-explorer-btn {
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

if old_portrait in content:
    content = content.replace(old_portrait, new_portrait)
    print("Replaced portrait header styling in app.py")
else:
    print("Warning: old_portrait not matched in app.py")

with open("calc_terminal/ui/app.py", "w", encoding="utf-8") as f:
    f.write(content)

# 2. Update calc_terminal/ui/theme_css.py
with open("calc_terminal/ui/theme_css.py", "r", encoding="utf-8") as f:
    t_content = f.read()

old_theme_btn = """#cct-header-explorer-btn {
    display: none;
    height: 3;
    min-height: 3;
    max-height: 3;
    width: 5;
    min-width: 5;
    padding: 0;
    content-align: center middle;
    border-top: solid #5a6585;
    border-left: solid #4a5270;
    border-bottom: solid #141520;
    border-right: solid #181926;
    background: #252839;
    color: $accent;
}
#cct-header-explorer-btn:hover {
    background: #2f3449;
    border-top: solid $accent-lighten-2;
    border-left: solid $accent;
    border-bottom: solid $accent-darken-3;
    border-right: solid $accent-darken-2;
    color: #ffffff;
}"""

new_theme_btn = """#cct-header-explorer-btn {
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

if old_theme_btn in t_content:
    t_content = t_content.replace(old_theme_btn, new_theme_btn)
    print("Replaced explorer btn in theme_css.py")
else:
    print("Warning: old_theme_btn not matched in theme_css.py")

with open("calc_terminal/ui/theme_css.py", "w", encoding="utf-8") as f:
    f.write(t_content)

print("Patching complete!")

