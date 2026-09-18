"""Drag-handle end-to-end simulation for CAT v0.7.9.0: real MouseDown/
MouseMove/MouseUp sequences against both resize handles, plus window
resize stability."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from textual import events

from calc_terminal.ui.app import CCTApp
from calc_terminal.ui.workspace import WorkspaceShell
from calc_terminal.ui.composer import StickyComposer

WS = r"C:\Users\ADMIN\Downloads\compressed"


class _FakeRepl:
    VERSION = "0.7.9.0"




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
    results = []

    def check(name, ok, extra=""):
        results.append(ok)
        print(f"[{'PASS' if ok else 'FAIL'}] {name} {extra}")

    # Fresh layout state — earlier runs may have persisted drag results.
    from calc_terminal.ui import resizers
    if os.path.exists(resizers.LAYOUT_PATH):
        os.remove(resizers.LAYOUT_PATH)

    os.makedirs(WS, exist_ok=True)
    app = CCTApp(_FakeRepl(), [], {})
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await dismiss_welcome(app, pilot)
        await app._open_folder(WS)
        await pilot.pause()
        shell = app.query_one(WorkspaceShell)
        composer = app.query_one(StickyComposer)
        explorer = shell.explorer

        async def drag(widget, dx_steps):
            """Press at the widget's center, then move in screen-space
            steps, then release."""
            r = widget.region
            sx, sy = r.x + r.width // 2, r.y + r.height // 2
            await pilot.mouse_down(offset=(sx, sy))
            for ddx, ddy in dx_steps:
                sx += ddx
                sy += ddy
                await pilot._post_mouse_events(
                    [events.MouseMove], offset=(sx, sy), button=1)
                await pilot.pause()
            await pilot.mouse_up(offset=(sx, sy))
            await pilot.pause()

        # ---- explorer divider: widen, narrow, clamp ----
        div = shell.query_one("#cct-explorer-resizer")
        explorer.set_width(32)
        await pilot.pause()
        start_w = explorer.width
        await drag(div, [(4, 0)] * 6)
        w_wide = explorer.width
        check("explorer divider drag widens panel", w_wide > start_w,
              f"{start_w} -> {w_wide}")
        await drag(div, [(-3, 0)] * 10)
        check("explorer divider drag narrows panel",
              explorer.width < w_wide, f"{w_wide} -> {explorer.width}")
        await drag(div, [(-8, 0)] * 3)
        check("explorer clamped at min width",
              explorer.width >= 14 and explorer.width <= 20,
              f"w={explorer.width}")

        # restore a sane width
        explorer.set_width(32)
        await pilot.pause()

        # ---- composer grip: grow, shrink ----
        grip = shell.query_one("#cct-composer-resizer")
        h0 = composer.region.height
        await drag(grip, [(0, -3)] * 5)
        h1 = composer.region.height
        check("composer grip drag up grows composer", h1 > max(h0, 1),
              f"{h0} -> {h1}")
        e_check = explorer.width
        await drag(grip, [(0, 4)] * 4)
        h2 = composer.region.height
        check("composer grip drag down shrinks composer", h1 > h2 >= 4,
              f"{h1} -> {h2}")
        check("explorer untouched during composer resizes",
              explorer.width == e_check, f"w={explorer.width}")
        conv_h = shell.query_one("#cct-conversation").region.height
        check("chat history keeps usable space", conv_h >= 8,
              f"chat_h={conv_h}")

        # ---- window resize stability ----
        for size in [(200, 50), (90, 32), (70, 26), (120, 40)]:
            await pilot.resize_terminal(*size)
            await pilot.pause()
            await asyncio.sleep(0.05)
            await pilot.pause()
            e = explorer.region
            c = composer.region
            m = shell.query_one("#cct-workspace-main").region
            ok = (c.x >= m.x - 1 and c.x + c.width <= m.x + m.width + 2
                  and e.x + e.width <= m.x + 1)
            check(f"no overlap after window resize @ {size}", ok,
                  f"explorer_w={e.width} composer=({c.x},{c.y},{c.width},{c.height})")

        # persistence written by drags
        from calc_terminal.ui import resizers
        saved = resizers.load_layout() if os.path.exists(
            resizers.LAYOUT_PATH) else {}
        check("dragged sizes persisted",
              saved.get("composer_height") is not None
              or saved.get("explorer_width") is not None, str(saved))
        if os.path.exists(resizers.LAYOUT_PATH):
            os.remove(resizers.LAYOUT_PATH)

    print(f"\n{sum(results)}/{len(results)} drag checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
