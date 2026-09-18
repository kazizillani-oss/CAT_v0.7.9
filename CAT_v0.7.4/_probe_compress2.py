"""Faithful repro: does a Button-bearing Horizontal shrink inside a
fixed-height Vertical?"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from textual.app import App
from textual.screen import Screen
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Button


class T2(Screen):
    CSS = """
    T2 { align: center middle; }
    #v { height: 17; border: round $primary; }
    #t { height: 3; padding: 1 2 0 2; border-bottom: solid $primary; }
    #s { height: 2; }
    #b { height: 4; padding: 1 2; }
    #b Button { margin-right: 1; }
    #a { height: 4; padding: 0 2 1 2; border-top: solid $primary; }
    #a Button { margin-right: 1; }
    """

    def compose(self):
        with Vertical(id="v"):
            with Horizontal(id="t"):
                yield Static("Title", id="tt")
                yield Button("X", id="tc")
            yield Static("Sub", id="s")
            with Horizontal(id="b"):
                yield Button("Add")
                yield Button("Edit")
            with Horizontal(id="a"):
                yield Button("Save", variant="primary")
                yield Button("Cancel")


class Probe(App):
    def compose(self):
        yield from []

    async def on_mount(self):
        self.push_screen(T2())


async def main():
    app = Probe()
    async with app.run_test(size=(60, 30), headless=True) as pilot:
        await pilot.pause()
        await asyncio.sleep(0.2)
        v = app.screen.query_one("#v")
        print("V:", v.region)
        for wid in ("t", "s", "b", "a"):
            w = app.screen.query_one(f"#{wid}")
            print(f"{wid}: style={w.styles.height} size={w.size} region={w.region}")


if __name__ == "__main__":
    asyncio.run(main())
