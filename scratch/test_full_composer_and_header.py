import sys
sys.path.insert(0, ".")
import asyncio
from textual.app import App
from calc_terminal.ui.header import BrandHeader
from calc_terminal.ui.composer import StickyComposer
from calc_terminal.ui import theme_css, app as cct_app

class FullApp(App):
    CSS = theme_css.BASE_CSS + cct_app._COMPONENT_CSS
    def get_css_variables(self):
        v = super().get_css_variables()
        v.update(theme_css.css_variables())
        return v
    def compose(self):
        yield BrandHeader()
        yield StickyComposer()

async def main():
    for w in [45, 60, 80, 100, 120]:
        app = FullApp()
        async with app.run_test(size=(w, 24)) as pilot:
            hdr = app.query_one(BrandHeader)
            comp = app.query_one(StickyComposer)
            hdr.on_resize()
            await pilot.pause(0.05)
            print(f"=== WIDTH {w} ===")
            print(f"Header:   {hdr.region} (max_x={hdr.region.x + hdr.region.width})")
            print(f"Composer: {comp.region} (max_x={comp.region.x + comp.region.width})")
            for bid in ["btn-attach", "btn-permissions", "btn-security", "cct-input", "btn-mic", "btn-send", "btn-stop"]:
                try:
                    b = comp.query_one(f"#{bid}")
                    print(f"  {bid:16}: display={b.display} region={b.region}")
                except Exception as e:
                    print(f"  {bid:16}: not found")

if __name__ == "__main__":
    asyncio.run(main())

