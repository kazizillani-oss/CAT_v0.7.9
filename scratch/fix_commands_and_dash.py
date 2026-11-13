import sys

# 1. Fix commands_data.py
p1 = r"calc_terminal/commands_data.py"
with open(p1, "r", encoding="utf-8") as f:
    text = f.read()

target1 = '    ("/sim3d", "[BETA\n'
repl1 = '    ("/sim3d", "[BETA] Interactive 3D molecular simulation"),\n'
if target1 in text:
    text = text.replace(target1, repl1)
    with open(p1, "w", encoding="utf-8") as f:
        f.write(text)
    print("Fixed commands_data.py")
else:
    print("Target 1 not found in commands_data.py")

# 2. Fix dashboard.py _get_viewport_size
p2 = r"calc_terminal/ui/dashboard.py"
with open(p2, "r", encoding="utf-8") as f:
    text = f.read()

target2 = """            if not w or not h:
                if hasattr(self, "app") and self.app and getattr(self.app, "size", None):
                    w = w or self.app.size.width
                    h = h or max(1, self.app.size.height - 8)"""

repl2 = """            if not w or not h:
                try:
                    if getattr(self, "is_attached", False):
                        app = getattr(self, "app", None)
                        if app and getattr(app, "size", None):
                            w = w or app.size.width
                            h = h or max(1, app.size.height - 8)
                except Exception:
                    pass"""

if target2 in text:
    text = text.replace(target2, repl2)
    with open(p2, "w", encoding="utf-8") as f:
        f.write(text)
    print("Fixed dashboard.py")
else:
    print("Target 2 not found in dashboard.py")

