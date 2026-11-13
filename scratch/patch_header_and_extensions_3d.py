"""
Script to apply 3D header skeuomorphism, restore portrait header, redesign extensions with 3D effects,
and fix dialog cross/bottom buttons.
"""

import os
import re

# ==========================================
# 1. PATCH calc_terminal/ui/app.py
# ==========================================
def patch_app_py():
    path = "calc_terminal/ui/app.py"
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    # 1.1 Landscape Header Controls 3D Effects
    old_header_controls = """/* LEFT: Rounded clean menu button + logo (matches Image 5) */
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
}"""

    new_header_controls = """/* LEFT: 3D Skeuomorphic menu button + logo */
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

    if old_header_controls in text:
        text = text.replace(old_header_controls, new_header_controls)
        print("[OK] Updated landscape header controls to 3D bevels in app.py")
    else:
        print("! Warning: old_header_controls not found in app.py")

    # 1.2 Portrait Header Restoration & 3D Keycaps
    idx_portrait_start = text.find("#cct-brandheader.is-portrait {")
    idx_tb_close = text.find("#cct-tb-close {", idx_portrait_start)
    if idx_portrait_start != -1 and idx_tb_close != -1:
        old_portrait_chunk = text[idx_portrait_start:idx_tb_close]
        new_portrait_chunk = """#cct-brandheader.is-portrait {
    height: 4;
    min-height: 4;
    max-height: 4;
    padding: 0 1;
    border-bottom: solid $border;
    dock: top;
    display: block;
}
#cct-brandheader.is-portrait #cct-header-top {
    height: 3;
    min-height: 3;
    max-height: 3;
    layout: horizontal;
    align: center middle;
    align-vertical: middle;
}
#cct-brandheader.is-portrait #cct-header-left {
    width: 1fr;
    height: 3;
    min-height: 3;
    max-height: 3;
    layout: horizontal;
    align: left middle;
    align-vertical: middle;
}
#cct-brandheader.is-portrait .cct-menu-btn,
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
}
#cct-brandheader.is-portrait #cct-header-explorer-btn,
.is-portrait #cct-header-explorer-btn {
    display: block;
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
"""
        text = text[:idx_portrait_start] + new_portrait_chunk + text[idx_tb_close:]
        print("[OK] Restored portrait header & applied 3D rules in app.py")
    else:
        print("! Warning: could not locate portrait rules in app.py")

    # 1.3 Fix _cascade_resize brand_header dispatch
    old_cascade_hdr = """                # 3. Update header controls
                hdr = getattr(self, "header", None)
                if hdr is not None and hasattr(hdr, "on_resize"):"""
    new_cascade_hdr = """                # 3. Update header controls
                hdr = None
                try:
                    hdr = self.brand_header
                except Exception:
                    hdr = getattr(self, "header", None)
                if hdr is not None and hasattr(hdr, "on_resize"):"""
    if old_cascade_hdr in text:
        text = text.replace(old_cascade_hdr, new_cascade_hdr)
        print("[OK] Fixed _cascade_resize brand_header dispatch in app.py")

    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

# ==========================================
# 2. PATCH calc_terminal/ui/header.py
# ==========================================
def patch_header_py():
    path = "calc_terminal/ui/header.py"
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    # 2.1 BrandHeader.apply_custom_header: always height 4
    old_apply = """                if not _cust.is_active():
                    self.display = True
                    if not self.has_class("is-portrait"):
                        self.styles.height = 4
                    else:
                        self.styles.height = 2
                    try:
                        logo = self.query_one(Logo)
                        if logo:
                            logo.display = True
                    except Exception:
                        pass
                    return"""
    new_apply = """                if not _cust.is_active():
                    self.display = True
                    self.styles.height = 4
                    try:
                        logo = self.query_one(Logo)
                        if logo:
                            logo.display = True
                    except Exception:
                        pass
                    return"""
    if old_apply in text:
        text = text.replace(old_apply, new_apply)
        print("[OK] Updated apply_custom_header height in header.py")

    # 2.2 BrandHeader.on_resize: height 4 in both portrait and landscape
    old_resize = """            if is_portrait:
                self.styles.height = 2
                compact = True
                ultra_compact = (w < 45)
            else:
                self.styles.height = 4
                compact = (w < 85)
                ultra_compact = (w < 50)"""
    new_resize = """            self.styles.height = 4
            self.display = True
            if is_portrait:
                compact = True
                ultra_compact = (w < 45)
            else:
                compact = (w < 85)
                ultra_compact = (w < 50)"""
    if old_resize in text:
        text = text.replace(old_resize, new_resize)
        print("[OK] Updated on_resize height in header.py")

    # 2.3 NavPanel 3D chassis & items
    old_nav_css = """        #cct-navmenu-box {
            margin-top: 3; margin-left: 1;
            width: 42; height: auto;
            max-height: 88%;
            background: $surface;
            border-top: tall $surface-highlight;
            border-left: tall $surface-highlight;
            border-bottom: tall $surface-dark;
            border-right: tall $surface-dark;
            padding: 1 0;
            opacity: 1; offset-y: 0;
            overflow-y: auto;
            scrollbar-gutter: stable;
            scrollbar-size: 1 1;
            scrollbar-color: $border $surface;
        }
        NavPanel.is-portrait #cct-navmenu-box,
        #cct-navmenu-box.is-portrait {
            margin-top: 2; margin-left: 0; margin-right: 0;
            width: 92%; max-width: 46;
            border: heavy $border;
        }"""
    new_nav_css = """        #cct-navmenu-box {
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
    if old_nav_css in text:
        text = text.replace(old_nav_css, new_nav_css)
        print("[OK] Updated NavPanel 3D chassis in header.py")

    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

