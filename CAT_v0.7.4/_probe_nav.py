"""Debug ap-nav row overflow."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from textual.app import App


def make_probe_cls():
    from calc_terminal.ui import theme_css

    class Probe(App):
        CSS = theme_css.BASE_CSS

        def compose(self):
            yield from []

        def get_css_variables(self):
            variables = dict(super().get_css_variables())
            variables.update(theme_css.css_variables())
            return variables

        async def on_mount(self):
            from calc_terminal.ui.attach_panel import AttachPanel
            self.push_screen(AttachPanel())

    return Probe


async def main():
    Probe = make_probe_cls()
    app = Probe()
    async with app.run_test(size=(100, 40), headless=True) as pilot:
        for _ in range(8):
            await pilot.pause()
            await asyncio.sleep(0.15)
        box = app.screen.query_one("#ap-box")
        nav = app.screen.query_one("#ap-nav")
        print("box:", box.region, "nav:", nav.region)
        for b in app.screen.query("Button"):
            if b.region.height:
                print(f"  {b.id}: {b.region}")


if __name__ == "__main__":
    asyncio.run(main())
