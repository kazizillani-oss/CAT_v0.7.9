"""Check whether each panel's CSS actually loads."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from textual.app import App


class Probe(App):
    def __init__(self, screen_factory):
        super().__init__()
        self._factory = screen_factory

    def compose(self):
        yield from []

    def get_css_variables(self):
        from calc_terminal.ui import theme_css
        variables = dict(super().get_css_variables())
        variables.update(theme_css.css_variables())
        return variables

    async def on_mount(self):
        self.push_screen(self._factory())


async def main():
    from calc_terminal.ui.mcp_panel import McpServersPanel, _AddMcpForm
    from calc_terminal.ui.backup_panel import BackupProvidersPanel, _AddProviderForm
    from calc_terminal.ui.attach_panel import AttachPanel

    from calc_terminal.ui import theme_css
    from textual.css.tokenize import Tokenizer
    from textual.css.model import parse as css_parse
    from textual.css.errors import StylesheetError

    for name, fac in [
        ("MCP main", lambda: McpServersPanel()),
        ("MCP add", lambda: _AddMcpForm()),
        ("Backup main", lambda: BackupProvidersPanel()),
        ("Backup add", lambda: _AddProviderForm()),
        ("Attach", lambda: AttachPanel()),
    ]:
        app = Probe(fac)
        async with app.run_test(size=(100, 40), headless=True) as pilot:
            await pilot.pause()
            css = fac().CSS
            try:
                tokens = Tokenizer(css, (fac.__name__ + ".CSS",)).tokenize()
                css_parse(tokens)
                print(f"{name}: CSS parses OK")
            except Exception as e:
                print(f"{name}: CSS FAILED -> {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
