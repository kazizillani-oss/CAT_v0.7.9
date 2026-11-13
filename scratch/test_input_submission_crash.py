import asyncio
import traceback
from unittest.mock import MagicMock
from calc_terminal.ui.app import CCTApp
from calc_terminal.ui.events import MessageSubmitted

async def main():
    repl = MagicMock()
    history = []
    stats = {}
    app = CCTApp(repl, history, stats)
    try:
        async with app.run_test() as pilot:
            print("App started.")
            await pilot.pause()
            print("Sending message...")
            try:
                # Trigger via message submit
                app.post_message(MessageSubmitted("hello world"))
                await pilot.pause(1.0)
                print("Message submitted without immediate crash.")
            except Exception as e:
                print("Crash caught during on_message_submitted:", e)
                traceback.print_exc()
    except Exception as e:
        print("Crash in run_test:", e)
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