# ==========================================
# 3. PATCH calc_terminal/ui/theme_css.py
# ==========================================
def patch_theme_css_py():
    path = "calc_terminal/ui/theme_css.py"
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    old_theme_chunk = """#cct-header-explorer-btn {
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

    new_theme_chunk = """#cct-header-explorer-btn {
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
}
#cct-brandheader.is-portrait #cct-header-explorer-btn,
.is-portrait #cct-header-explorer-btn {
    display: block;
}
#cct-brandheader.is-portrait #cct-header-right-box {
    height: 3;
    min-height: 3;
    max-height: 3;
    width: 1fr;
    layout: horizontal;
    align: right middle;
}"""

    if old_theme_chunk in text:
        text = text.replace(old_theme_chunk, new_theme_chunk)
        print("[OK] Updated portrait header rules in theme_css.py")
    else:
        print("! Warning: old_theme_chunk not found in theme_css.py")

    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

# ==========================================
# 4. PATCH calc_terminal/ui/extensions_panel.py
# ==========================================
def patch_extensions_panel_py():
    path = "calc_terminal/ui/extensions_panel.py"
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    old_ext_css = """        CSS = \"\"\"
        ExtensionsPanel { align: center middle; background: rgba(0, 0, 0, 0.72); }
        #ext-box {
            width: 88; max-width: 96%; height: auto; max-height: 84%;
            background: $surface;
            border-top: solid #7a7f9a;
            border-left: solid #6c7086;
            border-bottom: solid #11111b;
            border-right: solid #181825;
            padding: 0;
            layout: vertical;
            overflow: hidden;
        }
        #ext-titlebar {
            height: 5; min-height: 5; max-height: 5;
            padding: 0 2;
            border-bottom: solid #313244;
            layout: horizontal;
            align: center middle;
            background: $surface-darken-1;
        }
        #ext-title { width: 1fr; text-style: bold; color: $text; }
        #ext-close {
            width: 5; min-width: 5; max-width: 5; height: 3; min-height: 3; max-height: 3; padding: 0;
            content-align: center middle;
            border-top: solid #ffa198;
            border-left: solid #ffa198;
            border-bottom: solid #c73859;
            border-right: solid #c73859;
            background: #3e2430;
            color: #ffffff;
        }
        #ext-close:hover {
            background: #5a2c3a;
            border-top: solid #ffffff;
            border-left: solid #ffffff;
            border-bottom: solid #ffa198;
            border-right: solid #ffa198;
        }
        #ext-search { height: 3; padding: 0 2; margin: 1 0 0 0; }
        #ext-search Input {
            width: 1fr; height: 3;
            border-top: solid #11111b;
            border-left: solid #181825;
            border-bottom: solid #6c7086;
            border-right: solid #585b70;
            background: $surface-darken-2;
            color: $text;
        }
        #ext-search Input:focus { border: round $accent; }
        #ext-subtitle { color: $text-muted; height: 1; padding: 0 2; display: none; }
        #ext-list {
            height: 1fr; min-height: 4; max-height: 62%;
            overflow-y: auto; scrollbar-gutter: stable; scrollbar-size: 1 1;
            scrollbar-color: $border transparent;
            margin: 0 1; padding: 1 0 0 0;
        }
        .ext-card {
            height: auto; min-height: 6; padding: 1 2;
            border-top: solid #585b70;
            border-left: solid #45475a;
            border-bottom: solid #11111b;
            border-right: solid #181825;
            background: $surface;
            margin: 0 0 1 0;
            layout: horizontal;
            align-vertical: middle;
            overflow: hidden;
            transition: border 120ms, background 120ms;
        }
        .ext-card:hover {
            border-top: solid $accent-lighten-2;
            border-left: solid $accent;
            border-bottom: solid $accent-darken-3;
            border-right: solid $accent-darken-2;
            background: $surface-alt;
        }
        .ext-card.ext-busy { background: $surface; border: round $accent; }
        .ext-card-icon {
            width: 6; min-width: 6; height: 4; text-align: center; text-style: bold;
            content-align: center middle; background: $surface-darken-1;
            border-top: solid #585b70;
            border-left: solid #45475a;
            border-bottom: solid #11111b;
            border-right: solid #181825;
            margin-right: 2; padding: 0;
        }
        .ext-icon { width: 100%; height: 100%; text-align: center; content-align: center middle; }
        .ext-loading { width: 6; height: 3; color: $accent; content-align: center middle; }
        .ext-card-info { width: 1fr; height: auto; min-width: 16; }
        .ext-title-row { height: 1; layout: horizontal; }
        .ext-name { width: auto; height: 1; text-style: bold; margin-right: 2; color: $text; }
        .ext-type-badge { display: none; }
        .ext-verified { width: auto; height: 1; color: #5af78e; text-style: bold; }
        .ext-trusted { width: auto; height: 1; color: #5af78e; text-style: bold; margin-left: 1; }
        .ext-desc { width: 100%; height: auto; color: $text-muted; max-height: 2; overflow: hidden; margin-top: 0; }
        .ext-meta { width: 100%; height: 1; color: $text-muted; margin-top: 0; }
        .ext-status { display: none; }
        .ext-busy { color: $accent; }
        .ext-busy-label { color: $warning; text-style: bold; }
        .ext-card-actions { width: auto; min-width: 14; height: auto; layout: horizontal; align: right middle; }
        .ext-card-actions Button {
            min-width: 12; height: 3; min-height: 3; padding: 0 1; margin-left: 1;
            border-top: solid $accent-lighten-2;
            border-left: solid $accent;
            border-bottom: solid $accent-darken-3;
            border-right: solid $accent-darken-2;
            background: $surface;
            color: $accent;
            text-style: bold;
        }
        .ext-card-actions Button:hover {
            background: $accent;
            color: $surface-darken-2;
            border: round $accent;
        }
        .ext-card-actions Button:first-child { margin-left: 0; }
        .ext-card-actions Button:disabled { opacity: 0.7; }
        #ext-actions {
            height: 4; min-height: 4; padding: 0 2;
            border-top: solid #313244;
            background: $surface-darken-1;
            layout: horizontal;
            align: center middle;
            overflow: hidden;
        }
        #ext-actions-left { width: 1fr; height: auto; layout: horizontal; align: center middle; }
        #ext-actions-left Button, #ext-actions Button {
            margin-right: 1; min-width: 11; height: 3; min-height: 3; padding: 0 1;
            border-top: solid #6c7086;
            border-left: solid #585b70;
            border-bottom: solid #11111b;
            border-right: solid #181825;
            background: $surface-alt;
        }
        #ext-actions-left Button:hover, #ext-actions Button:hover {
            border-top: solid $accent-lighten-2;
            border-left: solid $accent;
            border-bottom: solid $accent-darken-3;
            border-right: solid $accent-darken-2;
        }
        #ext-error { color: $error; background: $surface; height: 1; padding: 0 2; display: none; }
        #ext-error.show { display: block; }
        .cct-compact #ext-box { width: 94%; max-height: 90%; }
        .cct-compact #ext-titlebar { height: 5; min-height: 5; }
        .cct-compact #ext-list { min-height: 6; }
        .cct-compact .ext-card { layout: vertical; min-height: 6; padding: 1; }
        .cct-compact .ext-card-icon { display: none; }
        .cct-compact .ext-card-info { width: 100%; }
        .cct-compact .ext-card-actions { width: 100%; layout: horizontal; align: right middle; margin-top: 1; }
        .cct-compact .ext-card-actions Button { width: auto; min-width: 10; padding: 0 1; margin: 0; }
        .cct-compact #ext-actions { padding: 0 1; }
        .cct-compact #ext-actions-left Button { min-width: 9; }
        \"\"\""""

    new_ext_css = """        CSS = \"\"\"
        ExtensionsPanel { align: center middle; background: rgba(0, 0, 0, 0.72); }
        #ext-box {
            width: 88; max-width: 96%; height: auto; max-height: 86%;
            background: #1e2030;
            border-top: solid #7a7f9a;
            border-left: solid #6c7086;
            border-bottom: solid #11111b;
            border-right: solid #181825;
            padding: 0;
            layout: vertical;
            overflow: hidden;
        }
        #ext-titlebar {
            height: 4; min-height: 4; max-height: 4;
            padding: 0 2;
            border-bottom: solid #141520;
            layout: horizontal;
            align: center middle;
            background: #252839;
        }
        #ext-title { width: 1fr; text-style: bold; color: $text; }
        #ext-close {
            width: 5; min-width: 5; max-width: 5; height: 3; min-height: 3; max-height: 3; padding: 0;
            content-align: center middle;
            border-top: solid #8a3f4d;
            border-left: solid #7a3542;
            border-bottom: solid #250f14;
            border-right: solid #301319;
            background: #3e1f27;
            color: #ff99a8;
            text-style: bold;
        }
        #ext-close:hover {
            background: #5a2533;
            border-top: solid #ff8899;
            border-left: solid #ff7788;
            border-bottom: solid #8a3f4d;
            border-right: solid #7a3542;
            color: #ffffff;
        }
        #ext-close:focus, #ext-close.-active {
            border-top: solid #250f14;
            border-left: solid #301319;
            border-bottom: solid #8a3f4d;
            border-right: solid #7a3542;
            background: #2e141a;
        }
        #ext-search { height: 3; padding: 0 2; margin: 1 0 0 0; }
        #ext-search Input {
            width: 1fr; height: 3;
            border-top: solid #11111b;
            border-left: solid #181825;
            border-bottom: solid #45475a;
            border-right: solid #3b3d4f;
            background: #181926;
            color: $text;
        }
        #ext-search Input:focus {
            border-top: solid $accent-darken-2;
            border-left: solid $accent-darken-1;
            border-bottom: solid $accent;
            border-right: solid $accent-lighten-1;
        }
        #ext-subtitle { color: $text-muted; height: 1; padding: 0 2; display: none; }
        #ext-list {
            height: 1fr; min-height: 4; max-height: 64%;
            overflow-y: auto; scrollbar-gutter: stable; scrollbar-size: 1 1;
            scrollbar-color: $border transparent;
            margin: 0 1; padding: 1 0 0 0;
        }
        .ext-card {
            height: auto; min-height: 6; padding: 1 2;
            border-top: solid #585b70;
            border-left: solid #45475a;
            border-bottom: solid #11111b;
            border-right: solid #181825;
            background: #222436;
            margin: 0 0 1 0;
            layout: horizontal;
            align-vertical: middle;
            overflow: hidden;
            transition: border 120ms, background 120ms;
        }
        .ext-card:hover {
            border-top: solid $accent-lighten-2;
            border-left: solid $accent;
            border-bottom: solid $accent-darken-3;
            border-right: solid $accent-darken-2;
            background: #282a3e;
        }
        .ext-card.ext-busy { background: #222436; border: round $accent; }
        .ext-card-icon {
            width: 6; min-width: 6; height: 4; text-align: center; text-style: bold;
            content-align: center middle; background: #181926;
            border-top: solid #11111b;
            border-left: solid #141520;
            border-bottom: solid #45475a;
            border-right: solid #3b3d4f;
            color: $accent;
            margin-right: 2; padding: 0;
        }
        .ext-icon { width: 100%; height: 100%; text-align: center; content-align: center middle; }
        .ext-loading { width: 6; height: 3; color: $accent; content-align: center middle; }
        .ext-card-info { width: 1fr; height: auto; min-width: 16; }
        .ext-title-row { height: 1; layout: horizontal; }
        .ext-name { width: auto; height: 1; text-style: bold; margin-right: 2; color: $text; }
        .ext-type-badge { display: none; }
        .ext-verified { width: auto; height: 1; color: #5af78e; text-style: bold; }
        .ext-trusted { width: auto; height: 1; color: #5af78e; text-style: bold; margin-left: 1; }
        .ext-desc { width: 100%; height: auto; color: $text-muted; max-height: 2; overflow: hidden; margin-top: 0; }
        .ext-meta { width: 100%; height: 1; color: $text-muted; margin-top: 0; }
        .ext-status { display: none; }
        .ext-busy { color: $accent; }
        .ext-busy-label { color: $warning; text-style: bold; }
        .ext-card-actions { width: auto; min-width: 14; height: auto; layout: horizontal; align: right middle; }
        .ext-card-actions Button {
            min-width: 12; height: 3; min-height: 3; padding: 0 1; margin-left: 1;
            border-top: solid #7a829e;
            border-left: solid #636b85;
            border-bottom: solid #11111b;
            border-right: solid #181825;
            background: #2c3044;
            color: $accent;
            text-style: bold;
        }
        .ext-card-actions Button:hover {
            border-top: solid #ffffff;
            border-left: solid $accent-lighten-2;
            border-bottom: solid $accent-darken-3;
            border-right: solid $accent-darken-2;
            background: $accent;
            color: #11111b;
        }
        .ext-card-actions Button.-active, .ext-card-actions Button:focus {
            border-top: solid #11111b;
            border-left: solid #181825;
            border-bottom: solid #7a829e;
            border-right: solid #636b85;
            background: #202332;
        }
        .ext-card-actions Button:first-child { margin-left: 0; }
        .ext-card-actions Button:disabled { opacity: 0.7; }
        #ext-actions {
            height: 4; min-height: 4; padding: 0 2;
            border-top: solid #313244;
            background: #1e2030;
            layout: horizontal;
            align: center middle;
            overflow: hidden;
        }
        #ext-actions-left { width: 1fr; height: auto; layout: horizontal; align: center middle; }
        #ext-actions-left Button, #ext-actions Button {
            margin-right: 1; min-width: 12; height: 3; min-height: 3; padding: 0 1;
            border-top: solid #5a6585;
            border-left: solid #4a5270;
            border-bottom: solid #141520;
            border-right: solid #181926;
            background: #282a3e;
            color: $text;
            text-style: bold;
        }
        #ext-actions-left Button:hover, #ext-actions Button:hover {
            border-top: solid $accent-lighten-2;
            border-left: solid $accent;
            border-bottom: solid $accent-darken-3;
            border-right: solid $accent-darken-2;
            background: #343750;
            color: #ffffff;
        }
        #ext-actions #ext-close2 {
            border-top: solid #8a3f4d;
            border-left: solid #7a3542;
            border-bottom: solid #250f14;
            border-right: solid #301319;
            background: #3e1f27;
            color: #ff99a8;
        }
        #ext-actions #ext-close2:hover {
            background: #5a2533;
            border-top: solid #ff8899;
            border-left: solid #ff7788;
            border-bottom: solid #8a3f4d;
            border-right: solid #7a3542;
            color: #ffffff;
        }
        #ext-error { color: $error; background: $surface; height: 1; padding: 0 2; display: none; }
        #ext-error.show { display: block; }
        .cct-compact #ext-box { width: 96%; max-height: 94%; }
        .cct-compact #ext-titlebar { height: 4; min-height: 4; }
        .cct-compact #ext-list { min-height: 6; }
        .cct-compact .ext-card { layout: vertical; min-height: 7; padding: 1; align-vertical: top; }
        .cct-compact .ext-card-icon { display: none; }
        .cct-compact .ext-card-info { width: 100%; }
        .cct-compact .ext-card-actions { width: 100%; layout: horizontal; align: right middle; margin-top: 1; }
        .cct-compact .ext-card-actions Button { width: 100%; min-width: 8; padding: 0 1; margin: 0; }
        .cct-compact #ext-actions { height: auto; min-height: 4; padding: 1; layout: vertical; }
        .cct-compact #ext-actions-left { width: 100%; layout: horizontal; align: center middle; }
        .cct-compact #ext-actions-left Button { width: 1fr; min-width: 6; padding: 0; }
        .cct-compact #ext-close2 { width: 100%; margin-top: 1; }
        \"\"\""""

    if old_ext_css in text:
        text = text.replace(old_ext_css, new_ext_css)
        print("[OK] Redesigned ExtensionsPanel CSS with 3D effects & responsiveness")
    else:
        print("! Warning: old_ext_css not found in extensions_panel.py")

    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

