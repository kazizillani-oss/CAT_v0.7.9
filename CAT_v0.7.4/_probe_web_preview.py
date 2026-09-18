"""
CAT v0.7.10 — LIVE WEB PREVIEW end-to-end probe (headless, REAL Chromium).

Verifies the complete spec-28 checklist against the actual stack:
real LiveServer + real Playwright Chromium + real watcher + real UI.

  ✓ open index.html            ✓ ▷ starts server+browser
  ✓ website renders (JS ran)   ✓ CSS hot-updates
  ✓ images load                ✓ rapid edits debounced
  ✓ URL field navigates        ✓ reload works
  ✓ back works                 ✓ ⏻ closes preview -> editor returns
  ✓ ⿻ fullscreen + restore    ✓ right pane resizes + persists
  ✓ closing all tabs keeps preview alive
  ✓ errors don't crash CAT     ✓ clean shutdown

Run: python _probe_web_preview.py
"""

import asyncio
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys, "__stdout__") and hasattr(sys.__stdout__, "reconfigure"):
            sys.__stdout__.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_results = []


def check(name, ok, detail=""):
    _results.append((name, bool(ok), detail))
    status = "[PASS] " if ok else "[FAIL] "
    msg = status + name + (f" {detail}" if detail else "")
    try:
        print(msg)
    except Exception:
        print(msg.encode("ascii", errors="replace").decode("ascii"))


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
        f.write(
            "<!doctype html><html><head>"
            '<link rel="stylesheet" href="style.css">'
            "</head><body><h1 id='h'>CAT Site</h1>"
            "<p id='js-check'>waiting</p>"
            '<img id="im" src="dot.png" alt="dot">'
            "<script>document.getElementById('js-check').textContent="
            "'javascript-ran';</script></body></html>")
    with open(os.path.join(root, "style.css"), "w", encoding="utf-8") as f:
        f.write("body{font-family:sans-serif} h1{color:purple}")
    # 1x1 transparent PNG
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d494844520000000100000001080600000"
        "01f15c4890000000d49444154789c626001000000ffff030000060005"
        "57bfabd40000000049454e44ae426082")
    with open(os.path.join(root, "dot.png"), "wb") as f:
        f.write(png)


def page_texts(ctrl):
    """Visible innerText lines from the LIVE Chromium page."""
    try:
        raw = ctrl.engine.evaluate(
            "(() => Array.from(document.body.innerText.split('\\n')"
            ".filter(s => s.trim())).slice(0, 40))()")
        return [str(x) for x in (raw or [])]
    except Exception:
        return []


def images_ok(ctrl):
    try:
        counts = ctrl.engine.evaluate(
            "(() => ({ok: document.images.length > 0 && "
            "Array.from(document.images).every(i => i.complete && "
            "i.naturalWidth > 0)}))()")
        return bool(counts and counts.get("ok"))
    except Exception:
        return False


