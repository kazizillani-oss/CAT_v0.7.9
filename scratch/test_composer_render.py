import sys
import asyncio
sys.stdout.reconfigure(encoding='utf-8')
from textual.app import App
from calc_terminal.ui.composer import StickyComposer

class TestApp(App):
    def compose(self):
        yield StickyComposer()

async def main():
    app = TestApp()
    async with app.run_test(size=(60, 20)) as pilot:
        comp = app.query_one(StickyComposer)
        comp.set_ai_mode("build")
        await pilot.pause()
        lines = pilot.app.screen.render_lines()
        print("=== RENDERED SCREEN (60x20, build mode) ===")
        for i, line in enumerate(lines):
            text = "".join(s.text for s in line)
            if text.strip():
                print(f"{i:2d}: [{len(text)}] {text}")

if __name__ == "__main__":
    asyncio.run(main())

