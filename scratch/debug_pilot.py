import asyncio
from unittest.mock import MagicMock
from calc_terminal.ui.app import CCTApp
import textual.pilot

orig_wait = textual.pilot.Pilot._wait_for_screen

async def custom_wait(self, timeout=5.0):
    screen = self.app.screen
    children = [self.app, *screen.walk_children(with_self=True)]
    print(f"Total children to wait on: {len(children)}")
    remaining = set(children)
    
    def make_decrement(child):
        def dec():
            remaining.discard(child)
            # print(f"Finished: {child}")
        return dec
        
    for child in children:
        if child.call_later(make_decrement(child)):
            pass
        else:
            remaining.discard(child)
            
    for _ in range(50):
        if not remaining:
            print("All drained!")
            return True
        await asyncio.sleep(0.1)
        
    print(f"TIMEOUT! Remaining un-drained widgets ({len(remaining)}):")
    for r in remaining:
        print(f"  - {r!r} (parent: {getattr(r, 'parent', None)!r}, is_mounted: {getattr(r, 'is_mounted', False)})")
    return False

textual.pilot.Pilot._wait_for_screen = custom_wait

async def test_debug():
    app = CCTApp(MagicMock(), [], MagicMock())
    async with app.run_test(size=(160, 50)) as pilot:
        print("Success entering pilot!")

asyncio.run(test_debug())
