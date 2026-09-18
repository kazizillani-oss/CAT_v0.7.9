"""Experiment: auto-height box with a 1fr scrollable child + max-height %."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from textual.app import App
from textual.screen import Screen
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.widgets import Static, Button


class TestScreen(Screen):
    CSS = """
    TestScreen { align: center middle; background: $surface 70%; }
    #t-box {
        width: 70; height: auto; max-height: 92%;
        background: $surface; border: round $border; padding: 0;
    }
    #t-title { height: 3; border-bottom: solid $border; }
    #t-list { height: 1fr; min-height: 3; overflow-y: auto; border: solid $border; }
    .t-row { height: 3; }
    #t-foot { height: 3; border-top: solid $border; }
    """

    def compose(self):
        with Vertical(id="t-box"):
            yield Static("TITLE", id="t-title")
            with ScrollableContainer(id="t-list"):
                for i in range(10):
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
            print(f"size={size}: box={box.region} list={lst.region} foot={foot.region}")
            print(f"   foot inside box: {box.region.contains_region(foot.region)}, "
                  f"box fits: {box.region.height <= size[1]}")


if __name__ == "__main__":
    asyncio.run(main())
