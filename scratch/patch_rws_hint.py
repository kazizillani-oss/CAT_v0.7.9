path = "calc_terminal/ui/sidebar.py"
with open(path, "r", encoding="utf-8") as f:
    txt = f.read()

# Replace hint in compose
old_hint = 'yield Static("Enter to open  \\u00b7  Up/Down to select  \\u00b7  Esc to close",\n                             id="cct-recentws-hint")'
new_hint = 'yield Static("Enter: Open  \\u00b7  Up/Down: Select  \\u00b7  Esc: Close",\n                             id="cct-recentws-hint")'
if old_hint in txt:
    txt = txt.replace(old_hint, new_hint, 1)
    print("Replaced hint")
else:
    print("Hint not found, trying raw string")
    old_hint_raw = 'yield Static("Enter to open  ·  Up/Down to select  ·  Esc to close",\n                             id="cct-recentws-hint")'
    new_hint_raw = 'yield Static("Enter: Open  ·  Up/Down: Select  ·  Esc: Close",\n                             id="cct-recentws-hint")'
    if old_hint_raw in txt:
        txt = txt.replace(old_hint_raw, new_hint_raw, 1)
        print("Replaced hint raw")

# In on_mount, update hint for narrow terminals
old_on_mount = """        def on_mount(self):
            try:
                screen_size = getattr(self.app, "size", None)
                if screen_size and (screen_size.width < 85 or (screen_size.width / max(1, screen_size.height)) < 2.0):
                    self.add_class("is-portrait")
            except Exception:
                pass"""

new_on_mount = """        def on_mount(self):
            try:
                screen_size = getattr(self.app, "size", None)
                if screen_size and (screen_size.width < 85 or (screen_size.width / max(1, screen_size.height)) < 2.0):
                    self.add_class("is-portrait")
                if screen_size and screen_size.width < 56:
                    self.query_one("#cct-recentws-hint", Static).update("Enter: Open  ·  Esc: Close")
            except Exception:
                pass"""

if old_on_mount in txt:
    txt = txt.replace(old_on_mount, new_on_mount, 1)
    print("Replaced on_mount in RecentWorkspacesScreen")

with open(path, "w", encoding="utf-8") as f:
    f.write(txt)
print("Finished update")

