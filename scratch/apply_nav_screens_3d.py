import re

PATH = r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9\calc_terminal\ui\nav_screens.py"

with open(PATH, "r", encoding="utf-8") as f:
    code = f.read()

# 1. Update _CenteredPanel CSS
old_centered = """        .cct-navpanel-box {
            width: 90%;
            max-width: 68;
            min-width: 28;
            height: auto;
            max-height: 88%;
            background: $surface;
            border: round $border;
            padding: 1 2;
            opacity: 1;
            offset-y: 0;
            layout: vertical;
            overflow: hidden hidden;
        }"""

new_centered = """        .cct-navpanel-box {
            width: 90%;
            max-width: 68;
            min-width: 28;
            height: auto;
            max-height: 88%;
            background: $surface;
            border-top: tall $surface-highlight;
            border-left: tall $surface-highlight;
            border-bottom: tall $border;
            border-right: tall $border;
            padding: 1 2;
            opacity: 1;
            offset-y: 0;
            layout: vertical;
            overflow: hidden hidden;
        }"""

assert old_centered in code, "old_centered not found"
code = code.replace(old_centered, new_centered)

# 2. Update ThemesPanel CSS
old_themes = """        #cct-navpanel-box { width: 92%; max-width: 56; max-height: 30; overflow: hidden hidden; border: round $border; }
        ThemesPanel.is-portrait #cct-navpanel-box,
        .is-portrait #cct-navpanel-box { width: 92%; max-width: 48; max-height: 85%; padding: 1 1; border: round $accent; }"""

new_themes = """        #cct-navpanel-box {
            width: 92%; max-width: 56; max-height: 30; overflow: hidden hidden;
            border-top: tall $surface-highlight;
            border-left: tall $surface-highlight;
            border-bottom: tall $border;
            border-right: tall $border;
        }
        ThemesPanel.is-portrait #cct-navpanel-box,
        .is-portrait #cct-navpanel-box {
            width: 92%; max-width: 48; max-height: 85%; padding: 1 1;
            border-top: tall $surface-highlight;
            border-left: tall $surface-highlight;
            border-bottom: tall $border;
            border-right: tall $border;
        }"""

assert old_themes in code, "old_themes not found"
code = code.replace(old_themes, new_themes)

# 3. Update UserPanel CSS
old_user = """        .cct-navpanel-box { width: 92%; max-width: 68; max-height: 34; overflow: hidden hidden; border: round $border; }
        UserPanel.is-portrait .cct-navpanel-box,
        .is-portrait .cct-navpanel-box { width: 94%; max-width: 52; max-height: 88%; padding: 1 1; border: round $accent; }
        UserPanel.is-portrait .user-prefs,
        UserPanel.is-portrait .user-quick,
        UserPanel.is-portrait .user-actions { layout: vertical; height: auto; }
        UserPanel.is-portrait .user-prefs Button,
        UserPanel.is-portrait .user-quick Button,
        UserPanel.is-portrait .user-actions Button { width: 100%; margin-right: 0; margin-top: 1; min-height: 2; height: auto; }
        UserPanel.is-portrait .user-detail { text-overflow: ellipsis; overflow-x: hidden; }
        .user-section { color: $text-faint; height: auto; padding-top: 1;
                        border-top: solid $border; margin-top: 1; }
        .user-detail { height: 1; color: $text-muted; padding: 0 1; }
        .user-toggle-row { height: 3; align-vertical: middle; padding: 0 1; margin-top: 1; }
        .user-toggle-label { width: 1fr; height: 1; color: $text; text-style: bold; }
        #user-wordwrap-switch { border: tall $border-active $border; background: $surface-alt; }
        #user-wordwrap-switch.-on { border: tall #86efac $success; }
        .user-quick { height: auto; padding-top: 1; border-top: solid $border; }
        .user-quick Button { margin-right: 1; margin-top: 0; border: tall $border-active $border; }
        .user-actions { height: auto; padding-top: 1; border-top: solid $border; }
        .user-actions Button { margin-right: 1; margin-top: 0; border: tall $border-active $border; }
        .user-prefs { height: auto; padding-top: 1; }
        .user-prefs Button { margin-right: 1; margin-top: 1; border: tall $border-active $border; }"""

