import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9"
p = os.path.join(ROOT, "calc_terminal/ui/nav_screens.py")
with open(p, "r", encoding="utf-8") as f:
    c = f.read().replace('\r\n', '\n')

old_mounts = """        def on_mount(self):
            try:
                screen_size = getattr(self.app, "size", None)
                if screen_size and (screen_size.width < 80 or (screen_size.width / max(1, screen_size.height)) < 2.0):
                    self.add_class("is-portrait")
            except Exception:
                pass
            super().on_mount()

        def compose_body(self):
            yield from ()

        def on_mount(self):
            self.call_after_refresh(
                lambda: self.query_one("#cct-navpanel-box").add_class("open"))"""

new_mounts = """        def compose_body(self):
            yield from ()

        def on_mount(self):
            try:
                screen_size = getattr(self.app, "size", None)
                if screen_size and (screen_size.width < 85 or (screen_size.width / max(1, screen_size.height)) < 2.0):
                    self.add_class("is-portrait")
            except Exception:
                pass
            self.call_after_refresh(
                lambda: self.query_one("#cct-navpanel-box").add_class("open"))"""

assert old_mounts in c, "old_mounts not found"
c = c.replace(old_mounts, new_mounts, 1)

with open(p, "w", encoding="utf-8") as f:
    f.write(c)

print("nav_screens.py on_mount consolidated successfully.")

