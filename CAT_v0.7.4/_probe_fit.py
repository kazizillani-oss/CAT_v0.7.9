"""Instrument fit_dialog: dump regions and content_size of McpServersPanel."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import calc_terminal.mcp as mcp
mcp.load_servers = lambda: [
    {"id": "srv1", "name": "Math Tools", "kind": "remote",
     "url": "http://localhost:3000/mcp", "status": "connected",
     "version": "2024-11-05", "latency_ms": 42, "tools": ["add", "mul"],
     "last_connected": 1755300000},
    {"id": "srv2", "name": "Git Helper", "kind": "local",
     "command": "npx git-mcp", "status": "disconnected",
     "version": "", "latency_ms": None, "tools": []},
]

_MCP_CSS = """
McpServersPanel { align: center middle; background: $app-background 70%; }
#mcp-box {
    width: 92; max-width: 100%; height: auto; max-height: 92%;
    background: $surface; border: round $border; padding: 0;
}
#mcp-titlebar { height: 3; padding: 1 2 0 2; border-bottom: solid $border; }
#mcp-title { text-style: bold; width: 1fr; }
#mcp-subtitle { color: $text-faint; height: 2; padding: 0 2; }
#mcp-list { height: auto; min-height: 4; padding: 1 2; overflow-y: auto; }
.mcp-card { height: 3; margin-bottom: 1; background: $app-background; border: round $border; padding: 0 1; }
.mcp-card-sel { border: round $border-active; }
.mcp-empty { color: $text-faint; padding: 2 1; }
#mcp-add-row { height: 4; padding: 0 2 1 2; }
#mcp-add-row Button { margin-right: 1; }
#mcp-ctx-actions { height: 4; padding: 0 2 1 2; }
#mcp-ctx-actions Button { margin-right: 1; width: 1fr; min-width: 10; }
#mcp-actions { height: 4; padding: 0 2 1 2; border-top: solid $border; }
#mcp-actions Button { margin-right: 1; }
"""


async def main():
    from textual.app import App
    from calc_terminal.ui import theme_css
    from calc_terminal.ui.mcp_panel import McpServersPanel

    class ProbeApp(App):
        CSS = theme_css.BASE_CSS + _MCP_CSS

        def get_css_variables(self):
            variables = dict(super().get_css_variables())
            variables.update(theme_css.css_variables())
            return variables

    app = ProbeApp()
    async with app.run_test(size=(110, 36), headless=True) as pilot:
        screen = McpServersPanel()
        await app.push_screen(screen)
        for _ in range(20):
            await pilot.pause()
            await asyncio.sleep(0.15)

        print("active:", app.screen is screen,
              "children:", [type(c).__name__ for c in screen.children])
        try:
            box = screen.query_one("#mcp-box")
        except Exception as e:
            print("MOUNT FAILED:", e)
            print("screens:", app.screen_stack)
            return

        lst = screen.query_one("#mcp-list")
        print("=== AFTER FIT ===")
        print("box region:", box.region, "styles.height:", box.styles.height)
        print("list region:", lst.region, "styles.height:", lst.styles.height,
              "content_size:", lst.content_size, "virtual_size:", lst.virtual_size)
        for c in box.children:
            print(f"  child {c.id or type(c).__name__}: region={c.region} "
                  f"styles.height={c.styles.height} display={c.display}")
        print("--- list children ---")
        for c in lst.children:
            print(f"  {c.id or type(c).__name__}: region={c.region} "
                  f"styles.height={c.styles.height} styles.margin={c.styles.margin}")

        # Now disable fit: reset heights and measure natural auto layout
        box.styles.height = "auto"
        lst.styles.height = "auto"
        for _ in range(6):
            await pilot.pause()
            await asyncio.sleep(0.2)
        print("=== NATURAL (no fit) ===")
        print("box region:", box.region, "styles.height:", box.styles.height)
        print("list region:", lst.region, "styles.height:", lst.styles.height,
              "content_size:", lst.content_size, "virtual_size:", lst.virtual_size)
        for c in box.children:
            print(f"  child {c.id or type(c).__name__}: region={c.region} "
                  f"styles.height={c.styles.height} display={c.display}")


asyncio.run(main())
