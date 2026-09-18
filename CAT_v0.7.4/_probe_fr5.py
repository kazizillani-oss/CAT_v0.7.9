"""Test: box auto + max-height 92%; list height auto + max-height 1fr."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from textual.app import App
from textual.screen import Screen
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.widgets import Static, Button

ROWS = int(sys.argv[1]) if len(sys.argv) > 1 else 2
LIST_CSS = sys.argv[2] if len(sys.argv) > 2 else "height: auto; max-height: 1fr;"


class TestScreen(Screen):
    CSS = f"""
    TestScreen {{ align: center middle; background: $surface 70%; }}
    #t-box {{
        width: 70; height: auto; max-height: 92%;
        background: $surface; border: round $border; padding: 0;
    }}
    #t-title {{ height: 3; border-bottom: solid $border; }}
    #t-list {{ {LIST_CSS} min-height: 3; overflow-y: auto; border: solid $border; }}
    .t-row {{ height: 3; }}
    #t-foot {{ height: 3; border-top: solid $border; }}
    """

    def compose(self):
        with Vertical(id="t-box"):
            yield Static("TITLE", id="t-title")
            with ScrollableContainer(id="t-list"):
                for i in range(ROWS):
                    yield Static(f"row {i}", classes="t-row")
            with Horizontal(id="t-foot"):
                yield Button("Cancel")
                yield Button("Save", variant="primary")


class Probe(App):
    def compose(self):
        yield from []

    def get_css_variables(self):
        from calc_terminal.ui import theme_css
        variables = dict(super().get_css_variables())
        variables.update(theme_css.css_variables())
        return variables

    async def on_mount(self):
        self.push_screen(TestScreen())


async def main():
    for size in [(100, 40), (100, 24), (100, 16)]:
        app = Probe()
        async with app.run_test(size=size, headless=True) as pilot:
            await pilot.pause()
            box = app.screen.query_one("#t-box")
            lst = app.screen.query_one("#t-list")
            foot = app.screen.query_one("#t-foot")
            print(f"rows={ROWS} size={size}: box={box.region} list={lst.region} "
                  f"content_size={lst.content_size} foot={foot.region} "
                  f"foot_in_box={box.region.contains_region(foot.region)}")


if __name__ == "__main__":
    asyncio.run(main())
