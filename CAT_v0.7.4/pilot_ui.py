"""v0.7.8.2 UI pilot: full attachment chain through the real CCTApp.

Headless (Textual Pilot), with aicore.stream_ai stubbed so we can capture
exactly what prompt + attachments the model request would receive.
Prints PASS/FAIL for every link in the chain.
"""
import asyncio
import os
import sys
import tempfile

sys.path.insert(0, ".")

from calc_terminal import attachments as _att

fails = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


captured = {"prompt": None, "attachments": None, "history": None, "system": None}


def fake_stream_ai(prompt, system_prompt=None, history=None, config=None,
                   on_failover=None, attachments=None):
    if captured["prompt"] is None:
        captured["prompt"] = prompt
        captured["system"] = system_prompt
        captured["history"] = history
        captured["attachments"] = attachments
    yield "Here is my analysis of the attached file."


from calc_terminal import aicore
aicore.stream_ai = fake_stream_ai

# Provider must be "configured" for the turn to start.
import json

_cfg = {
    "provider": "openai", "model": "gpt-3.5-turbo",
    "api_key": "fake", "base_url": "http://127.0.0.1:1",
}
_cfg_dir = os.path.expanduser("~/.cct")
os.makedirs(_cfg_dir, exist_ok=True)
_cfg_file = os.path.join(_cfg_dir, "config.json")
_old_cfg = None
if os.path.exists(_cfg_file):
    with open(_cfg_file, "r", encoding="utf-8") as f:
        _old_cfg = f.read()
with open(_cfg_file, "w", encoding="utf-8") as f:
    json.dump(_cfg, f)

tmp = tempfile.mkdtemp()
py_path = os.path.join(tmp, "test.py")
with open(py_path, "w", encoding="utf-8") as f:
    f.write("def hello(name):\n    return f'hi {name}'\n")


async def main():
    try:
        from calc_terminal.ui.app import CCTApp, TEXTUAL_AVAILABLE
        from textual.widgets import TextArea
        from calc_terminal.ui.attachments import AttachmentBar

        check("textual available", TEXTUAL_AVAILABLE)

        class StubRepl:
            VERSION = "v0.7.8.2-test"
            def handle(self, raw):
                print("REPL handled:", raw)

        app = CCTApp(StubRepl(), [], {})
        app._current_ai_mode = "notebook"

        async with app.run_test() as pilot:
            app.composer.add_attachment(py_path)
            check("chip created",
                  len(app.query_one(AttachmentBar)._attachments) == 1)

            # Let the async extraction land.
            for _ in range(40):
                await pilot.pause()
                bar = app.query_one(AttachmentBar)
                atts = list(bar._attachments.values())
                if atts and atts[0].extraction_status in (_att.STATUS_READY,
                                                          _att.STATUS_FAILED):
                    break

            att = list(app.query_one(AttachmentBar)._attachments.values())[0]
            check("chip extraction ready",
                  att.extraction_status == _att.STATUS_READY, att.error or "")
            check("chip content present", att.content and "hello" in att.content)

            # Submit the message with the attachment.
            editor = app.query_one("#cct-input", TextArea)
            editor.text = "Analyze this file and explain what it does."
            app.composer.submit()

            # Drive workers to completion.
            for _ in range(80):
                await pilot.pause()
                worker = getattr(app, "_current_worker", None)
                if captured["prompt"] is not None and (worker is None or worker.is_finished):
                    break

            check("stream_ai received prompt", captured["prompt"] is not None)
            if captured["prompt"]:
                check("prompt contains file content", "hello" in captured["prompt"],
                      (captured["prompt"] or "")[:220].replace("\n", "\\n"))
                check("prompt names the file", "test.py" in (captured["prompt"] or ""))
            check("attachments reached the model layer",
                  captured["attachments"] is not None
                  and len(captured["attachments"]) == 1,
                  str(captured["attachments"]))
            if captured["attachments"]:
                a = captured["attachments"][0]
                check("object kind code", a.kind == "code")
                check("object content real", a.content and "hello" in a.content)

            # Mode must be unchanged.
            check("mode unchanged after attach+send",
                  app._current_ai_mode == "notebook", app._current_ai_mode)

    finally:
        if _old_cfg is not None:
            with open(_cfg_file, "w", encoding="utf-8") as f:
                f.write(_old_cfg)
        else:
            try:
                os.remove(_cfg_file)
            except Exception:
                pass


asyncio.run(main())

print()
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
else:
    print("UI PILOT ALL PASSED")
