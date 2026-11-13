import asyncio
from textual.app import App
from calc_terminal.ui.extensions_panel import ExtensionsPanel
from calc_terminal.ui import theme_css

class TestApp(App):
    CSS = theme_css.BASE_CSS
    def get_css_variables(self):
        vars_dict = dict(super().get_css_variables())
        vars_dict.update(theme_css.css_variables())
        return vars_dict
    def on_mount(self):
        self.push_screen(ExtensionsPanel())

async def main():
    app = TestApp()
    async with app.run_test(size=(105, 38)) as pilot:
        await pilot.pause(0.5)
        screen = app.screen
        print("Screen class:", type(screen))
        print("All node IDs in screen:")
        for w in screen.query("*"):
            print(f"  {type(w).__name__} (id={w.id!r}, classes={list(w.classes)})")

if __name__ == "__main__":
    asyncio.run(main())

