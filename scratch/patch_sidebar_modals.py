import os

path = "calc_terminal/ui/sidebar.py"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Let's inspect lines around 250-430 for RecentWorkspacesScreen
# and 550-620 for OpenWorkspaceScreen
content = "".join(lines)

# 1. Update RecentWorkspacesScreen close button & buttons CSS
old_rws_css_target = """        #cct-recentws-close {
            min-width: 9; max-width: 12; height: 3; min-height: 3; max-height: 3; padding: 0 1;
        }"""

new_rws_css_target = """        #cct-recentws-close {
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

if old_rws_css_target in content:
    content = content.replace(old_rws_css_target, new_rws_css_target, 1)
    print("Replaced rws-close CSS")
else:
    print("Could not find old_rws_css_target")

# 2. Update OpenWorkspaceScreen close button CSS
old_ows_css_target = """        #ows-close-btn {
            min-width: 9; max-width: 12; height: 3; min-height: 3; max-height: 3; padding: 0 1;
        }"""

new_ows_css_target = """        #ows-close-btn {
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

if old_ows_css_target in content:
    content = content.replace(old_ows_css_target, new_ows_css_target, 1)
    print("Replaced ows-close CSS")
else:
    print("Could not find old_ows_css_target")

# 3. Update RecentWorkspaces buttons & layout
old_btns_css = """        #cct-recentws-btns {
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
        }"""

new_btns_css = """        #cct-recentws-btns {
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
        }"""

if old_btns_css in content:
    content = content.replace(old_btns_css, new_btns_css, 1)
    print("Replaced rws-btns CSS")
else:
    print("Could not find old_btns_css")

# 4. Make RecentWorkspaces responsive check in on_mount
old_rws_mount = """        def on_mount(self):
            self._render_rows()
            self._update_count()
            self.call_after_refresh(
                lambda: self.query_one("#cct-recentws-box").add_class("open"))"""

new_rws_mount = """        def on_mount(self):
            try:
                screen_size = getattr(self.app, "size", None)
                if screen_size and (screen_size.width < 75 or (screen_size.width / max(1, screen_size.height)) < 1.6):
                    self.add_class("is-portrait")
            except Exception:
                pass
            self._render_rows()
            self._update_count()
            self.call_after_refresh(
                lambda: self.query_one("#cct-recentws-box").add_class("open"))"""

if old_rws_mount in content:
    content = content.replace(old_rws_mount, new_rws_mount, 1)
    print("Replaced rws-mount responsive handling")
else:
    print("Could not find old_rws_mount")

# 5. Make RecentWorkspaces hint dynamic
old_hint = """                yield Static("Enter to open  \u00b7  Up/Down to select  \u00b7  Esc to close",
                             id="cct-recentws-hint")"""

new_hint = """                yield Static("Enter: Open  \u00b7  Up/Down: Select  \u00b7  Esc: Close",
                             id="cct-recentws-hint")"""

if old_hint in content:
    content = content.replace(old_hint, new_hint, 1)
    print("Replaced rws-hint")
else:
    print("Could not find old_hint")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Finished sidebar modals patch")

