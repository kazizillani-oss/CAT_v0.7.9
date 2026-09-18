"""Verify the weak-model image warning on attachment chips (headless)."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from calc_terminal import aicore
from calc_terminal import attachments as _att

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".cct_ai_config.json")
backup = None
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        backup = f.read()


def set_cfg(provider, model, style):
    aicore.save_config({"provider": provider, "model": model, "api_style": style,
                        "api_key": "test", "base_url": "http://localhost"})


def make_image():
    from PIL import Image
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    Image.new("RGB", (20, 12), color=(10, 120, 200)).save(path)
    return path


def restore():
    if backup is not None:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(backup)


try:
    from calc_terminal.ui import attachments as ui_att
    img = make_image()
    att = _att.AttachmentManager.create(img)
    assert att.kind == "image" and att.extraction_status == _att.STATUS_READY

    print("=== weak model (deepseek) ===")
    set_cfg("deepseek", "deepseek-chat", "openai")
    warn = ui_att._vision_warning(att)
    print(f"   warning = {warn!r}")
    assert warn is not None, "weak model must warn on image chips"
    label = ui_att._chip_label(att)
    needle = "can't see this image"
    print(f"   chip label contains warning: {needle in label}")
    assert needle in label

    print("=== vision model (gpt-4o) ===")
    set_cfg("openai", "gpt-4o", "openai")
    warn2 = ui_att._vision_warning(att)
    print(f"   warning = {warn2!r}")
    assert warn2 is None, "vision model must not warn"

    print("=== unconfigured (no provider) ===")
    set_cfg("", "", "openai")
    warn3 = ui_att._vision_warning(att)
    print(f"   warning = {warn3!r}")
    assert warn3 is None, "no provider = no claim either way"

    print("=== text file never warns ===")
    fd, tp = tempfile.mkstemp(suffix=".md")
    os.write(fd, b"hello world")
    os.close(fd)
    tatt = _att.AttachmentManager.create(tp)
    set_cfg("deepseek", "deepseek-chat", "openai")
    assert ui_att._vision_warning(tatt) is None, "text files must never warn"
    print("   PASS")

    print("\nWEAK-MODEL WARNING TESTS PASSED")
    os.remove(img)
    os.remove(tp)
finally:
    restore()
