"""
CAT v0.7.10 — Live Web Preview UPGRADE probe (headless, REAL Chromium).

Covers the v0.7.10 spec gaps on top of the 27-check baseline probe:

  ✓ /preview command opens the live preview end-to-end
  ✓ /preview status reports honest server/preview state
  ✓ Ctrl+Shift+P toggles preview closed (⏻ semantics)…
  ✓ …and back open again
  ✓ /preview reload keeps a running preview healthy
  ✓ /preview stop returns the right pane to CODE
  ✓ Esc exits ⿻ expanded mode from the app level
  ✓ Esc exits ⿻ expanded mode from the focused code editor
  ✓ header menu gained the Live Web Preview entry
  ✓ framework detection: Vite workspace reuses npm dev server wiring
    (detector-level check — spawning npm itself stays out of e2e)

Run: python _probe_v0710_gaps.py
"""

import asyncio
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_results = []


def check(name, ok, detail=""):
    _results.append((name, bool(ok), detail))
    print(("[PASS] " if ok else "[FAIL] ") + name + (f" {detail}" if detail else ""))


async def dismiss_welcome(app, pilot, timeout=6.0):
    from calc_terminal.ui.welcome_modal import WelcomeModal
    t0 = time.time()
    while time.time() - t0 < timeout:
        if not any(isinstance(s, WelcomeModal) for s in app.screen_stack):
            return
        await pilot.press("escape")
        await asyncio.sleep(0.05)


async def wait_for(predicate, timeout=40.0, step=0.25):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if predicate():
                return True
        except Exception:
            pass
        await asyncio.sleep(step)
    return False


def make_site(root):
    with open(os.path.join(root, "index.html"), "w", encoding="utf-8") as f:
        f.write("<!doctype html><html><head>"
                '<link rel="stylesheet" href="style.css">'
                "</head><body><h1 id='h'>CAT Site</h1></body></html>")
    with open(os.path.join(root, "style.css"), "w", encoding="utf-8") as f:
        f.write("body{font-family:sans-serif}")


async def run_slash_command(app, pilot, text):
    """Type a slash command into the REAL composer and press Enter.
    Two Enters on purpose: the first one either accepts the type-ahead
    suggestion ('/preview' -> '/preview ') or submits directly (when a
    subcommand kept the palette closed); the second submits whatever
    landed in the input. A second Enter on an empty input is a no-op,
    so this is safe for both shapes."""
    from calc_terminal.ui.composer import StickyComposer, ComposerInput
    comp = app.query_one(StickyComposer)
    inp = comp.query_one("#cct-input", ComposerInput)
    inp.text = ""
    inp.focus()
    await pilot.pause()
    await pilot.press(*text)
    await pilot.pause()
    await pilot.press("enter")
    await pilot.pause()
    await pilot.press("enter")
    await pilot.pause()
    await asyncio.sleep(0.3)