new_user = """        .cct-navpanel-box {
            width: 92%; max-width: 68; max-height: 34; overflow: hidden hidden;
            border-top: tall $surface-highlight;
            border-left: tall $surface-highlight;
            border-bottom: tall $border;
            border-right: tall $border;
        }
        UserPanel.is-portrait .cct-navpanel-box,
        .is-portrait .cct-navpanel-box {
            width: 94%; max-width: 52; max-height: 88%; padding: 1 1;
            border-top: tall $surface-highlight;
            border-left: tall $surface-highlight;
            border-bottom: tall $border;
            border-right: tall $border;
        }
        UserPanel.is-portrait .user-prefs,
        UserPanel.is-portrait .user-quick,
        UserPanel.is-portrait .user-actions { layout: vertical; height: auto; }
        UserPanel.is-portrait .user-prefs Button,
        UserPanel.is-portrait .user-quick Button,
        UserPanel.is-portrait .user-actions Button {
            width: 100%; margin-right: 0; margin-top: 1; min-height: 3; height: auto;
        }
        UserPanel.is-portrait .user-detail { text-overflow: ellipsis; overflow-x: hidden; }
        .user-section { color: $text-faint; height: auto; padding-top: 1;
                        border-top: solid $border; margin-top: 1; }
        .user-detail { height: 1; color: $text-muted; padding: 0 1; }
        .user-toggle-row { height: 3; align-vertical: middle; padding: 0 1; margin-top: 1; }
        .user-toggle-label { width: 1fr; height: 1; color: $text; text-style: bold; }
        #user-wordwrap-switch {
            border-top: tall $surface-highlight;
            border-left: tall $surface-highlight;
            border-bottom: tall $surface-shadow;
            border-right: tall $surface-shadow;
            background: $surface-alt;
        }
        #user-wordwrap-switch.-on { border: tall #86efac $success; }
        .user-quick { height: auto; padding-top: 1; border-top: solid $border; }
        .user-quick Button {
            margin-right: 1; margin-top: 0; height: 3;
            border-top: tall $surface-highlight;
            border-left: tall $surface-highlight;
            border-bottom: tall $surface-shadow;
            border-right: tall $surface-shadow;
            background: $surface;
            color: $text;
            text-style: bold;
        }
        .user-quick Button:hover {
            border-top: tall $accent-lighten-2;
            border-left: tall $accent-lighten-2;
            border-bottom: tall $accent;
            border-right: tall $accent;
            background: $surface-alt;
            color: #ffffff;
        }
        .user-actions { height: auto; padding-top: 1; border-top: solid $border; }
        .user-actions Button {
            margin-right: 1; margin-top: 0; height: 3;
            border-top: tall $surface-highlight;
            border-left: tall $surface-highlight;
            border-bottom: tall $surface-shadow;
            border-right: tall $surface-shadow;
            background: $surface;
            color: $text;
            text-style: bold;
        }
        .user-actions Button:hover {
            border-top: tall $accent-lighten-2;
            border-left: tall $accent-lighten-2;
            border-bottom: tall $accent;
            border-right: tall $accent;
            background: $surface-alt;
            color: #ffffff;
        }
        .user-prefs { height: auto; padding-top: 1; }
        .user-prefs Button {
            margin-right: 1; margin-top: 1; height: 3;
            border-top: tall $surface-highlight;
            border-left: tall $surface-highlight;
            border-bottom: tall $surface-shadow;
            border-right: tall $surface-shadow;
            background: $surface;
            color: $text;
            text-style: bold;
        }
        .user-prefs Button:hover {
            border-top: tall $accent-lighten-2;
            border-left: tall $accent-lighten-2;
            border-bottom: tall $accent;
            border-right: tall $accent;
            background: $surface-alt;
            color: #ffffff;
        }"""

assert old_user in code, "old_user not found"
code = code.replace(old_user, new_user)

with open(PATH, "w", encoding="utf-8") as f:
    f.write(code)

print("nav_screens.py updated successfully.")

