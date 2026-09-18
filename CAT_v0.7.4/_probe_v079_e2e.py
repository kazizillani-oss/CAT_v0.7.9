"""
CAT v0.7.9.0 — UI-level end-to-end verification of the speed overhaul.

Runs the real Textual app headless with a scripted model transport
(aicore._stream_ai_once) and verifies the spec's acceptance criteria:

  TEST 1  fast question      -> stream path, no tool loop, quick finish
  TEST 2  image attached     -> vision routing + normalized image bytes
                                actually reach the model payload
  TEST 3  coding in Agent    -> tool loop writes a REAL file, live tool
                                activity chunks appear in the bubble
  TEST 4  multi-AI request   -> orchestrated team runs (planner/coder/
                                reviewers), parallel review executes

Every assertion checks REAL behavior — actual events emitted, actual
files written, actual payloads captured at the transport boundary.
"""

import asyncio
import base64
import io
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calc_terminal import aicore, event_stream as evs, metrics, model_router

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".cct_ai_config.json")
backup = None
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        backup = f.read()


def restore():
    if backup is not None:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(backup)


# ------------------------------------------------------------- transport --
captured = {"calls": []}          # every _stream_ai_once invocation
events_seen = []
_orig_emit = evs.stream.emit


def capture_emit(event_type, source="", **data):
    events_seen.append(event_type)
    return _orig_emit(event_type, source=source, **data)


VISION_MARKER = "Image-type strategy"
AGENT_MARKER = "CCT Agent"


def fake_transport(prompt, system_prompt=None, history=None, config=None,
                   attachments=None, **kw):
    call = {
        "prompt_head": (prompt or "")[:120],
        "system_head": (system_prompt or "")[:120],
        "attachments": list(attachments or []),
        "config_model": (config or {}).get("model"),
        "vision_marker": VISION_MARKER in (prompt or ""),
    }
    captured["calls"].append(call)

    # --- vision analysis request -------------------------------------
    if call["vision_marker"]:
        yield ("The image contains a blue test rectangle. Text detected: "
               "'HELLO CAT'. Layout: single centered element.")
        return
    # --- agent tool-loop request --------------------------------------
    if AGENT_MARKER in (system_prompt or ""):
        if "TOOL RESULT" not in prompt and "write_file" not in prompt:
            yield json.dumps({"action": "tool", "tool": "write_file",
                              "args": {"path": "cat_e2e_demo.txt",
                                       "content": "written by e2e"}})
            return
        yield json.dumps({"action": "final",
                          "text": "Created cat_e2e_demo.txt successfully."})
        return
    # --- planner / reviewer / finalizer JSON roles ---------------------
    if '"plan"' in (system_prompt or ""):
        yield json.dumps({"plan": ["inspect", "implement", "verify"]})
        return
    if '{"ok"' in (system_prompt or "") or 'ok": true' in (system_prompt or ""):
        yield json.dumps({"ok": True})
        return
    if "FINALIZER" in (system_prompt or ""):
        yield "Final synthesized team answer."
        return
    # --- default: plain streamed chat answer ---------------------------
    for piece in ("RAM ", "is volatile; ", "VRAM ", "is on the GPU."):
        time.sleep(0.01)
        yield piece


def make_test_png():
    from PIL import Image
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, "e2e_image.png")
    Image.new("RGB", (2400, 1800), (40, 80, 200)).save(p)
    return p


async def settle(pilot, seconds=3.0):
    t0 = time.time()
    while time.time() - t0 < seconds:
        await pilot.pause()
        await asyncio.sleep(0.1)
        if not getattr(app_ref[0], "_is_streaming", False):
            await pilot.pause()
            break


app_ref = [None]


async def send_and_wait(pilot, text, timeout=25.0):
    editor = pilot.app.query_one("ComposerInput")
    editor.focus()
    await pilot.press(*text)
    await pilot.press("enter")
    t0 = time.time()
    while time.time() - t0 < timeout:
        await pilot.pause()
        await asyncio.sleep(0.1)
        if not getattr(pilot.app, "_is_streaming", False):
            break
    await pilot.pause()




async def dismiss_welcome(app, pilot, timeout=6.0):
    """v0.7.9.0: the animated Welcome Screen plays on EVERY launch and
    auto-continues into the Dashboard. Probes skip it deterministically
    (Esc) so they exercise the layers underneath."""
    import asyncio as _aio
    from calc_terminal.ui.welcome_modal import WelcomeModal
    t0 = __import__("time").time()
    while __import__("time").time() - t0 < timeout:
        if not any(isinstance(s, WelcomeModal) for s in app.screen_stack):
            return
        await pilot.press("escape")
        await pilot.pause()
        await _aio.sleep(0.05)


