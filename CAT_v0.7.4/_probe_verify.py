"""Headless pilot: render MCP/Backup/Attach modals at several terminal
sizes and verify the footer buttons are fully inside the box and on screen."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from textual.app import App
from textual.widgets import Button


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


async def check(size, name, fac):
    app = Probe(fac)
    async with app.run_test(size=size, headless=True) as pilot:
        await pilot.pause()
        await asyncio.sleep(0.35)
        screen = app.screen
        box = None
        for w in screen.query("*"):
            if w.id and w.id.endswith("-box"):
                box = w
                break
        if box is None:
            print(f"{name} @ {size}: NO BOX FOUND")
            return
        vh, vw = screen.size.height, screen.size.width
        inside, outside = [], []
        for b in screen.query(Button):
            if box.region.contains_region(b.region):
                inside.append((b.id, b.region.y, b.region.height))
            else:
                outside.append((b.id, b.region.y, b.region.height))
        on_screen = all(0 <= b.region.y < vh and b.region.bottom <= vh for b in screen.query(Button))
        centered = abs((box.region.y + box.region.height / 2) - vh / 2) <= 1.5
        box_fits = box.region.height <= vh
        print(f"{name} @ {vw}x{vh}: box={box.region} centered={centered} fits={box_fits} "
              f"buttons_inside_box={len(inside)} buttons_outside={len(outside)} all_buttons_on_screen={on_screen}")
        if outside:
            print(f"   OUTSIDE buttons: {outside}")


async def main():
    from calc_terminal.ui.mcp_panel import McpServersPanel, _AddMcpForm
    from calc_terminal.ui.backup_panel import BackupProvidersPanel, _AddProviderForm
    from calc_terminal.ui.attach_panel import AttachPanel

    for size in [(120, 44), (100, 30), (80, 24)]:
        for name, fac in [
            ("MCP main", lambda: McpServersPanel()),
            ("MCP add", lambda: _AddMcpForm()),
            ("Backup main", lambda: BackupProvidersPanel()),
            ("Backup add", lambda: _AddProviderForm()),
            ("Attach", lambda: AttachPanel()),
        ]:
            await check(size, name, fac)
        print()


if __name__ == "__main__":
    asyncio.run(main())
