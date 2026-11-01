import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9"

# 1. Update nav_screens.py
path_nav = os.path.join(ROOT, "calc_terminal/ui/nav_screens.py")
with open(path_nav, "r", encoding="utf-8") as f:
    c_nav = f.read().replace('\r\n', '\n')

old_panel_box = """        .cct-navpanel-box {
            width: 90%;
            max-width: 68;
            min-width: 30;
            height: auto;
            max-height: 28;
            background: $surface;
            border: tall $border-active $border;
            padding: 1 2;
            opacity: 1;
            offset-y: 0;
            layout: vertical;
            overflow: hidden hidden;
        }"""

new_panel_box = """        .cct-navpanel-box {
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

assert old_panel_box in c_nav, "old_panel_box not found"
c_nav = c_nav.replace(old_panel_box, new_panel_box, 1)

old_themes_css = """        ThemesPanel { align: center middle; background: $app-background 60%; width: 100%; height: 100%; }
        #cct-navpanel-box { width: 56; max-height: 30; overflow: hidden hidden; }"""

new_themes_css = """        ThemesPanel { align: center middle; background: $app-background 60%; width: 100%; height: 100%; }
        #cct-navpanel-box { width: 92%; max-width: 56; max-height: 30; overflow: hidden hidden; border: round $border; }
        ThemesPanel.is-portrait #cct-navpanel-box,
        .is-portrait #cct-navpanel-box { width: 92%; max-width: 48; max-height: 85%; padding: 1 1; border: round $accent; }"""

assert old_themes_css in c_nav, "old_themes_css not found"
c_nav = c_nav.replace(old_themes_css, new_themes_css, 1)

old_themes_init = """        def __init__(self, current_theme):
            self._current = current_theme
            super().__init__()
            self.title = "Themes" """

# Add on_mount to ThemesPanel
old_themes_comp = """        def compose_body(self):"""
new_themes_comp = """        def on_mount(self):
            try:
                screen_size = getattr(self.app, "size", None)
                if screen_size and (screen_size.width < 80 or (screen_size.width / max(1, screen_size.height)) < 2.0):
                    self.add_class("is-portrait")
            except Exception:
                pass
            super().on_mount()

        def compose_body(self):"""

assert old_themes_comp in c_nav, "old_themes_comp not found"
c_nav = c_nav.replace(old_themes_comp, new_themes_comp, 1)

# UserPanel
old_user_css = """        UserPanel { align: center middle; background: $app-background 60%; width: 100%; height: 100%; }
        .cct-navpanel-box { width: 68; max-height: 34; overflow: hidden hidden; }"""

new_user_css = """        UserPanel { align: center middle; background: $app-background 60%; width: 100%; height: 100%; }
        .cct-navpanel-box { width: 92%; max-width: 68; max-height: 34; overflow: hidden hidden; border: round $border; }
        UserPanel.is-portrait .cct-navpanel-box,
        .is-portrait .cct-navpanel-box { width: 94%; max-width: 52; max-height: 88%; padding: 1 1; border: round $accent; }
        UserPanel.is-portrait .user-prefs,
        UserPanel.is-portrait .user-quick,
        UserPanel.is-portrait .user-actions { layout: vertical; height: auto; }
        UserPanel.is-portrait .user-prefs Button,
        UserPanel.is-portrait .user-quick Button,
        UserPanel.is-portrait .user-actions Button { width: 100%; margin-right: 0; margin-top: 1; min-height: 2; height: auto; }
        UserPanel.is-portrait .user-detail { text-overflow: ellipsis; overflow-x: hidden; }"""

assert old_user_css in c_nav, "old_user_css not found"
c_nav = c_nav.replace(old_user_css, new_user_css, 1)

old_user_mount = """        def on_mount(self):
            super().on_mount()
            self.call_after_refresh(self._refresh)"""

new_user_mount = """        def on_mount(self):
            try:
                screen_size = getattr(self.app, "size", None)
                if screen_size and (screen_size.width < 85 or (screen_size.width / max(1, screen_size.height)) < 2.0):
                    self.add_class("is-portrait")
            except Exception:
                pass
            super().on_mount()
            self.call_after_refresh(self._refresh)"""

assert old_user_mount in c_nav, "old_user_mount not found"
c_nav = c_nav.replace(old_user_mount, new_user_mount, 1)

with open(path_nav, "w", encoding="utf-8") as f:
    f.write(c_nav)
print("Updated calc_terminal/ui/nav_screens.py successfully.")

# 2. Update sidebar.py
path_sb = os.path.join(ROOT, "calc_terminal/ui/sidebar.py")
with open(path_sb, "r", encoding="utf-8") as f:
    c_sb = f.read().replace('\r\n', '\n')

old_rws_box = """        #cct-recentws-box {
            width: 84; height: auto; max-height: 88%;
            background: $surface; border: tall $border-active $border;
            padding: 0 0 1 0;
            opacity: 0; offset-y: 1;
            transition: opacity 120ms, offset 150ms;
        }"""

new_rws_box = """        #cct-recentws-box {
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
        }"""

assert old_rws_box in c_sb, "old_rws_box not found"
c_sb = c_sb.replace(old_rws_box, new_rws_box, 1)

old_rws_mount = """        def on_mount(self):
            self.call_after_refresh(
                lambda: self.query_one("#cct-recentws-box").add_class("open"))"""

new_rws_mount = """        def on_mount(self):
            try:
                screen_size = getattr(self.app, "size", None)
                if screen_size and (screen_size.width < 85 or (screen_size.width / max(1, screen_size.height)) < 2.0):
                    self.add_class("is-portrait")
            except Exception:
                pass
            self.call_after_refresh(
                lambda: self.query_one("#cct-recentws-box").add_class("open"))"""

assert old_rws_mount in c_sb, "old_rws_mount not found"
c_sb = c_sb.replace(old_rws_mount, new_rws_mount, 1)

old_ows_box = """        #ows-box {
            width: 70; height: auto; max-height: 36;
            background: $surface; border: tall $border-active $border; padding: 0;
            opacity: 0; offset-y: 1;
            transition: opacity 150ms, offset 180ms;
        }"""

new_ows_box = """        #ows-box {
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
        }"""

assert old_ows_box in c_sb, "old_ows_box not found"
c_sb = c_sb.replace(old_ows_box, new_ows_box, 1)

old_ows_mount = """        def on_mount(self):
            self.call_after_refresh(
                lambda: self.query_one("#ows-box").add_class("open"))"""

new_ows_mount = """        def on_mount(self):
            try:
                screen_size = getattr(self.app, "size", None)
                if screen_size and (screen_size.width < 85 or (screen_size.width / max(1, screen_size.height)) < 2.0):
                    self.add_class("is-portrait")
            except Exception:
                pass
            self.call_after_refresh(
                lambda: self.query_one("#ows-box").add_class("open"))"""

assert old_ows_mount in c_sb, "old_ows_mount not found"
c_sb = c_sb.replace(old_ows_mount, new_ows_mount, 1)

with open(path_sb, "w", encoding="utf-8") as f:
    f.write(c_sb)
print("Updated calc_terminal/ui/sidebar.py successfully.")

