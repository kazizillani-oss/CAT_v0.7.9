import asyncio
from textual.app import App
from calc_terminal.ui.composer import StickyComposer

class TestApp(App):
    CSS = """
    Screen { background: #13141f; }
    """
    def compose(self):
        yield StickyComposer(model_label="nvidia/nemotron-3-ultra-550b-a55b")

async def test_width(w, name):
    app = TestApp()
    async with app.run_test(size=(w, 20)) as pilot:
        await pilot.pause()
        comp = app.query_one(StickyComposer)
        comp.set_ai_mode("agent")
        await pilot.pause()
        svg = app.export_screenshot()
        with open(f"scratch/{name}.svg", "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"Exported {name}.svg with width {w}")

async def main():
    await test_width(50, "test_composer_w50")
    await test_width(80, "test_composer_w80")

asyncio.run(main())

