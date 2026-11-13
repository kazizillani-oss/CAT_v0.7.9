import asyncio
from textual.app import App, ComposeResult
from calc_terminal.ui import theme_css
from calc_terminal.ui.app import _COMPONENT_CSS
from calc_terminal.ui.header import BrandHeader, NavPanel

class TestApp(App):
    CSS = theme_css.BASE_CSS + _COMPONENT_CSS
    def get_css_variables(self):
        v = dict(super().get_css_variables())
        v.update(theme_css.css_variables())
        return v
    def compose(self) -> ComposeResult:
        yield BrandHeader()

async def main():
    app = TestApp()
    async with app.run_test(size=(90, 30)) as pilot:
        screen = NavPanel()
        app.push_screen(screen)
        await pilot.pause(0.1)
        svg = app.export_screenshot()
        with open('scratch/nav_panel_verified.svg', 'w', encoding='utf-8') as f:
            f.write(svg)
        print('Exported nav_panel_verified.svg')

asyncio.run(main())

