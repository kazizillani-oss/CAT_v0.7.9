import sys
sys.path.insert(0, ".")
import asyncio
from textual.app import App
from calc_terminal.ui.composer import StickyComposer
from calc_terminal.ui import theme_css
from calc_terminal.ui import app as cct_app

class TestApp(App):
    CSS = theme_css.BASE_CSS + cct_app._COMPONENT_CSS
    def get_css_variables(self):
        v = super().get_css_variables()
        v.update(theme_css.css_variables())
        return v
    def compose(self):
        yield StickyComposer(model_label="nvidia/nemotron-3-ultra-550b-a55b")

async def main():
    for w in [48, 65, 80]:
        app = TestApp()
        async with app.run_test(size=(w, 14)) as pilot:
            comp = app.query_one(StickyComposer)
            comp.set_ai_mode("agent")
            await pilot.pause(0.1)
            svg = app.export_screenshot()
            with open(f"scratch/composer_render_{w}.svg", "w", encoding="utf-8") as f:
                f.write(svg)
            print(f"Exported composer_render_{w}.svg")

if __name__ == "__main__":
    asyncio.run(main())

