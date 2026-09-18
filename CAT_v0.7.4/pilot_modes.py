"""v0.7.8.2: agent/build mode attachment flow + mode-stability matrix."""
import asyncio
import json
import os
import sys
import tempfile

sys.path.insert(0, ".")

fails = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


captured = {}


def fake_stream_ai(prompt, system_prompt=None, history=None, config=None,
                   on_failover=None, attachments=None):
    captured["stream_prompt"] = prompt
    captured["stream_attachments"] = attachments
    yield "ok"


def fake_run_agent(prompt, mode="agent", permission_callback=None, on_step=None,
                   should_cancel=None):
    captured["agent_prompt"] = prompt
    captured["agent_mode"] = mode
    captured["agent_attachments"] = type("A", (), {"attachments": None})()
    return "done", [], {}


from calc_terminal import aicore, agent as cct_agent
aicore.stream_ai = fake_stream_ai
cct_agent.run_agent = fake_run_agent

_cfg = {"provider": "openai", "model": "gpt-4o", "api_key": "fake",
        "base_url": "http://127.0.0.1:1"}
_cfg_file = os.path.join(os.path.expanduser("~"), ".cct_ai_config.json")
_old = None
if os.path.exists(_cfg_file):
    with open(_cfg_file, "r", encoding="utf-8") as f:
        _old = f.read()
with open(_cfg_file, "w", encoding="utf-8") as f:
    json.dump(_cfg, f)

tmp = tempfile.mkdtemp()
py_path = os.path.join(tmp, "test.py")
with open(py_path, "w", encoding="utf-8") as f:
    f.write("def hello(name):\n    return f'hi {name}'\n")


async def run_mode_case(app, pilot, mode, expected_loop):
    from textual.widgets import TextArea
    from calc_terminal.ui.attachments import AttachmentBar
    app._set_ai_mode(mode)
    await pilot.pause()
    app.composer.add_attachment(py_path)
    for _ in range(30):
        await pilot.pause()
        bar = app.query_one(AttachmentBar)
        atts = list(bar._attachments.values())
        if atts and atts[0].extraction_status in ("ready", "failed"):
            break
    att = list(app.query_one(AttachmentBar)._attachments.values())[0]
    check(f"[{mode}] attachment extraction ready", att.extraction_status == "ready", att.error or "")
    editor = app.query_one("#cct-input", TextArea)
    editor.text = "Analyze this file."
    app.composer.submit()
    for _ in range(60):
        await pilot.pause()
        worker = getattr(app, "_current_worker", None)
        if captured.get("stream_prompt") or captured.get("agent_prompt"):
            if worker is None or worker.is_finished:
                break
    # mode must be unchanged
    check(f"[{mode}] mode unchanged after send", app._current_ai_mode == mode,
          app._current_ai_mode)
    # mode must be unchanged after typing
    editor.text = "hello there"
    await pilot.pause()
    check(f"[{mode}] mode unchanged after typing", app._current_ai_mode == mode)
    editor.text = ""
    return att


async def main():
    from calc_terminal.ui.app import CCTApp
    from calc_terminal.ui.attachments import AttachmentBar

    class StubRepl:
        VERSION = "v0.7.8.2-test"
        def handle(self, raw):
            pass

    try:
        app = CCTApp(StubRepl(), [], {})
        async with app.run_test() as pilot:
            # Mode stability matrix for every mode.
            for mode in ("notebook", "research", "plan", "build", "debugger", "agent"):
                captured.clear()
                await run_mode_case(app, pilot, mode, None)
                await pilot.pause()
                # clean the composer bar for the next case
                bar = app.query_one(AttachmentBar)
                bar._attachments = {}
                for child in list(bar.children):
                    child.remove()

            # Tool-loop paths (agent / build) route through run_agent with
            # the real attachment objects registered.
            app._set_ai_mode("agent")
            await pilot.pause()
            captured.clear()
            app.composer.add_attachment(py_path)
            for _ in range(30):
                await pilot.pause()
                bar = app.query_one(AttachmentBar)
                atts = list(bar._attachments.values())
                if atts and atts[0].extraction_status in ("ready", "failed"):
                    break
            from textual.widgets import TextArea
            editor = app.query_one("#cct-input", TextArea)
            editor.text = "Analyze this file."
            app.composer.submit()
            for _ in range(60):
                await pilot.pause()
                worker = getattr(app, "_current_worker", None)
                if captured.get("agent_prompt"):
                    if worker is None or worker.is_finished:
                        break
            check("agent loop prompt contains file content",
                  captured.get("agent_prompt") and "hello" in captured["agent_prompt"])
            check("agent attachments registered",
                  len(cct_agent.get_attachments()) == 1)
            check("agent mode not mutated", app._current_ai_mode == "agent")
    finally:
        if _old is not None:
            with open(_cfg_file, "w", encoding="utf-8") as f:
                f.write(_old)
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
print("MODE MATRIX ALL PASSED")