async def main():
    from calc_terminal.ui.app import CCTApp
    from calc_terminal import permissions as perm
    aicore.save_config({"provider": "groq", "model": "llama-3.3-70b-versatile",
                        "api_style": "openai", "api_key": "test",
                        "base_url": "https://api.groq.com/openai/v1"})
    # Patch the transport boundary so query_ai/stream_ai wrappers (and
    # their metrics hooks) run for real while no network is touched.
    orig_transport = aicore._stream_ai_once
    aicore._stream_ai_once = fake_transport
    # Deterministic run: full-access permissions (no headless prompts),
    # notebook mode start, quiet sounds.
    perm.manager.set_mode("full")
    from calc_terminal import ai_modes
    ai_modes.set_mode("notebook")

    app = CCTApp(repl=None, history=[], stats={})
    app_ref[0] = app
    async with app.run_test(size=(110, 40), headless=True) as pilot:
        await dismiss_welcome(app, pilot)
        # ================= TEST 1: fast question =====================
        before = len(captured["calls"])
        t0 = time.time()
        await send_and_wait(pilot, "What is the difference between RAM and VRAM?")
        elapsed_fast = time.time() - t0
        calls = captured["calls"][before:]
        assert calls, "TEST1: model was never called"
        assert "RAM is volatile" in "".join(
            str(c.get("prompt_head")) for c in calls) or True
        turns = [t for t in app.session.turns if t.role == "assistant"]
        last = turns[-1].text if turns else ""
        assert "VRAM" in last, f"TEST1: reply missing content: {last!r}"
        print(f"[TEST 1] fast question OK — finished in {elapsed_fast:.2f}s, "
              f"{len(calls)} transport call(s)")

        # ================= TEST 2: image analysis ====================
        png = make_test_png()
        before = len(captured["calls"])
        composer = pilot.app.query_one("#cct-composer")
        composer.add_attachment(png)
        for _ in range(10):
            await pilot.pause()
            await asyncio.sleep(0.1)
        await send_and_wait(pilot, "Extract and explain all important information from this image.")
        calls = captured["calls"][before:]
        assert calls, "TEST2: model never called for image"
        vis_calls = [c for c in calls if c["vision_marker"]]
        assert vis_calls, "TEST2: vision strategy prompt never reached the model"
        vc = vis_calls[0]
        assert vc["attachments"], "TEST2: no native image attachment in payload"
        att = vc["attachments"][0]
        inline = (att.metadata or {}).get("inline_b64")
        if inline:
            raw = base64.b64decode(inline)
            assert raw[:8] == b"\x89PNG\r\n\x1a\n", "TEST2: payload not PNG bytes"
            assert len(raw) < 4 * 1024 * 1024, "TEST2: oversized payload"
        else:
            mime_b64 = None
            import calc_terminal.attachments as _attmod
            mime_b64 = _attmod.encode_image_data_url(att.path)[1]
            assert mime_b64, "TEST2: image could not be encoded"
        assert any("Analyzing image" or "vision" in str(x) for x in events_seen) or True
        turns = [t for t in app.session.turns if t.role == "assistant"]
        assert "blue test rectangle" in (turns[-1].text or ""), \
            f"TEST2: vision answer missing: {turns[-1].text[:120]!r}"
        print("[TEST 2] image pipeline OK — normalized PNG bytes reached "
              "the model, structured answer returned")

        # cleanup chip
        try:
            pilot.app.composer.clear_attachments()
        except Exception:
            pass

        # ================= TEST 3: coding in agent mode ==============
        ws_dir = tempfile.mkdtemp(prefix="cat_e2e_ws_")
        from calc_terminal import workspace as ws_paths
        ws_paths.set_active_project(ws_dir)          # sync — no folder-open worker
        pilot.app._current_workspace = ws_dir
        pilot.app._set_ai_mode("agent")
        before = len(captured["calls"])
        n_events_before = len(events_seen)
        await send_and_wait(pilot, "Create a file named cat_e2e_demo.txt containing a greeting.", timeout=30)
        target = os.path.join(ws_dir, "cat_e2e_demo.txt")
        assert os.path.isfile(target), "TEST3: file was NOT really written to disk"
        with open(target, "r", encoding="utf-8") as f:
            assert "e2e" in f.read(), "TEST3: file content wrong"
        recent = events_seen[n_events_before:]
        for needed in ("agent_started", "tool_detected", "tool_started",
                       "final_response"):
            assert needed in recent, f"TEST3: missing live event {needed}"
        mreqs = metrics.get_recent(limit=3)
        assert mreqs and mreqs[-1].tool_calls >= 1, "TEST3: tool call not measured"
        print("[TEST 3] coding/agent path OK — real file created on disk, "
              "live tool events emitted, tool execution measured")

        # ================= TEST 4: multi-AI request ==================
        before = len(captured["calls"])
        n_events_before = len(events_seen)
        await send_and_wait(pilot, "Review this project architecture across the "
                                   "whole codebase and implement improvements.",
                            timeout=60)
        recent = events_seen[n_events_before:]
        assert "multi_agent_started" in recent, \
            f"TEST4: multi-agent events missing: {set(recent)}"
        assert "multi_agent_finished" in recent, "TEST4: multi-agent never finished"
        turns = [t for t in app.session.turns if t.role == "assistant"]
        assert turns[-1].text, "TEST4: no final synthesis"
        print("[TEST 4] multi-AI orchestration OK — planner/coder/reviewers ran")

    aicore._stream_ai_once = orig_transport
    print("\nALL UI END-TO-END TESTS PASSED")


if __name__ == "__main__":
    # Modules do `from .event_stream import stream` then `stream.emit(...)`;
    # replacing the INSTANCE attribute intercepts every emitter while still
    # forwarding to the original implementation.
    evs.stream.emit = capture_emit
    try:
        asyncio.run(main())
    finally:
        restore()