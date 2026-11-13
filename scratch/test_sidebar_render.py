import sys
sys.path.insert(0, ".")
import asyncio
from textual.app import App
from calc_terminal.ui.sidebar import Explorer
from calc_terminal.ui import theme_css
from calc_terminal.ui import app as cct_app

class TestApp(App):
    CSS = theme_css.BASE_CSS + cct_app._COMPONENT_CSS
    def get_css_variables(self):
        v = super().get_css_variables()
        v.update(theme_css.css_variables())
        return v
    def compose(self):
        yield Explorer()

async def main():
    app = TestApp()
    async with app.run_test(size=(40, 30)) as pilot:
        exp = app.query_one(Explorer)
        exp.open_folder("c:/Users/ADMIN")
        await pilot.pause(0.1)
        svg = app.export_screenshot()
        with open("scratch/test_sidebar_fixed_scroll.svg", "w", encoding="utf-8") as f:
            f.write(svg)
        print("Exported test_sidebar_fixed_scroll.svg")

if __name__ == "__main__":
    asyncio.run(main())

