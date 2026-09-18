"""Check why main-panel CSS isn't applied — dump matching rules."""
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
    from calc_terminal.ui.backup_panel import BackupProvidersPanel
    from calc_terminal.ui.attach_panel import AttachPanel

    for name, fac in [
        ("MCP main", lambda: McpServersPanel()),
        ("MCP add", lambda: _AddMcpForm()),
        ("Backup main", lambda: BackupProvidersPanel()),
        ("Attach", lambda: AttachPanel()),
    ]:
        app = Probe(fac)
        async with app.run_test(size=(100, 40), headless=True) as pilot:
            await pilot.pause()
            ss = app.stylesheet
            rules = []
            for _r in ss.rules:
                for selector in _r.selector_set:
                    s = str(selector)
                    if "mcp-box" in s or "amf-box" in s \
                       or "bpp-box" in s or "ap-box" in s:
                        rules.append(s)
            print(f"{name}: rules={rules[:5]}")
            screen_css = getattr(app.screen, "_css", None)
            print(f"   screen class={type(app.screen).__name__}")


if __name__ == "__main__":
    asyncio.run(main())