async def main():
    from calc_terminal import theme
    from calc_terminal.app import App as ReplApp
    from calc_terminal.ui.app import CCTApp
    from calc_terminal.ui.workspace import WorkspaceShell
    from calc_terminal.ui.header import NAV_ITEMS

    theme.set_theme("tokyo-night", persist=False, paint_bg=False)
    root = tempfile.mkdtemp(prefix="cat_gaps_ws_")
    make_site(root)
    layout_backup = None
    app = None
    try:
        from calc_terminal.ui.resizers import LAYOUT_PATH
        if os.path.exists(LAYOUT_PATH):
            with open(LAYOUT_PATH, encoding="utf-8") as f:
                layout_backup = f.read()

        repl = ReplApp()
        app = CCTApp(repl, [], {"solved": 0})
        app._current_ai_mode = "notebook"

        notes = []
        orig_note = app._system_note

        def capturing_note(text, *a, **k):
            notes.append(str(text))
            return orig_note(text, *a, **k)

        app._system_note = capturing_note

        async with app.run_test(size=(150, 42), headless=True) as pilot:
            await dismiss_welcome(app, pilot)
            shell = app.query_one(WorkspaceShell)

            await app._open_folder(root)
            await pilot.pause(); await asyncio.sleep(0.4)
            check("workspace opened", shell.workspace_root == root)

            # ---- header menu integration ---------------------------------
            ids = {item[0] for item in NAV_ITEMS}
            check("header menu has Live Web Preview entry",
                  "toggle_preview" in ids)

            # ---- /preview opens everything -------------------------------
            await run_slash_command(app, pilot, "/preview")
            ok = await wait_for(
                lambda: getattr(app, "_preview_ctrl", None) is not None
                and app._preview_ctrl.preview_state.value == "running",
                timeout=60)
            ctrl = getattr(app, "_preview_ctrl", None)
            check("/preview starts server + browser", bool(ok),
                  str(getattr(ctrl, "preview_state", None)))
            if not ok or ctrl is None:
                return False
            check("/preview flips pane to PREVIEW",
                  await wait_for(
                      lambda: shell.mode.name == "PREVIEW"
                      and shell.preview_panel.display, timeout=15))
            port_ok = (ctrl.server.url.startswith("http://127.0.0.1:")
                       and ctrl.server.port > 0)
            check("auto-assigned port, not hardcoded", port_ok,
                  ctrl.server.url)

            # ---- /preview status ------------------------------------------
            del notes[:]
            await run_slash_command(app, pilot, "/preview status")
            status_text = notes[-1] if notes else ""
            check("/preview status reports running",
                  "Server: running" in status_text
                  and "Preview: running" in status_text,
                  status_text.replace("\n", " | ")[:120])

            # ---- Ctrl+Shift+P toggles CLOSED --------------------------------
            await pilot.press("ctrl+shift+p")
            closed = await wait_for(
                lambda: shell.mode.name == "CODE"
                and not ctrl.engine.available
                and not ctrl.server.running, timeout=25)
            check("Ctrl+Shift+P closes preview (⏻ semantics)", closed)

            # ---- …and back OPEN ----------------------------------------------
            await pilot.press("ctrl+shift+p")
            reopened = await wait_for(
                lambda: ctrl.preview_state.value == "running"
                and shell.mode.name == "PREVIEW", timeout=60)
            check("Ctrl+Shift+P reopens preview", reopened)

            # ---- /preview reload ------------------------------------------------
            await run_slash_command(app, pilot, "/preview reload")
            await asyncio.sleep(1.5)
            check("/preview reload keeps preview running",
                  ctrl.preview_state.value == "running")

            # ---- Esc exits expanded mode (app level) -----------------------------
            app.action_toggle_right_pane_fullscreen()
            await pilot.pause(); await asyncio.sleep(0.35)
            check("⿻ expands preview pane", shell.fullscreen)
            await pilot.press("escape")
            exited = await wait_for(lambda: not shell.fullscreen, timeout=10)
            check("Esc exits expanded preview (app level)", exited)

            # ---- Esc exits expanded mode from the CODE editor ---------------------
            shell.set_right_mode(__import__(
                "calc_terminal.browser", fromlist=["WorkspaceMode"]
            ).WorkspaceMode.CODE)
            await pilot.pause(); await asyncio.sleep(0.3)
            editor = shell.editor
            area = editor.active_text_area()
            if area is None:
                shell.open_file(os.path.join(root, "index.html"))
                await pilot.pause(); await asyncio.sleep(0.4)
                area = editor.active_text_area()
            check("editor tab available for esc test", area is not None)
            if area is not None:
                area.focus()
                await pilot.pause()
                app.action_toggle_right_pane_fullscreen()
                await pilot.pause(); await asyncio.sleep(0.35)
                check("⿻ expands code editor", shell.fullscreen)
                await pilot.press("escape")
                exited_code = await wait_for(
                    lambda: not shell.fullscreen, timeout=10)
                check("Esc exits expanded code editor", exited_code)

            # ---- /preview stop ------------------------------------------------------
            await run_slash_command(app, pilot, "/preview stop")
            stopped = await wait_for(
                lambda: not ctrl.engine.available
                and not ctrl.server.running, timeout=25)
            check("/preview stop stops the stack", stopped)
            check("/preview stop returns pane to CODE",
                  shell.mode.name == "CODE")

            # ---- /preview status after stop -------------------------------------------
            del notes[:]
            await run_slash_command(app, pilot, "/preview status")
            stopped_text = notes[-1] if notes else ""
            check("/preview status reports stopped",
                  "Server: stopped" in stopped_text,
                  stopped_text.replace("\n", " | ")[:120])

            # ---- unknown subcommand is honest -------------------------------------------
            del notes[:]
            await run_slash_command(app, pilot, "/preview bogus")
            usage_text = notes[-1] if notes else ""
            check("/preview bogus prints usage", "Usage:" in usage_text)

            # ---- Vite project detection wiring (no npm spawn) ----------------------------
            from calc_terminal.browser.project_detector import (
                detect_project, VITE, dependencies_installed)
            vite_root = tempfile.mkdtemp(prefix="cat_vite_ws_")
            with open(os.path.join(vite_root, "package.json"), "w",
                      encoding="utf-8") as f:
                f.write('{"scripts": {"dev": "vite"},'
                        '"devDependencies": {"vite": "^5"}}')
            with open(os.path.join(vite_root, "vite.config.js"), "w",
                      encoding="utf-8") as f:
                f.write("export default {}")
            det = detect_project(vite_root)
            check("Vite workspace detected as framework",
                  det.kind == VITE and dependencies_installed(det) is False,
                  f"{det.kind} deps={dependencies_installed(det)}")

        # ---- exit cleanliness ---------------------------------------------------------
        ctrl = getattr(app, "_preview_ctrl", None)
        check("exit leaves nothing running",
              ctrl is None or (not ctrl.server.running
                               and not ctrl.engine.available))
    finally:
        from calc_terminal.ui.resizers import LAYOUT_PATH
        if layout_backup is not None:
            with open(LAYOUT_PATH, "w", encoding="utf-8") as f:
                f.write(layout_backup)
        elif os.path.exists(LAYOUT_PATH):
            os.remove(LAYOUT_PATH)

    passed = sum(1 for _, ok, _ in _results if ok)
    print(f"\n{passed}/{len(_results)} v0.7.10 gap checks passed")
    return passed == len(_results)


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
