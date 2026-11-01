import re

PATH = r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9\calc_terminal\ui\sidebar.py"

with open(PATH, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Update RecentWorkspacesScreen CSS
old_rws_css = """        RecentWorkspacesScreen { align: center middle; background: $app-background 60%; }
        #cct-recentws-box {
            width: 92%; max-width: 84; height: auto; max-height: 88%;
            background: $surface; border: round $border;
            padding: 0 0 1 0;
            opacity: 0; offset-y: 1;
            transition: opacity 120ms, offset 150ms;
        }
        RecentWorkspacesScreen.is-portrait #cct-recentws-box,
        .is-portrait #cct-recentws-box {
            width: 94%; max-width: 52; max-height: 88%; padding: 0; border: round $accent;
        }
        RecentWorkspacesScreen.is-portrait #cct-recentws-titlebar,
        .is-portrait #cct-recentws-titlebar {
            height: 3; min-height: 3; max-height: 3; padding: 0 1;
        }
        RecentWorkspacesScreen.is-portrait .cct-rws-label,
        .is-portrait .cct-rws-label {
            width: 1fr; min-width: 12; max-width: 100%;
        }
        RecentWorkspacesScreen.is-portrait .cct-rws-path,
        .is-portrait .cct-rws-path {
            display: none;
        }
        #cct-recentws-box.open { opacity: 1; offset-y: 0; }
        #cct-recentws-titlebar {
            height: 5; min-height: 5; max-height: 5; padding: 0 2;
            border-bottom: solid $border;
            layout: horizontal; align: center middle;
        }
        #cct-recentws-title { text-style: bold; width: 1fr; }
        #cct-recentws-close {
            min-width: 9; max-width: 12; height: 3; min-height: 3; padding: 0 1;
        }"""

new_rws_css = """        RecentWorkspacesScreen { align: center middle; background: $app-background 60%; }
        #cct-recentws-box {
            width: 92%; max-width: 84; height: auto; max-height: 88%;
            background: $surface;
            border-top: tall $surface-highlight;
            border-left: tall $surface-highlight;
            border-bottom: tall $border;
            border-right: tall $border;
            padding: 0 0 1 0;
            opacity: 0; offset-y: 1;
            transition: opacity 120ms, offset 150ms;
        }
        RecentWorkspacesScreen.is-portrait #cct-recentws-box,
        .is-portrait #cct-recentws-box {
            width: 94%; max-width: 52; max-height: 88%; padding: 0;
            border-top: tall $surface-highlight;
            border-left: tall $surface-highlight;
            border-bottom: tall $border;
            border-right: tall $border;
        }
        RecentWorkspacesScreen.is-portrait #cct-recentws-titlebar,
        .is-portrait #cct-recentws-titlebar {
            height: 4; min-height: 4; max-height: 4; padding: 0 1;
        }
        RecentWorkspacesScreen.is-portrait .cct-rws-label,
        .is-portrait .cct-rws-label {
            width: 1fr; min-width: 12; max-width: 100%;
        }
        RecentWorkspacesScreen.is-portrait .cct-rws-path,
        .is-portrait .cct-rws-path {
            display: none;
        }
        #cct-recentws-box.open { opacity: 1; offset-y: 0; }
        #cct-recentws-titlebar {
            height: 4; min-height: 4; max-height: 4; padding: 0 2;
            border-bottom: solid $border;
            layout: horizontal; align: center middle;
        }
        #cct-recentws-title { text-style: bold; width: 1fr; }
        #cct-recentws-close {
            min-width: 9; max-width: 12; height: 3; min-height: 3; max-height: 3; padding: 0 1;
        }"""

assert old_rws_css in code, "old_rws_css not found"
code = code.replace(old_rws_css, new_rws_css)

# Update RecentWorkspacesScreen btns styling
old_rws_btns = """        #cct-recentws-btns {
            height: 4; padding: 0 2;
            margin-top: 1;
            border-top: solid $border;
            align-horizontal: right;
            align-vertical: middle;
        }
        #cct-recentws-btns Button {
            margin-left: 1;
            min-width: 14;
            height: 3;
            border: tall $border-active $border;
        }
        .cct-btn-spacer { width: 1fr; }"""

new_rws_btns = """        #cct-recentws-btns {
            height: auto; min-height: 4; padding: 0 2;
            margin-top: 1;
            border-top: solid $border;
            layout: horizontal;
            align: right middle;
        }
        #cct-recentws-btns Button {
            margin-left: 1;
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
        #cct-recentws-btns Button:hover {
            border-top: tall $accent-lighten-2;
            border-left: tall $accent-lighten-2;
            border-bottom: tall $accent;
            border-right: tall $accent;
            background: $surface-alt;
            color: #ffffff;
        }
        #cct-recentws-open {
            background: $accent 35%;
            color: #ffffff;
            border-top: tall $accent-lighten-2;
            border-left: tall $accent-lighten-2;
            border-bottom: tall $surface-shadow;
            border-right: tall $surface-shadow;
        }
        RecentWorkspacesScreen.is-portrait #cct-recentws-btns,
        .is-portrait #cct-recentws-btns {
            layout: vertical;
            height: auto;
            min-height: 8;
            padding: 0 1;
            margin-top: 1;
            border-top: solid $border;
            align: center middle;
        }
        RecentWorkspacesScreen.is-portrait #cct-recentws-btns Button,
        .is-portrait #cct-recentws-btns Button {
            width: 100%;
            margin: 1 0 0 0;
            min-height: 3;
            height: auto;
        }
        RecentWorkspacesScreen.is-portrait .cct-btn-spacer,
        .is-portrait .cct-btn-spacer {
            display: none;
        }
        .cct-btn-spacer { width: 1fr; }"""

assert old_rws_btns in code, "old_rws_btns not found"
code = code.replace(old_rws_btns, new_rws_btns)

# Update OpenWorkspaceScreen CSS
old_ows_css = """        OpenWorkspaceScreen { align: center middle; background: $app-background 70%; }
        #ows-box {
            width: 92%; max-width: 70; height: auto; max-height: 36;
            background: $surface; border: round $border; padding: 0;
            opacity: 0; offset-y: 1;
            transition: opacity 150ms, offset 180ms;
        }
        OpenWorkspaceScreen.is-portrait #ows-box,
        .is-portrait #ows-box {
            width: 94%; max-width: 52; max-height: 88%; padding: 0 1; border: round $accent;
        }
        OpenWorkspaceScreen.is-portrait #ows-titlebar,
        .is-portrait #ows-titlebar {
            height: 3; min-height: 3; max-height: 3; padding: 0 1;
        }
        OpenWorkspaceScreen.is-portrait #ows-button-row,
        .is-portrait #ows-button-row {
            layout: vertical; height: auto;
        }
        OpenWorkspaceScreen.is-portrait #ows-button-row Button,
        .is-portrait #ows-button-row Button {
            width: 100%; margin: 1 0; min-height: 2; height: auto;
        }
        #ows-box.open { opacity: 1; offset-y: 0; }
        #ows-titlebar {
            height: 5; min-height: 5; max-height: 5; padding: 0 2;
            border-bottom: solid $border; margin-bottom: 0;
            layout: horizontal; align: center middle;
        }
        #ows-title { text-style: bold; width: 1fr; }
        #ows-close-btn {
            min-width: 9; max-width: 12; height: 3; min-height: 3; padding: 0 1;
        }"""

new_ows_css = """        OpenWorkspaceScreen { align: center middle; background: $app-background 70%; }
        #ows-box {
            width: 92%; max-width: 70; height: auto; max-height: 36;
            background: $surface;
            border-top: tall $surface-highlight;
            border-left: tall $surface-highlight;
            border-bottom: tall $border;
            border-right: tall $border;
            padding: 0;
            opacity: 0; offset-y: 1;
            transition: opacity 150ms, offset 180ms;
        }
        OpenWorkspaceScreen.is-portrait #ows-box,
        .is-portrait #ows-box {
            width: 94%; max-width: 52; max-height: 88%; padding: 0 1;
            border-top: tall $surface-highlight;
            border-left: tall $surface-highlight;
            border-bottom: tall $border;
            border-right: tall $border;
        }
        OpenWorkspaceScreen.is-portrait #ows-titlebar,
        .is-portrait #ows-titlebar {
            height: 4; min-height: 4; max-height: 4; padding: 0 1;
        }
        OpenWorkspaceScreen.is-portrait #ows-button-row,
        .is-portrait #ows-button-row {
            layout: vertical; height: auto;
        }
        OpenWorkspaceScreen.is-portrait #ows-button-row Button,
        .is-portrait #ows-button-row Button {
            width: 100%; margin: 1 0; min-height: 3; height: auto;
        }
        #ows-box.open { opacity: 1; offset-y: 0; }
        #ows-titlebar {
            height: 4; min-height: 4; max-height: 4; padding: 0 2;
            border-bottom: solid $border; margin-bottom: 0;
            layout: horizontal; align: center middle;
        }
        #ows-title { text-style: bold; width: 1fr; }
        #ows-close-btn {
            min-width: 9; max-width: 12; height: 3; min-height: 3; max-height: 3; padding: 0 1;
        }"""

assert old_ows_css in code, "old_ows_css not found"
code = code.replace(old_ows_css, new_ows_css)

# Update ows-button-row buttons with 3D bevels
old_ows_btns = """        #ows-button-row { height: 3; align: center middle; margin-top: 0; }
        #ows-button-row Button { margin: 0 1; }"""

new_ows_btns = """        #ows-button-row { height: auto; min-height: 4; align: center middle; margin-top: 1; }
        #ows-button-row Button {
            margin: 0 1;
            height: 3;
            border-top: tall $surface-highlight;
            border-left: tall $surface-highlight;
            border-bottom: tall $surface-shadow;
            border-right: tall $surface-shadow;
            background: $surface;
            color: $text;
            text-style: bold;
        }
        #ows-button-row Button:hover {
            border-top: tall $accent-lighten-2;
            border-left: tall $accent-lighten-2;
            border-bottom: tall $accent;
            border-right: tall $accent;
            background: $surface-alt;
            color: #ffffff;
        }
        #ows-open-btn {
            background: $accent 35%;
            color: #ffffff;
            border-top: tall $accent-lighten-2;
            border-left: tall $accent-lighten-2;
            border-bottom: tall $surface-shadow;
            border-right: tall $surface-shadow;
        }"""

assert old_ows_btns in code, "old_ows_btns not found"
code = code.replace(old_ows_btns, new_ows_btns)

with open(PATH, "w", encoding="utf-8") as f:
    f.write(code)

print("sidebar.py updated successfully with 3D effects and responsive layouts.")

