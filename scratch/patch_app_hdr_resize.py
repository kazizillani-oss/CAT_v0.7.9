p = "calc_terminal/ui/app.py"
with open(p, "r", encoding="utf-8") as f:
    text = f.read()

old_hdr = '''                # 3. Update header controls
                hdr = getattr(self, "header", None)
                if hdr is not None and hasattr(hdr, "on_resize"):
                    try:
                        hdr.on_resize()
                    except Exception:
                        pass'''

new_hdr = '''                # 3. Update header controls
                try:
                    b_hdr = getattr(self, "brand_header", None)
                    if b_hdr is not None and hasattr(b_hdr, "on_resize"):
                        b_hdr.on_resize()
                except Exception:
                    pass'''

if old_hdr in text:
    text = text.replace(old_hdr, new_hdr)
    print("Replaced header resize in app.py")
else:
    old_hdr_crlf = old_hdr.replace("\n", "\r\n")
    if old_hdr_crlf in text:
        text = text.replace(old_hdr_crlf, new_hdr.replace("\n", "\r\n"))
        print("Replaced header resize CRLF in app.py")
    else:
        print("old_hdr NOT found")

with open(p, "w", encoding="utf-8") as f:
    f.write(text)

