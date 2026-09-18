import asyncio, sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from textual.app import App
from calc_terminal.ui import theme_css
from calc_terminal.ui.attach_panel import AttachPanel

class P(App):
    CSS = theme_css.BASE_CSS
    def compose(self): yield from []
    def get_css_variables(self):
        v = dict(super().get_css_variables()); v.update(theme_css.css_variables()); return v
    async def on_mount(self): self.push_screen(AttachPanel())

async def main():
    app = P()
    async with app.run_test(size=(100, 40), headless=True) as pilot:
        for _ in range(6):
            await pilot.pause(); await asyncio.sleep(0.15)
        s = app.screen
        print("view before:", s._view)
        s._cwd = os.path.dirname(os.path.abspath(__file__))
        s._enter_mode("files")
        print("view after:", s._view)
        try:
            s._refresh_chrome()
            print("refresh_chrome: OK")
        except Exception:
            traceback.print_exc()
        try:
            s._refresh_cap()
            print("refresh_cap: OK")
        except Exception:
            traceback.print_exc()

asyncio.run(main())
