import asyncio
from textual.app import App
from calc_terminal.ui import theme_css
from calc_terminal.ui.app import _COMPONENT_CSS
from calc_terminal.ui.header import NavPanel, _NavRow

class TestApp(App):
    CSS = theme_css.BASE_CSS + _COMPONENT_CSS
    def get_css_variables(self):
        v = dict(super().get_css_variables())
        v.update(theme_css.css_variables())
        return v

async def main():
    app = TestApp()
    async with app.run_test(size=(90, 30)) as pilot:
        screen = NavPanel()
        app.push_screen(screen)
        await pilot.pause(0.05)
        rows = list(screen.query(_NavRow))
        print('Row count:', len(rows))
        for r in rows[:5]:
            print(f"{r._label}: border={r.styles.border} border_top={r.styles.border_top} height={r.styles.height}")

asyncio.run(main())

