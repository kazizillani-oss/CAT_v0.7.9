import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9"

path = os.path.join(ROOT, "calc_terminal/ui/theme_css.py")
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

target1 = '''/* 3D Elevated Command Palette */
#cct-cmdpalette {
    background: $surface-alt;
    border: tall;
    border-top: tall $surface-highlight;
    border-left: tall $surface-highlight;
    border-bottom: tall $surface-dark;
    border-right: tall $surface-dark;
    tint: $surface-highlight 4%;
    margin-left: 2;
    margin-right: 2;
    margin-top: 1;
    margin-bottom: 1;
    width: 1fr;
    max-height: 8;
    height: auto;
    display: none;
    padding: 0 1;
    scrollbar-size: 1 1;
    scrollbar-gutter: stable;
    scrollbar-color: $accent $surface-dark;
    scrollbar-color-hover: $accent-highlight $surface-dark;
    scrollbar-color-active: $accent $surface-dark;
}
#cct-cmdpalette.open { display: block; }
.cct-cmd-row {
    height: 1; min-height: 1; max-height: 1;
    padding: 0 1; color: $text-muted; width: 1fr;
    border-left: thick transparent;
    border-right: thick transparent;
    transition: background 60ms, color 60ms, border-left 60ms;
}
.cct-cmd-row:hover {
    background: $surface-highlight 25%; color: #ffffff;
    border-left: thick $surface-highlight;
    border-right: thick $surface-dark;
}'''

replace1 = '''/* Clean Elevated Command Palette */
#cct-cmdpalette {
    background: $surface;
    border: round $border;
    tint: $accent 4%;
    margin-left: 1;
    margin-right: 1;
    margin-top: 0;
    margin-bottom: 0;
    width: 1fr;
    max-height: 10;
    height: auto;
    display: none;
    padding: 0;
    scrollbar-size: 1 1;
    scrollbar-gutter: auto;
    scrollbar-color: $accent $surface;
}
#cct-cmdpalette.open { display: block; }
.cct-cmd-row {
    height: 1; min-height: 1; max-height: 1;
    padding: 0 1; color: $text-muted; width: 100%;
    border-left: thick transparent;
    border-right: thick transparent;
    transition: background 60ms, color 60ms, border-left 60ms;
}
.cct-cmd-row:hover {
    background: $accent 15%; color: #ffffff;
    border-left: thick $accent;
}
.cct-cmd-row-selected {
    background: $accent 22%; color: #ffffff;
    border-left: thick $accent;
    text-style: bold;
}'''

assert target1 in content, "target1 not found in theme_css.py"
content = content.replace(target1, replace1, 1)

# Add ultra-responsive modal rules at the end of theme_css
responsive_modal_rules = '''
/* -------------------------------------------------------------
   ULTRA-RESPONSIVE PORTRAIT MODAL & NAVIGATION RULES
------------------------------------------------------------- */
.is-portrait .cct-navpanel-box,
UserPanel.is-portrait .cct-navpanel-box,
ThemesPanel.is-portrait #cct-navpanel-box {
    width: 94%;
    max-width: 52;
    min-width: 28;
    max-height: 88%;
    padding: 1 1;
    border: round $accent;
}

UserPanel.is-portrait .user-prefs,
UserPanel.is-portrait .user-quick,
UserPanel.is-portrait .user-actions {
    layout: vertical;
    height: auto;
}

UserPanel.is-portrait .user-prefs Button,
UserPanel.is-portrait .user-quick Button,
UserPanel.is-portrait .user-actions Button {
    width: 100%;
    margin-right: 0;
    margin-top: 1;
    min-height: 2;
    height: auto;
}

UserPanel.is-portrait .user-detail {
    text-overflow: ellipsis;
    overflow-x: hidden;
}

ThemesPanel.is-portrait #cct-navpanel-box {
    width: 92%;
    max-width: 48;
    max-height: 88%;
}

OpenWorkspaceScreen.is-portrait #ows-box,
.is-portrait #ows-box {
    width: 94%;
    max-width: 52;
    max-height: 88%;
    padding: 0 1;
    border: round $border;
}

OpenWorkspaceScreen.is-portrait #ows-titlebar,
.is-portrait #ows-titlebar {
    height: 3;
    min-height: 3;
    max-height: 3;
    padding: 0 1;
}

OpenWorkspaceScreen.is-portrait #ows-button-row,
.is-portrait #ows-button-row {
    layout: vertical;
    height: auto;
}

OpenWorkspaceScreen.is-portrait #ows-button-row Button,
.is-portrait #ows-button-row Button {
    width: 100%;
    margin: 1 0;
    min-height: 2;
    height: auto;
}

RecentWorkspacesScreen.is-portrait #cct-recentws-box,
.is-portrait #cct-recentws-box {
    width: 94%;
    max-width: 52;
    max-height: 88%;
    padding: 0;
    border: round $border;
}

RecentWorkspacesScreen.is-portrait #cct-recentws-titlebar,
.is-portrait #cct-recentws-titlebar {
    height: 3;
    min-height: 3;
    max-height: 3;
    padding: 0 1;
}

RecentWorkspacesScreen.is-portrait .cct-rws-label,
.is-portrait .cct-rws-label {
    width: 1fr;
    min-width: 12;
    max-width: 100%;
}

RecentWorkspacesScreen.is-portrait .cct-rws-path,
.is-portrait .cct-rws-path {
    display: none;
}
'''

content += "\n" + responsive_modal_rules

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("calc_terminal/ui/theme_css.py updated successfully.")

