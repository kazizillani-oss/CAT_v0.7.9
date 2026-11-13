import asyncio
from unittest.mock import MagicMock
from calc_terminal.ui.app import CCTApp

async def inspect():
    repl = MagicMock()
    history = MagicMock()
    history.get_history.return_value = []
    stats = MagicMock()
    app = CCTApp(repl=repl, history=history, stats=stats)
    async with app.run_test(size=(120, 35)) as pilot:
        await pilot.pause(0.1)
        print("Screen children:")
        for w in app.screen.walk_children():
            r = getattr(w, "region", None)
            if r and r.y < 8 and getattr(w, "display", True):
                print(f"{w.__class__.__name__} id={getattr(w, 'id', None)} classes={w.classes} region={r}")

asyncio.run(inspect())
