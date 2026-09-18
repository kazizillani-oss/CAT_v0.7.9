import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def main():
    from calc_terminal.ui.mcp_panel import McpServersPanel, _AddMcpForm
    from calc_terminal.ui.backup_panel import BackupProvidersPanel, _AddProviderForm
    from calc_terminal.ui.attach_panel import AttachPanel

    for name, fac in [
        ("MCP main", McpServersPanel),
        ("MCP add", _AddMcpForm),
        ("Backup main", BackupProvidersPanel),
        ("Backup add", _AddProviderForm),
        ("Attach", AttachPanel),
    ]:
        css = getattr(fac, "CSS", None)
        print(f"{name}: CSS attr present={css is not None} len={len(css) if css else 0} first={repr(css[:40]) if css else None}")


if __name__ == "__main__":
    asyncio.run(main())
