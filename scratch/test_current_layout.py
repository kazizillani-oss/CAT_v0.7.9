import asyncio
from textual.app import App, ComposeResult
from calc_terminal.ui import theme_css, app as cct_app
from calc_terminal.ui.header import BrandHeader
from calc_terminal.ui.composer import StickyComposer

class LayoutTestApp(App):
    CSS = theme_css.BASE_CSS + cct_app._COMPONENT_CSS
    def get_css_variables(self):
        v = super().get_css_variables()
        v.update(theme_css.css_variables())
        return v
    def compose(self) -> ComposeResult:
        yield BrandHeader()
        yield StickyComposer()

async def main():
    for w, h in [(100, 30), (50, 30)]:
        app = LayoutTestApp()
        async with app.run_test(size=(w, h)) as pilot:
            hdr = app.query_one(BrandHeader)
            hdr.on_resize()
            comp = app.query_one(StickyComposer)
            await pilot.pause(0.05)
            print(f"=== Size {w}x{h} ===")
            print(f"Header region: {hdr.region}")
            print(f"Composer region: {comp.region}")
            for wid in ["cct-composer-left", "cct-right-controls", "cct-prompt-row", "btn-send", "btn-attach", "btn-permissions"]:
                try:
                    elem = comp.query_one(f"#{wid}")
                    print(f"  {wid}: region={elem.region}, display={elem.display}")
                except Exception as e:
                    print(f"  {wid}: NOT FOUND ({e})")

if __name__ == "__main__":
    asyncio.run(main())