async def main():
    from calc_terminal import theme
    from calc_terminal.app import App as ReplApp
    from calc_terminal.ui.app import CCTApp
    from calc_terminal.ui.workspace import WorkspaceShell
    from calc_terminal.ui.composer import StickyComposer
    from calc_terminal.browser import WorkspaceMode
    from textual.widgets import Static

    theme.set_theme("tokyo-night", persist=False, paint_bg=False)
    root = tempfile.mkdtemp(prefix="cat_web_ws_")
    make_site(root)
    layout_backup = None
    app = None
    try:
        from calc_terminal.ui.resizers import LAYOUT_PATH, load_layout
        if os.path.exists(LAYOUT_PATH):
            with open(LAYOUT_PATH, encoding="utf-8") as f:
                layout_backup = f.read()

        repl = ReplApp()
        app = CCTApp(repl, [], {"solved": 0})
        app._current_ai_mode = "notebook"
        async with app.run_test(size=(150, 42), headless=True) as pilot:
            await dismiss_welcome(app, pilot)
            shell = app.query_one(WorkspaceShell)
            editor = shell.editor
            panel = shell.preview_panel

            await app._open_folder(root)
            await pilot.pause(); await asyncio.sleep(0.4)
            check("workspace opened", shell.workspace_root == root)

            # ---- open index.html in a tab ------------------------------
            shell.open_file(os.path.join(root, "index.html"))
            await pilot.pause(); await asyncio.sleep(0.4)
            check("index.html opens in a tab", len(editor._open_paths) == 1)
            run_visible = False
            try:
                pill = editor.query_one("#cct-tb-run", Static)
                run_visible = bool(pill.display)
            except Exception:
                pass
            check("▷ pill visible for HTML tab", run_visible)

            # ---- click ▷ -------------------------------------------------
            await pilot.click("#cct-tb-run")
            ok = await wait_for(
                lambda: app._preview_ctrl is not None
                and app._preview_ctrl.preview_state.value == "running",
                timeout=60)
            ctrl = getattr(app, "_preview_ctrl", None)
            check("▷ starts server + browser", bool(ok),
                  str(getattr(ctrl, "preview_state", None)))
            if not ok or ctrl is None:
                return False
            await wait_for(lambda: editor.display, timeout=10)
            check("right pane remains in CODE mode (editor active for user)",
                  shell.mode is WorkspaceMode.CODE and editor.display)
            check("server on localhost auto-port",
                  ctrl.server.url.startswith("http://127.0.0.1:")
                  and ctrl.server.port not in (80, 3000, 5173),
                  ctrl.server.url)

            # ---- the website really renders --------------------------------
            got_js = await wait_for(
                lambda: any("javascript-ran" in t for t in page_texts(ctrl)),
                timeout=30)
            check("JavaScript executes in Chromium", got_js,
                  str(page_texts(ctrl)[:3]))
            check("images load", await wait_for(
                lambda: images_ok(ctrl), timeout=20))
            check("HTML content rendered", await wait_for(
                lambda: any("CAT Site" in t for t in page_texts(ctrl)),
                timeout=15))

            # ---- editor session survived the switch ------------------------
            check("editor state intact under preview",
                  len(editor._open_paths) == 1
                  and editor.active_text_area() is not None)

            # ---- AI css edit → hot update -----------------------------------
            app._drain_preview_events()
            with open(os.path.join(root, "style.css"), "a",
                      encoding="utf-8") as f:
                f.write("\nh1{letter-spacing:3px}")
            ctrl.notify_ai_wrote(os.path.join(root, "style.css"))
            check("AI css edit hot-updates preview", await wait_for(
                lambda: any("CSS updated" in t
                            for t in panel._activity_lines), timeout=15))

            # ---- rapid writes are debounced into few reloads --------------
            reloads_before = getattr(ctrl.server, "_reload_count", 0)
            for i in range(12):
                with open(os.path.join(root, "index.html"), "a",
                          encoding="utf-8") as f:
                    f.write(f"\n<!-- burst {i} -->")
                ctrl.notify_ai_wrote(os.path.join(root, "index.html"))
                await asyncio.sleep(0.01)
            await asyncio.sleep(1.5)
            burst_reloads = (getattr(ctrl.server, "_reload_count", 0)
                             - reloads_before)
            check("rapid edits coalesce (≤4 engine reloads / 12 writes)",
                  burst_reloads <= 4, f"reloads={burst_reloads}")

            # ---- URL bar navigation + error isolation ----------------------
            app.preview_navigate_user("missing-page.html")
            check("bad URL shows isolated error", await wait_for(
                lambda: ctrl.preview_state.value == "error", timeout=25))
            check("CAT alive after preview error",
                  app.is_running and ctrl.engine.available)
            app.action_preview_back()
            await wait_for(
                lambda: ctrl.preview_state.value == "running", timeout=25)
            check("← back returns to working page",
                  ctrl.preview_state.value == "running")

            # ---- ⟳ reload ----------------------------------------------------
            app.action_preview_reload()
            await asyncio.sleep(1.2)
            check("⟳ keeps preview running",
                  ctrl.preview_state.value == "running")

            # ---- ⿻ fullscreen --------------------------------------------------
            width_before = shell.right_pane.size.width or 0
            app.action_toggle_right_pane_fullscreen()
            await pilot.pause(); await asyncio.sleep(0.35)
            check("⿻ expands right pane fullscreen",
                  shell.fullscreen and shell.right_pane.size.width >= 140)
            app.action_toggle_right_pane_fullscreen()
            await pilot.pause(); await asyncio.sleep(0.45)
            restored = abs((shell.right_pane.size.width or 0) - width_before) <= 2
            check("⿻ restores exact pane config", restored,
                  f"{width_before} -> {shell.right_pane.size.width}")

            # ---- right-pane resize + persistence -------------------------------
            target_width = max(26, width_before - 10)
            shell.set_right_width(target_width)
            shell.persist_rightpane_width()
            await pilot.pause(); await asyncio.sleep(0.2)
            check("right pane resizable",
                  abs((shell.right_pane.size.width or 0) - target_width) <= 2,
                  str(shell.right_pane.size.width))
            check("pane width persisted",
                  load_layout().get("rightpane_width") == target_width)

            # ---- closing ALL editor tabs keeps preview alive ---------------------
            editor.close_active()
            await pilot.pause(); await asyncio.sleep(0.3)
            check("all tabs closed -> empty editor",
                  len(editor._open_paths) == 0)
            check("closing tabs does NOT kill preview",
                  ctrl.preview_state.value == "running")

            # ---- ⏻ close ----------------------------------------------------------
            app.action_preview_close()
            stopped = await wait_for(
                lambda: ctrl.server is not None and not ctrl.server.running
                and not ctrl.engine.available, timeout=20)
            check("⏻ stops server+browser", stopped)
            check("⏻ preserves right pane in CODE",
                  shell.mode is WorkspaceMode.CODE and editor.display)

            # ---- geometry: composer can never overlap editor/preview ---------------
            composer = app.query_one(StickyComposer)
            comp_region = composer.region
            ed_region = shell.editor.region
            inter_w = min(comp_region.right, ed_region.right) - \
                max(comp_region.x, ed_region.x)
            inter_h = min(comp_region.bottom, ed_region.bottom) - \
                max(comp_region.y, ed_region.y)
            no_overlap = inter_w <= 0 or inter_h <= 0
            check("chat box never overlaps code editor", no_overlap,
                  f"composer={comp_region} editor={ed_region}")
            chat_col = shell.chat_column
            inside = (comp_region.x >= chat_col.region.x - 1
                      and comp_region.right <= chat_col.region.right + 1)
            check("composer stays inside its own column", inside)

        # ---- exit cleanliness -------------------------------------------------------
        ctrl = getattr(app, "_preview_ctrl", None)
        check("exit leaves preview stack stopped",
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
    print(f"\n{passed}/{len(_results)} web-preview e2e checks passed")
    return passed == len(_results)


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
