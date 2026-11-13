import asyncio
from textual.app import App
from textual.screen import Screen
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Button

css_test = """
AgentModeMenuTest {
    align: center middle;
    background: rgba(0, 0, 0, 0.65);
}
#cct-agentmenu-box {
    width: 74;
    height: auto;
    background: #13141f;
    border: tall;
    border-top: tall #8b92b2;
    border-left: tall #6e7594;
    border-bottom: tall #585b70;
    border-right: tall #45475a;
    padding: 0 1;
}
#cct-agentmenu-titlebar {
    height: 3;
    padding: 0 1;
    layout: horizontal;
    align-vertical: middle;
    background: #1c1e2d;
    color: #fab387;
    border-top: tall #fab387;
    border-left: tall #fab387;
    border-bottom: tall #585b70;
    border-right: tall #45475a;
    margin: 1 0 0 0;
}
#cct-agentmenu-title {
    text-style: bold;
    width: 1fr;
    height: 1;
    align-vertical: middle;
    color: #fab387;
}
Button#cct-agentmenu-close, Button.cct-agentmenu-close-btn {
    width: 5;
    min-width: 0;
    max-width: 5;
    height: 1;
    min-height: 0;
    max-height: 1;
    padding: 0;
    margin: 0;
    background: #2b1d24;
    color: #ff7b72;
    border: none;
    border-left: tall #ffa198;
    border-right: tall #c73859;
    content-align: center middle;
    text-style: bold;
}
Button#cct-agentmenu-close:hover {
    background: #e06c75;
    color: #ffffff;
    border-left: tall #ffffff;
    border-right: tall #801020;
}
"""

class AgentModeMenuTest(Screen):
    DEFAULT_CSS = css_test
    def compose(self):
        with Vertical(id="cct-agentmenu-box"):
            with Horizontal(id="cct-agentmenu-titlebar"):
                yield Static("🐱  Kitties (1-Click Switch)", id="cct-agentmenu-title")
                yield Button("✕", id="cct-agentmenu-close", classes="cct-agentmenu-close-btn")

class TestApp(App):
    def on_mount(self):
        self.push_screen(AgentModeMenuTest())

async def run():
    app = TestApp()
    async with app.run_test(size=(90, 20)) as pilot:
        await pilot.pause()
        svg = app.export_screenshot()
        with open("scratch/test_agentmenu_close_fixed.svg", "w", encoding="utf-8") as f:
            f.write(svg)
        print("Exported fixed SVG")

asyncio.run(run())
