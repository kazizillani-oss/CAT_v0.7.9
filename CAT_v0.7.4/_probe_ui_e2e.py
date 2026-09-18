"""Full UI-level end-to-end: attach -> send -> prompt reaches model."""
import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from calc_terminal import aicore

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".cct_ai_config.json")
backup = None
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        backup = f.read()

captured = {}


def fake_stream_ai(prompt, system_prompt=None, history=None, config=None,
                   attachments=None, **kwargs):
    captured["prompt"] = prompt
    captured["attachments"] = attachments
    yield "I read the attached file. The answer constant is 42."


def restore():
    if backup is not None:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(backup)


try:
    aicore.save_config({"provider": "deepseek", "model": "deepseek-chat",
                        "api_style": "openai", "api_key": "test",
                        "base_url": "http://localhost"})
    aicore.stream_ai = fake_stream_ai

    fd, path = tempfile.mkstemp(suffix=".py")
    os.write(fd, b"# config\nANSWER = 42\n")
    os.close(fd)

    async def main():
        from calc_terminal.ui.app import CCTApp
        app = CCTApp(repl=None, history=[], stats={})
        # This probe exercises the ATTACH -> STREAM pipeline. Force
        # Notebook mode so the router can't divert into the agent loop
        # (which calls query_ai, not the patched stream_ai) — otherwise
        # the result depends on whatever AI mode the machine has saved.
        app._current_ai_mode = "notebook"
        async with app.run_test(size=(110, 36), headless=True) as pilot:
            for _ in range(8):
                await pilot.pause()
                await asyncio.sleep(0.15)
            composer = app.query_one("#cct-composer")
            bar = app.query_one("#cct-chips")
            composer.add_attachment(path)
            print("attachment added, chip_ids =", list(bar._attachments))
            chip_id = list(bar._attachments)[0]
            for _ in range(25):
                await pilot.pause()
                await asyncio.sleep(0.2)
            from calc_terminal.ui.attachments import Chip
            chips = [c for c in bar.children if isinstance(c, Chip)]
            label = chips[0]._label_text if chips else ""
            print("chip label:", label.encode("ascii", "replace").decode())
            from calc_terminal import attachments as _att
            att = bar._attachments[chip_id]
            print("chip status:", att.extraction_status, "kind:", att.kind)

            editor = composer.query_one("ComposerInput")
            editor.focus()
            await pilot.press(*"summarize the attached file")
            await pilot.press("enter")
            for _ in range(40):
                await pilot.pause()
                await asyncio.sleep(0.2)
            print("\ncaptured prompt (first 400 chars):")
            print((captured.get("prompt") or "(none)")[:400])
            print("\nattachments passed to model:", len(captured.get("attachments") or []))
            assert captured.get("prompt"), "no prompt captured — pipeline never reached the model"
            assert "ANSWER = 42" in captured["prompt"], "file content NOT in model prompt"
            atts = captured.get("attachments") or []
            assert len(atts) == 1 and getattr(atts[0], "kind", None) == "code", \
                "Attachment object did not ride along"
            # weak model warning on the chip
            assert "can't see this image" not in label, "text chip must not warn"
            # Turn recorded attachments
            turns = app.session.turns
            user_turn = turns[-2] if len(turns) >= 2 else turns[0]
            print("user turn attachments recorded:", len(user_turn.attachments or []))
            assert user_turn.attachments, "Turn.attachments not recorded"
            print("\nUI END-TO-END PIPELINE PASSED")
            os.remove(path)

    asyncio.run(main())
finally:
    restore()
