import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9"
p = os.path.join(ROOT, "calc_terminal/ui/theme_css.py")
with open(p, "r", encoding="utf-8") as f:
    c = f.read().replace('\r\n', '\n')

# Remove duplicate .cct-cmd-row-selected
dup = """.cct-cmd-row-selected {
    background: $accent 22%; color: #ffffff;
    border-left: thick $accent;
    text-style: bold;
}
.cct-cmd-row-selected {
    background: $surface-alt;
    tint: $accent 15%;
    color: #ffffff;
    border-left: thick $accent;
    border-right: thick $surface-dark;
    text-style: bold;
}"""

single = """.cct-cmd-row-selected {
    background: $accent 22%; color: #ffffff;
    border-left: thick $accent;
    text-style: bold;
}"""

if dup in c:
    c = c.replace(dup, single, 1)
    print("Removed duplicate .cct-cmd-row-selected")

# Add responsive modal rules before """\ndef fit_dialog
modal_rules = """
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
    border: round $accent;
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
    border: round $accent;
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
"""

target_end = '"""\n\n\ndef fit_dialog'
if target_end in c:
    c = c.replace(target_end, modal_rules + target_end, 1)
    print("Inserted modal_rules into BASE_CSS")

with open(p, "w", encoding="utf-8") as f:
    f.write(c)

import py_compile
py_compile.compile(p, doraise=True)
print("theme_css.py compiles with 0 errors!")

