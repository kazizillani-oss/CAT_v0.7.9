import sys

sys.stdout.reconfigure(encoding='utf-8')

with open("calc_terminal/ui/header.py", "r", encoding="utf-8") as f:
    hdr = f.read()

hdr = hdr.replace("\r\n", "\n")

target = """_MARK = "\\u2b21"  # WHITE HEXAGON — a molecule/benzene-ring silhouette,"""
replacement = """def _safe_glyph(emoji: str, fallback: str) -> str:
    try:
        import sys
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        emoji.encode(enc)
        return emoji
    except Exception:
        return fallback

_MARK = "\\u2b21"  # WHITE HEXAGON — a molecule/benzene-ring silhouette,"""

assert target in hdr, "target not found"
hdr = hdr.replace(target, replacement)

with open("calc_terminal/ui/header.py", "w", encoding="utf-8", newline="\r\n") as f:
    f.write(hdr)

print("Added _safe_glyph to header.py")

