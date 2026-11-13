from textual.app import App
from textual.screen import Screen
from textual.containers import Vertical, Horizontal, VerticalScroll
from textual.widgets import Static, Button, Input

class TestPanel(Screen):
    CSS = """
    TestPanel { align: center middle; background: rgba(0, 0, 0, 0.75); }
    #box {
        width: 88; max-width: 96%; height: auto; max-height: 88%;
        background: #1e1e2e;
        border: tall;
        border-top: tall #45475a;
        border-left: tall #45475a;
        border-bottom: tall #11111b;
        border-right: tall #11111b;
        padding: 0;
        layout: vertical;
        overflow: hidden;
    }
    #titlebar {
        height: 3; min-height: 3; max-height: 3;
        padding: 0 1;
        border-bottom: solid #313244;
        layout: horizontal;
        align-vertical: middle;
        background: #11111b;
    }
    #title { width: 1fr; text-style: bold; color: #cba6f7; }
    #close-btn {
        width: 5; min-width: 5; max-width: 5;
        height: 1; min-height: 1; max-height: 1;
        padding: 0; margin: 0;
        border: none;
        border-left: tall #ffa198;
        border-right: tall #c73859;
        background: #2b1d24;
        color: #ff7b72;
        content-align: center middle;
        text-style: bold;
    }
    #search { height: 3; padding: 0 1; margin: 1 0 0 0; }
    #search Input { width: 100%; height: 3; background: #181825; color: #cdd6f4; border: tall #313244; }
    #list {
        height: auto; min-height: 7; max-height: 22;
        overflow-y: auto; scrollbar-gutter: stable; scrollbar-size: 1 1;
        margin: 0 1; padding: 0;
    }
    .card {
        height: 6; min-height: 6; max-height: 6;
        padding: 1 2;
        border: tall;
        border-top: tall #45475a;
        border-left: tall #45475a;
        border-bottom: tall #11111b;
        border-right: tall #11111b;
        background: #181825;
        margin: 0 1 1 0;
    }
    #actions {
        height: 4; min-height: 4; max-height: 4; padding: 0 1; margin: 0;
        border-top: solid #313244;
        background: #1e1e2e;
        layout: horizontal;
        align: center middle;
    }
    #actions-left { width: 1fr; height: 3; layout: horizontal; align: left middle; }
    #actions Button {
        height: 3; min-width: 12; margin-right: 1;
        border: tall;
        border-top: tall #45475a;
        border-left: tall #45475a;
        border-bottom: tall #11111b;
        border-right: tall #11111b;
        background: #181825;
        color: #cdd6f4;
    }
    #btn-close2 {
        border-top: tall #ffa0a0 !important;
        border-left: tall #f38ba8 !important;
        border-bottom: tall #7a2d3b !important;
        border-right: tall #7a2d3b !important;
        background: #4a1e27 !important;
        color: #ff99a8 !important;
    }
    """
    def compose(self):
        with Vertical(id="box"):
            with Horizontal(id="titlebar"):
                yield Static("▣  Extensions & Component Manager", id="title")
                yield Button("✕", id="close-btn")
            with Vertical(id="search"):
                yield Input(placeholder="Search extensions, skills, commands...")
            with VerticalScroll(id="list"):
                for i in range(4):
                    yield Static(f"Card {i+1}", classes="card")
            with Horizontal(id="actions"):
                with Horizontal(id="actions-left"):
                    yield Button("↓ GitHub Install")
                    yield Button("＋ Create Extension")
                    yield Button("Enable All")
                yield Button("Close", id="btn-close2")

class TestApp(App):
    def on_mount(self):
        self.push_screen(TestPanel())

app = TestApp()
async def test():
    async with app.run_test(size=(100, 38)) as pilot:
        p = app.screen
        box = p.query_one('#box')
        list_w = p.query_one('#list')
        act = p.query_one('#actions')
        print('box region:', box.region)
        print('list region:', list_w.region)
        print('act region:', act.region)
        print('box bottom:', box.region.y + box.region.height)
        print('act bottom:', act.region.y + act.region.height)
        print('difference (dead space):', (box.region.y + box.region.height) - (act.region.y + act.region.height) - 1)

import asyncio
asyncio.run(test())

