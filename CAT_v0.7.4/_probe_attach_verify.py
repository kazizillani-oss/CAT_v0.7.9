"""End-to-end attachment pipeline verification (headless, offline)."""
import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from calc_terminal import attachments as _att


def make_text_file():
    fd, path = tempfile.mkstemp(suffix=".py")
    os.write(fd, b"# project config\nANSWER = 42\n\ndef greet(name):\n    return f'hello {name}'\n")
    os.close(fd)
    return path


def make_image_file():
    try:
        from PIL import Image
        fd, path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        Image.new("RGB", (24, 16), color=(200, 30, 30)).save(path)
        return path
    except Exception:
        return None


def main():
    text_path = make_text_file()
    img_path = make_image_file()

    print("=== 1. text file: validate -> read -> detect -> extract ===")
    att = _att.AttachmentManager.create(text_path)
    print(f"   kind={att.kind} status={att.extraction_status} error={att.error}")
    assert att.kind == "code" and att.extraction_status == _att.STATUS_READY, "text extraction failed"
    ctx = _att.AttachmentManager.build_context([att])
    print(f"   context block ({len(ctx)} chars) contains file content: {'ANSWER = 42' in ctx}")
    assert "ANSWER = 42" in ctx, "file content did NOT reach the model context"
    print("   PASS: text file content reaches the model context")

    print("\n=== 2. weak model (no vision): image falls back to text, no payload ===")
    from calc_terminal import aicore
    cfg_weak = {"provider": "deepseek", "model": "deepseek-chat", "api_style": "openai"}
    caps = _att.provider_capabilities(cfg_weak)
    print(f"   capabilities = {caps}")
    assert caps["vision"] is False, "weak model must not claim vision"

    if img_path:
        img_att = _att.AttachmentManager.create(img_path)
        print(f"   image kind={img_att.kind} status={img_att.extraction_status}")
        assert img_att.kind == "image", "PNG must be detected as image"
        messages = aicore._openai_messages("sys", [], "what is this?", attachments=[img_att], vision=False)
        content = messages[-1]["content"]
        parts = content if isinstance(content, list) else [content]
        has_image_part = any(isinstance(p, dict) and p.get("type") == "image_url" for p in parts)
        print(f"   weak model message: image part present? {has_image_part}")
        assert not has_image_part, "weak model must NOT get a native image payload"
        ctx_i = _att.AttachmentManager.build_context([img_att])
        print(f"   metadata fallback present in context: {'Attached image' in ctx_i}")
        assert "Attached image" in ctx_i
        print("   PASS: weak model gets honest metadata text, never a silent image")
    else:
        print("   (PIL unavailable - skipping image tests)")

    print("\n=== 3. vision model: image travels as a native payload ===")
    cfg_v = {"provider": "openai", "model": "gpt-4o", "api_style": "openai"}
    caps_v = _att.provider_capabilities(cfg_v)
    print(f"   capabilities = {caps_v}")
    assert caps_v["vision"] is True, "gpt-4o must be vision-capable"
    if img_path:
        messages = aicore._openai_messages("sys", [], "what color?", attachments=[img_att], vision=True)
        content = messages[-1]["content"]
        parts = content if isinstance(content, list) else [content]
        has_image_part = any(isinstance(p, dict) and p.get("type") == "image_url" for p in parts)
        print(f"   vision model message: image part present? {has_image_part}")
        assert has_image_part, "vision model must receive the image natively"
        print("   PASS: image reaches the vision model as a native payload")

    print("\n=== 4. _prepare_attachments returns the right vision flag ===")
    v_weak = aicore._prepare_attachments([img_att], cfg_weak)
    v_strong = aicore._prepare_attachments([img_att], cfg_v)
    print(f"   weak={v_weak} vision={v_strong}")
    assert v_weak is False and v_strong is True
    print("   PASS")

    print("\n=== 5. unknown model defaults to safe no-vision ===")
    cfg_u = {"provider": "openai", "model": "mystery-model-9000", "api_style": "openai"}
    caps_u = _att.provider_capabilities(cfg_u)
    print(f"   capabilities = {caps_u}")
    assert caps_u["vision"] is False, "unknown models must default to text fallback"
    print("   PASS: unknown model safely degrades")

    print("\nALL PIPELINE CHECKS PASSED")
    for p in (text_path, img_path):
        if p:
            try:
                os.remove(p)
            except Exception:
                pass


if __name__ == "__main__":
    main()
