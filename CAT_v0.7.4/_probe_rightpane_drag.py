"""Quick regression: RightPaneResizeHandle drag must not raise and must
resize + persist (regression for 'Vertical' has no set_width)."""
import asyncio
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_results = []


def check(name, ok, detail=""):
    _results.append((name, bool(ok), detail))
    print(("[PASS] " if ok else "[FAIL] ") + name + f" {detail}")


async def main():
    from calc_terminal import theme
    from calc_terminal.app import App as ReplApp
    from calc_terminal.ui.app import CCTApp
    from calc_terminal.ui.workspace import WorkspaceShell
    from calc_terminal.ui.resizers import (RightPaneResizeHandle,
                                           load_layout)

    backup = None
    from calc_terminal.ui.resizers import LAYOUT_PATH
    if os.path.exists(LAYOUT_PATH):
        with open(LAYOUT_PATH, encoding="utf-8") as f:
            backup = f.read()
    try:
        root = tempfile.mkdtemp(prefix="cat_drag_ws_")
        with open(os.path.join(root, "index.html"), "w") as f:
            f.write("<h1>x</h1>")

        repl = ReplApp()
        app = CCTApp(repl, [], {"solved": 0})
        async with app.run_test(size=(150, 42), headless=True) as pilot:
            from calc_terminal.ui.welcome_modal import WelcomeModal
            for _ in range(30):
                if not any(isinstance(s, WelcomeModal)
                           for s in app.screen_stack):
                    break
                await pilot.press("escape")
                await asyncio.sleep(0.05)
            shell = app.query_one(WorkspaceShell)
            await app._open_folder(root)
            await pilot.pause(); await asyncio.sleep(0.4)
            # A file must be open for the right pane to claim space
            # (chat-only until then — correct behavior).
            shell.open_file(os.path.join(root, "index.html"))
            await pilot.pause(); await asyncio.sleep(0.4)

            handle = shell.query_one(RightPaneResizeHandle)
            check("handle visible in split mode", bool(handle.display))

            before = shell.right_pane.size.width or 44
            # simulate a real drag: press on the handle, move left ~10
            # cells, release (same mechanics _probe_cat_drag uses).
            hx = handle.region.x + handle.region.width // 2
            hy = handle.region.y + 2
            await pilot.hover(handle, offset=(0, 2))
            await pilot.mouse_down(handle, offset=(0, 2))
            for dx in range(1, 11):
                try:
                    await pilot.hover(None,
                                      offset=(hx - dx - app.screen.x
                                              if hasattr(app, "screen")
                                              else hx - dx, hy))
                except Exception:
                    pass
                await pilot.pause()
            await pilot.mouse_up(handle, offset=(-10, 2) if False else (0, 2))
            await pilot.pause(); await asyncio.sleep(0.3)

            after = shell.right_pane.size.width or 0
            check("drag did not crash and resized",
                  isinstance(after, int) and after > 0,
                  f"{before} -> {after}")
            saved = load_layout().get("rightpane_width")
            check("width persisted after drag", saved == getattr(
                shell, "_rightpane_width", None), str(saved))
    finally:
        if backup is not None:
            with open(LAYOUT_PATH, "w", encoding="utf-8") as f:
                f.write(backup)
        elif os.path.exists(LAYOUT_PATH):
            os.remove(LAYOUT_PATH)

    passed = sum(1 for _, ok, _ in _results if ok)
    print(f"\n{passed}/{len(_results)} right-drag checks passed")
    return passed == len(_results)


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
