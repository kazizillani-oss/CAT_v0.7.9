"""Test: does a fixed-height Vertical compress explicit-height children?"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from textual.app import App
from textual.screen import Screen
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Button
from textual.css.styles import Styles


class T1(Screen):
    CSS = """
    T1 { align: center middle; }
    #v { height: 15; border: round $primary; }
    #a { height: 3; background: red; }
    #b { height: 4; background: green; }
    #c { height: 6; background: blue; }
    """

    def compose(self):
        with Vertical(id="v"):
            yield Static("A", id="a")
            yield Static("B", id="b")
            yield Static("C", id="c")


class Probe(App):
    def compose(self):
        yield from []

    async def on_mount(self):
        self.push_screen(T1())


async def main():
    app = Probe()
    async with app.run_test(size=(60, 30), headless=True) as pilot:
        await pilot.pause()
        v = app.screen.query_one("#v")
        print("V:", v.region, "content:", v.content_size)
        for wid in ("a", "b", "c"):
            w = app.screen.query_one(f"#{wid}")
            print(f"{wid}: style={w.styles.height} size={w.size} region={w.region}")


if __name__ == "__main__":
    asyncio.run(main())