# ==========================================
# 5. PATCH calc_terminal/ui/sidebar.py
# ==========================================
def patch_sidebar_py():
    path = "calc_terminal/ui/sidebar.py"
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    # 5.1 RecentWorkspaces close button 3D ruby keycap
    old_rws_close = """        #cct-recentws-close {
            width: 5; min-width: 5; max-width: 5; height: 3; min-height: 3; max-height: 3; padding: 0;
            content-align: center middle;
            border-top: solid #ffa198;
            border-left: solid #ffa198;
            border-bottom: solid #c73859;
            border-right: solid #c73859;
            background: #3e2430;
            color: #ffffff;
        }
        #cct-recentws-close:hover {
            background: #5a2c3a;
            border-top: solid #ffffff;
            border-left: solid #ffffff;
            border-bottom: solid #ffa198;
            border-right: solid #ffa198;
        }"""
    new_rws_close = """        #cct-recentws-close {
            width: 5; min-width: 5; max-width: 5; height: 3; min-height: 3; max-height: 3; padding: 0;
            content-align: center middle;
            border-top: solid #8a3f4d;
            border-left: solid #7a3542;
            border-bottom: solid #250f14;
            border-right: solid #301319;
            background: #3e1f27;
            color: #ff99a8;
            text-style: bold;
        }
        #cct-recentws-close:hover {
            background: #5a2533;
            border-top: solid #ff8899;
            border-left: solid #ff7788;
            border-bottom: solid #8a3f4d;
            border-right: solid #7a3542;
            color: #ffffff;
        }"""
    if old_rws_close in text:
        text = text.replace(old_rws_close, new_rws_close)
        print("[OK] Updated RecentWorkspacesScreen close button 3D ruby bevels")

    # 5.2 RecentWorkspaces bottom buttons layout & 3D bevels
    old_rws_btns_css = """        #cct-recentws-btns {
            height: auto; min-height: 4; padding: 0 1;
            margin-top: 1;
            border-top: solid $border;
            layout: horizontal;
            align: center middle;
        }
        #cct-recentws-btns Button {
            margin: 0 1;
            min-width: 10;
            height: 3;
            border-top: solid #7a7f9a;
            border-left: solid #6c7086;
            border-bottom: solid #11111b;
            border-right: solid #181825;
            background: $surface;
            color: $text;
            text-style: bold;
        }
        #cct-recentws-btns Button:hover {
            border-top: tall $accent-light;
            border-left: tall $accent-light;
            border-bottom: tall $accent;
            border-right: tall $accent;
            background: $surface-alt;
            color: #ffffff;
        }
        #cct-recentws-open {
            background: $accent 35%;
            color: #ffffff;
            border-top: tall $accent-light;
            border-left: tall $accent-light;
            border-bottom: tall $surface-shadow;
            border-right: tall $surface-shadow;
        }"""
    new_rws_btns_css = """        #cct-recentws-btns {
            height: 4; min-height: 4; padding: 0 1;
            margin-top: 1;
            border-top: solid $border;
            layout: horizontal;
            align: right middle;
        }
        #cct-recentws-btns Button {
            margin: 0 1;
            min-width: 10;
            height: 3;
            padding: 0 1;
            border-top: solid #5a6585;
            border-left: solid #4a5270;
            border-bottom: solid #141520;
            border-right: solid #181926;
            background: #252839;
            color: $text;
            text-style: bold;
        }
        #cct-recentws-btns Button:hover {
            border-top: solid $accent-lighten-2;
            border-left: solid $accent;
            border-bottom: solid $accent-darken-3;
            border-right: solid $accent-darken-2;
            background: #343750;
            color: #ffffff;
        }
        #cct-recentws-btns #cct-recentws-clear {
            margin-right: auto;
        }
        #cct-recentws-btns #cct-recentws-open {
            background: $accent 35%;
            color: #ffffff;
            border-top: solid $accent-lighten-2;
            border-left: solid $accent;
            border-bottom: solid $accent-darken-3;
            border-right: solid $accent-darken-2;
            min-width: 10;
        }"""
    if old_rws_btns_css in text:
        text = text.replace(old_rws_btns_css, new_rws_btns_css)
        print("[OK] Updated RecentWorkspacesScreen buttons CSS")

    # 5.3 OpenWorkspaceScreen close button 3D ruby keycap
    old_ows_close = """        #ows-close-btn {
            width: 5; min-width: 5; max-width: 5; height: 3; min-height: 3; max-height: 3; padding: 0;
            content-align: center middle;
            border-top: solid #ffa198;
            border-left: solid #ffa198;
            border-bottom: solid #c73859;
            border-right: solid #c73859;
            background: #3e2430;
            color: #ffffff;
        }
        #ows-close-btn:hover {
            background: #5a2c3a;
            border-top: solid #ffffff;
            border-left: solid #ffffff;
            border-bottom: solid #ffa198;
            border-right: solid #ffa198;
        }"""
    new_ows_close = """        #ows-close-btn {
            width: 5; min-width: 5; max-width: 5; height: 3; min-height: 3; max-height: 3; padding: 0;
            content-align: center middle;
            border-top: solid #8a3f4d;
            border-left: solid #7a3542;
            border-bottom: solid #250f14;
            border-right: solid #301319;
            background: #3e1f27;
            color: #ff99a8;
            text-style: bold;
        }
        #ows-close-btn:hover {
            background: #5a2533;
            border-top: solid #ff8899;
            border-left: solid #ff7788;
            border-bottom: solid #8a3f4d;
            border-right: solid #7a3542;
            color: #ffffff;
        }"""
    if old_ows_close in text:
        text = text.replace(old_ows_close, new_ows_close)
        print("[OK] Updated OpenWorkspaceScreen close button 3D ruby bevels")

    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

if __name__ == "__main__":
    patch_app_py()
    patch_header_py()
    patch_theme_css_py()
    patch_extensions_panel_py()
    patch_sidebar_py()
    print("Done applying 3D header and extensions redesign patches!")
