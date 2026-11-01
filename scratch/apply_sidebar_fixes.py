import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9"

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

if old_rws_box in c_sb:
    c_sb = c_sb.replace(old_rws_box, new_rws_box, 1)
    print("Replaced old_rws_box")

old_rws_mount = """        def on_mount(self):
            self.call_after_refresh(lambda: self.query_one("#cct-recentws-box").add_class("open"))"""

new_rws_mount = """        def on_mount(self):
            try:
                screen_size = getattr(self.app, "size", None)
                if screen_size and (screen_size.width < 85 or (screen_size.width / max(1, screen_size.height)) < 2.0):
                    self.add_class("is-portrait")
            except Exception:
                pass
            self.call_after_refresh(lambda: self.query_one("#cct-recentws-box").add_class("open"))"""

if old_rws_mount in c_sb:
    c_sb = c_sb.replace(old_rws_mount, new_rws_mount, 1)
    print("Replaced old_rws_mount")

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

if old_ows_box in c_sb:
    c_sb = c_sb.replace(old_ows_box, new_ows_box, 1)
    print("Replaced old_ows_box")

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

if old_ows_mount in c_sb:
    c_sb = c_sb.replace(old_ows_mount, new_ows_mount, 1)
    print("Replaced old_ows_mount")

with open(path_sb, "w", encoding="utf-8") as f:
    f.write(c_sb)
print("Updated calc_terminal/ui/sidebar.py successfully.")

