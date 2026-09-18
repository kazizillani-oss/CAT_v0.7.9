"""v0.7.8.2 headless trace of the attachment data flow.

Exercises: chip -> Attachment object -> MessageSubmitted -> session Turn
-> _augment_prompt/build_context -> stream_ai prompt & attachments=.
Prints PASS/FAIL per link of the data pipeline.
"""
import os
import sys

sys.path.insert(0, ".")
os.environ["CCT_HEADLESS"] = "1"

import tempfile

from calc_terminal import attachments as _att
from calc_terminal.session import ChatSession

fails = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


# ---- 1. Attachment object creation + extraction -----------------------
tmp = tempfile.mkdtemp()
py_path = os.path.join(tmp, "test.py")
with open(py_path, "w", encoding="utf-8") as f:
    f.write("def hello(name):\n    return f'hi {name}'\n")

att = _att.Attachment(py_path)
check("attachment created", att.path == os.path.abspath(py_path))
fresh = _att.AttachmentManager.create(py_path)
check("extraction ready", fresh.extraction_status == _att.STATUS_READY, fresh.error or "")
check("content has file body", fresh.content and "hello" in fresh.content,
      (fresh.content or "")[:80])
check("kind is code", fresh.kind == "code", fresh.kind)

# ---- 2. build_context block --------------------------------------------
ctx = _att.AttachmentManager.build_context([fresh])
check("context block built", bool(ctx), (ctx or "")[:100])
check("context contains content", "hello" in ctx)
check("context names the file", "test.py" in ctx)

# ---- 3. ensure_extracted on a pending object ---------------------------
att2 = _att.Attachment(py_path)  # status selecting
att2.extraction_status = _att.STATUS_READING
att2.content = None
_att.AttachmentManager.ensure_extracted(att2)
check("ensure_extracted recovers content", att2.content and "hello" in att2.content,
      str(att2.extraction_status))

# ---- 4. session turn holds objects -------------------------------------
sess = ChatSession()
turn = sess.add_user_turn("Analyze this file.", [fresh], mode="notebook")
check("turn stores attachments", turn.attachments == [fresh])
hist = sess.as_prompt_history()
check("history folds attachment context", any("hello" in t for _r, t in hist))

# ---- 5. provider capability layer --------------------------------------
caps_none = _att.provider_capabilities({"provider": "openai", "model": "gpt-3.5-turbo", "api_style": "openai"})
check("gpt-3.5 -> no vision", caps_none.get("vision") is False)
caps_vision = _att.provider_capabilities({"provider": "openai", "model": "gpt-4o", "api_style": "openai"})
check("gpt-4o -> vision", caps_vision.get("vision") is True)
caps_unknown = _att.provider_capabilities({"provider": "openai", "model": "custom-model-x", "api_style": "openai"})
check("unknown model -> safe no-vision", caps_unknown.get("vision") is False)

# ---- 6. weak-model fallback (text model + py file) ---------------------
from calc_terminal import aicore
monkey = {
    "provider": "openai", "model": "gpt-3.5-turbo", "api_style": "openai",
    "api_key": "test", "base_url": "http://127.0.0.1:1",
}
aug = _att.AttachmentManager.build_context([fresh])
check("weak-model text block usable", "hello" in aug)

# _user_content with vision=False must return plain prompt
from calc_terminal.aicore import _user_content
uc = _user_content("Analyze this file.", [fresh], vision=False)
check("non-vision user content is plain text", isinstance(uc, str))
uc_v = _user_content("Look at this.", [fresh], vision=True)
check("non-image + vision stays plain text", isinstance(uc_v, str))

# ---- 7. image attachment -----------------------------------------------
png_path = os.path.join(tmp, "img.png")
try:
    from PIL import Image
    Image.new("RGB", (4, 4), (255, 0, 0)).save(png_path)
    img = _att.AttachmentManager.create(png_path)
    check("image extraction ready", img.extraction_status == _att.STATUS_READY, img.error or "")
    check("image kind", img.kind == "image")
    check("image has payload", _att.attachment_has_image_payload(img) is True)
    mime, b64 = _att.encode_image_data_url(png_path)
    check("image data url", mime == "image/png" and b64)
    uc_v = _user_content("Look at this.", [img], vision=True)
    check("vision user content becomes parts list", isinstance(uc_v, list) and len(uc_v) == 2)
except ImportError:
    print("SKIP image tests (PIL missing)")

# ---- 8. failure honesty -------------------------------------------------
missing = _att.AttachmentManager.create(os.path.join(tmp, "nope.bin"))
check("missing file fails honestly", missing.extraction_status == _att.STATUS_FAILED and missing.error)
ctx_fail = _att.AttachmentManager.build_context([missing])
check("failed attachment still named in context", "nope.bin" in ctx_fail and "unavailable" in ctx_fail)

print()
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
print("ALL CHECKS PASSED")
