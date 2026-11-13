import asyncio
from unittest.mock import MagicMock
from calc_terminal.ui.app import CCTApp

async def main():
    repl = MagicMock()
    history = MagicMock()
    stats = MagicMock()

    print("--- 1. Testing Landscape Boot (120x40) ---")
    app = CCTApp(repl, history, stats)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.1)
        header = app.query_one("#cct-brandheader")
        assert not header.has_class("is-portrait"), "Should be landscape"
        print("✓ Landscape header loaded successfully!")

    print("--- 2. Testing Portrait Boot (50x40) ---")
    app_port = CCTApp(repl, history, stats)
    async with app_port.run_test(size=(50, 40)) as pilot:
        await pilot.pause(0.1)
        header_p = app_port.query_one("#cct-brandheader")
        assert header_p.has_class("is-portrait"), "Should be portrait"
        print("✓ Portrait header loaded successfully!")

    print("All headless pilot boots passed!")

if __name__ == "__main__":
    asyncio.run(main())

