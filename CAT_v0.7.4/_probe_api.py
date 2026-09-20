"""Tiny API probe for Textual's stylesheet reader (run once)."""
import inspect

from textual.css.stylesheet import Stylesheet

print("Stylesheet methods:",
      [m for m in dir(Stylesheet) if not m.startswith("__")])
print()
print(inspect.signature(Stylesheet.add_source))
print()
try:
    from textual.app import App
    print("App css hooks:",
          [m for m in dir(App) if "css" in m.lower()][:40])
except Exception as exc:
    print("App import failed", exc)
