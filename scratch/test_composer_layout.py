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
        yield StickyComposer()

async def main():
    for w in [50, 80, 100, 120]:
        app = TestApp()
        async with app.run_test(size=(w, 24)) as pilot:
            comp = app.query_one(StickyComposer)
            await pilot.pause(0.05)
            print(f"=== WIDTH {w} ===")
            print(f"Composer region: {comp.region}")
            for wid in ["cct-prompt-row", "cct-editor-stack", "cct-input", "cct-footer", "cct-left-controls", "cct-center-status", "cct-right-controls", "btn-permissions", "btn-attach", "btn-send", "btn-stop"]:
                try:
                    wobj = comp.query_one(f"#{wid}")
                    print(f"  {wid}: display={wobj.display}, region={wobj.region}")
                except Exception:
                    pass

if __name__ == "__main__":
    asyncio.run(main())
