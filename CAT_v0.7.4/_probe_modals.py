"""Headless pilot: render MCP/Backup/Attach modals at several terminal
sizes and dump what the dialog box actually looks like (to find footer
clipping / empty-space bugs). Run: python _probe_modals.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from textual.app import App
from textual.pilot import Pilot


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

    for size in [(100, 40), (100, 30), (100, 24)]:
        for name, fac in [
            ("MCP main", lambda: McpServersPanel()),
            ("MCP add", lambda: _AddMcpForm()),
            ("Backup main", lambda: BackupProvidersPanel()),
            ("Backup add", lambda: _AddProviderForm()),
            ("Attach", lambda: AttachPanel()),
        ]:
            app = Probe(fac)
            async with app.run_test(size=size, headless=True) as pilot:
                await pilot.pause()
                await asyncio.sleep(0.3)
                screen = app.screen
                # find the box widget
                box = None
                for w in screen.query("*"):
                    if w.id and w.id.endswith("-box"):
                        box = w
                        break
                print(f"--- {name} @ {size[0]}x{size[1]} ---")
                if box is not None:
                    print(f"box id={box.id} region={box.region} size={box.size} visible={box.visible}")
                    print(f"box styles height={box.styles.height} max_height={box.styles.max_height} width={box.styles.width}")
                    # dump the footer row + last rows of the screen
                    from textual.widgets import Button
                    btns = [w for w in box.query(Button) if w.region.bottom > box.region.bottom - 2]
                    for b in btns[:6]:
                        # textual >= 8: Region.contains takes a point (x, y)
                        inside = box.region.contains(b.region.x, b.region.y)
                        print(f"  button {b.id} region={b.region} (inside box: {inside})")
                print()


if __name__ == "__main__":
    asyncio.run(main())
