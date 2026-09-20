"""Compare Textual border glyph sets: is `tall` a chunkier 3D bevel than `heavy`?"""
import importlib
import pkgutil

import textual

found = None
for mod in pkgutil.walk_packages(textual.__path__, "textual."):
    name = mod.name
    try:
        m = importlib.import_module(name)
    except Exception:
        continue
    if hasattr(m, "BORDER_CHARS"):
        found = name
        chars = m.BORDER_CHARS
        break

print("BORDER_CHARS found in:", found)
if found:
    for kind in ("tall", "heavy", "round", "solid", "double", "thick", "panel", "wide", "hkey", "vkey"):
        if kind in chars:
            print(f"  {kind:>7}: {chars[kind]}")
