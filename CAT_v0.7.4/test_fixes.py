"""v0.7.8.2: provider-native image payload shapes + mode persistence."""
import os
import sys
import tempfile

sys.path.insert(0, ".")

fails = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


tmp = tempfile.mkdtemp()
png_path = os.path.join(tmp, "img.png")
from PIL import Image
Image.new("RGB", (8, 8), (0, 200, 0)).save(png_path)

from calc_terminal import attachments as _att
img = _att.AttachmentManager.create(png_path)
check("image ready", img.extraction_status == _att.STATUS_READY, img.error or "")

from calc_terminal.aicore import _user_content, _openai_messages, _anthropic_messages, _gemini_contents

# OpenAI shape
uc = _user_content("what is this", [img], vision=True, api_style="openai")
check("openai: parts list", isinstance(uc, list) and len(uc) == 2)
check("openai: text part", uc[0] == {"type": "text", "text": "what is this"})
check("openai: image_url part",
      uc[1]["type"] == "image_url" and uc[1]["image_url"]["url"].startswith("data:image/png;base64,"))

# Anthropic shape
uc = _user_content("what is this", [img], vision=True, api_style="anthropic")
check("anthropic: parts list", isinstance(uc, list) and len(uc) == 2)
check("anthropic: image source shape",
      uc[1] == {"type": "image",
                "source": {"type": "base64", "media_type": "image/png",
                           "data": uc[1]["source"]["data"]}})
check("anthropic: base64 data present", len(uc[1]["source"]["data"]) > 0)

# Gemini shape
uc = _user_content("what is this", [img], vision=True, api_style="gemini")
check("gemini: parts list", isinstance(uc, list) and len(uc) == 2)
check("gemini: inline_data shape",
      uc[1] == {"inline_data": {"mime_type": "image/png", "data": uc[1]["inline_data"]["data"]}})

# Full builders carry provider-correct shapes end to end.
om = _openai_messages("sys", [], "hi", [img], vision=True)
check("openai messages image_url",
      om[-1]["content"][1]["type"] == "image_url")
am = _anthropic_messages([], "hi", [img], vision=True)
check("anthropic messages image source",
      am[-1]["content"][1]["type"] == "image")
gm = _gemini_contents([], "hi", [img], vision=True)
check("gemini messages inline_data",
      "inline_data" in gm[-1]["parts"][1])

# non-vision: plain string prompt preserved for every style
for style in ("openai", "anthropic", "gemini"):
    uc = _user_content("plain", [img], vision=False, api_style=style)
    check(f"{style}: non-vision plain string", uc == "plain")

# ---- mode persistence -------------------------------------------------
import json as _json
from calc_terminal import config as _cfg
_cfg_dir = os.path.expanduser("~")
_cfg_file = _cfg.CONFIG_PATH
_old = None
if os.path.exists(_cfg_file):
    with open(_cfg_file, "r", encoding="utf-8") as f:
        _old = f.read()
try:
    with open(_cfg_file, "w", encoding="utf-8") as f:
        _json.dump({"default_ai_mode": "build"}, f)
    _cfg._cached = None  # force reload
    from calc_terminal import ai_modes
    _cfg._cached = None
    ai_modes._restore_saved_mode()
    check("saved mode restored on import", ai_modes.current_mode() == "build",
        ai_modes.current_mode())
    # switching persists
    ai_modes.set_mode("agent")
    with open(_cfg_file, "r", encoding="utf-8") as f:
        saved = _json.load(f)
    check("mode switch persisted", saved.get("default_ai_mode") == "agent",
          str(saved.get("default_ai_mode")))
finally:
    if _old is not None:
        with open(_cfg_file, "w", encoding="utf-8") as f:
            f.write(_old)
    else:
        try:
            os.remove(_cfg_file)
        except Exception:
            pass
    _cfg._cached = None

print()
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
print("FIX TESTS ALL PASSED")
