import asyncio
from textual.app import App
from calc_terminal.ui.header import BrandHeader
from calc_terminal.ui import theme_css

class TestApp(App):
    CSS = theme_css.BASE_CSS
    def get_css_variables(self):
        v = super().get_css_variables()
        v.update(theme_css.css_variables())
        return v
    def compose(self):
        yield BrandHeader()

async def main():
    for w in [35, 45, 60, 80]:
        app = TestApp()
        async with app.run_test(size=(w, 24)) as pilot:
            hdr = app.query_one(BrandHeader)
            hdr.on_resize()
            await pilot.pause(0.05)
            print(f"=== WIDTH {w} ===")
            print(f"Header: {hdr.region}")
            for wid in ["cct-header-top", "cct-header-left", "cct-nav-menu-btn", "cct-logo", "cct-header-perm-pill", "cct-header-right-box", "cct-header-explorer-btn", "cct-header-right"]:
                try:
                    wobj = hdr.query_one(f"#{wid}")
                    print(f"  {wid}: display={wobj.display}, region={wobj.region}")
                except Exception as e:
                    print(f"  {wid}: not found")

if __name__ == "__main__":
    asyncio.run(main())
