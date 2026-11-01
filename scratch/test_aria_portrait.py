import os
import sys
import asyncio
sys.stdout.reconfigure(encoding="utf-8")
from calc_terminal.app import App
from calc_terminal.ui.app import CCTApp
from calc_terminal.ui.composer import StickyComposer

ARTIFACT_DIR = r"C:\Users\ADMIN\.gemini\antigravity\brain\6044f886-d0e4-4199-9ee7-c7349e91cb18"

async def test_widths():
    for w in [42, 45, 48, 50, 55, 60]:
        repl = App()
        stats = {"solved": 0, "provider": "none", "model": "none"}
        app = CCTApp(repl, repl.history, stats)
        async with app.run_test(size=(w, 35)) as pilot:
            await pilot.pause()
            comp = app.query_one(StickyComposer)
            comp.set_ai_mode("build")
            await pilot.pause()
            await pilot.pause()
            
            svg_path = os.path.join(ARTIFACT_DIR, f"scratch_aria_portrait_{w}x35.svg")
            app.save_screenshot(svg_path)
            print(f"Saved {w}x35 screenshot")

if __name__ == "__main__":
    asyncio.run(test_widths())
