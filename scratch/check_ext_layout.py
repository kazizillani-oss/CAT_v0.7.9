from textual.app import App
from textual.screen import Screen
from calc_terminal.ui.extensions_panel import ExtensionsPanel

class DummyApp(App):
    CSS = """
    $surface: #1e1e2e;
    $surface-alt: #181825;
    $surface-dark: #11111b;
    $surface-highlight: #45475a;
    $surface-shadow: #11111b;
    $surface-active: #313244;
    $accent: #cba6f7;
    $accent-dark: #89b4fa;
    $accent-highlight: #b4befe;
    $border: #313244;
    $text: #cdd6f4;
    $text-muted: #6c7086;
    $text-faint: #585b70;
    $warning: #f9e2af;
    $error: #f38ba8;
    $success: #a6e3a1;
    """
    def on_mount(self):
        self.push_screen(ExtensionsPanel())

app = DummyApp()
async def test():
    async with app.run_test(size=(100, 38)) as pilot:
        p = app.screen
        box = p.query_one('#ext-box')
        print('box region:', box.region)
        for c in box.children:
            print('  child:', c.id or c, 'region:', c.region)

import asyncio
asyncio.run(test())

