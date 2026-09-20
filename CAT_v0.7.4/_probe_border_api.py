"""Diagnose the runtime border-style API + scoped button query."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main():
    from textual.widgets import Button
    from calc_terminal import aicore
    from calc_terminal import projects as _projects
    from calc_terminal.ui.app import CCTApp
    _projects.recent = lambda: []
    aicore.save_config({"provider": "groq", "model": "x", "api_style": "openai",
                        "api_key": "t", "base_url": "https://localhost"})
    app = CCTApp(repl=None, history=[], stats={})
    async with app.run_test(size=(120, 40), headless=True) as pilot:
        for _ in range(8):
            await pilot.pause()
            await asyncio.sleep(0.1)
        try:
            await pilot.press("escape")
            await pilot.pause()
        except Exception:
            pass
        for _ in range(6):
            await pilot.pause()
            await asyncio.sleep(0.1)

        conv = app.query_one("#cct-conversation")
        dash = conv._welcome
        print("dash:", type(dash).__name__, "classes:", dash.classes,
              "size:", dash.size, "outer:", dash.outer_size)
        for sel in ("#cct-dash-actions", "#cct-dash-columns",
                    "#cct-empty-art"):
            try:
                w = dash.query_one(sel)
                print(f"  {sel}: size={w.size} outer={w.outer_size} "
                      f"height_style={w.styles.height!r} "
                      f"display={w.display}")
            except Exception as e:
                print(f"  {sel}: MISSING {e!r}")
        b = dash.query_one("#dash-open-folder", Button)
        print("button: size=", b.size, "outer=", b.outer_size,
              "container=", b.container_size)
        print("  styles.height=", b.styles.height,
              " min_height=", b.styles.min_height,
              " max_height=", b.styles.max_height)
        print("  computed border top/left/bottom/right:",
              b.styles.border_top, b.styles.border_left,
              b.styles.border_bottom, b.styles.border_right)
        print("dash parent:", type(dash.parent).__name__,
              getattr(dash.parent, "id", None),
              getattr(dash.parent, "classes", None))
        print("dash region:", dash.region)
        print("conversation region:", conv.region, "scroll:", conv.scroll_offset)


asyncio.run(main())
