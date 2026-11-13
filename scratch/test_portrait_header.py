import asyncio
from calc_terminal.ui.app import CCTApp
from calc_terminal.ui.header import BrandHeader, MenuButton, Logo, PermissionPill
from calc_terminal import repl as repl_mod
from calc_terminal import session as sess_mod
from calc_terminal import stats as stats_mod

async def run_portrait_test():
    repl = repl_mod.Repl()
    sess = sess_mod.Session()
    stats = stats_mod.Stats()
    app = CCTApp(repl, sess, stats)
    
    async with app.run_test(size=(48, 40)) as pilot:
        await pilot.pause()
        hdr = app.query_one(BrandHeader)
        print("Header attached:", hdr.is_attached)
        print("Header display:", hdr.display)
        print("Header classes:", list(hdr.classes))
        print("Header styles height:", hdr.styles.height)
        menu_btn = hdr.query_one(MenuButton)
        logo = hdr.query_one(Logo)
        pill = hdr.query_one(PermissionPill)
        exp_btn = hdr.query_one("#cct-header-explorer-btn")
        print("Menu button display:", menu_btn.display)
        print("Logo display:", logo.display)
        print("Pill display:", pill.display)
        print("Explorer button display:", exp_btn.display)
        assert hdr.display is True, "Header must be visible in portrait mode"
        assert exp_btn.display is True, "Explorer button must be visible in portrait mode"
        print("[SUCCESS] Portrait mode header verification passed!")

if __name__ == "__main__":
    asyncio.run(run_portrait_test())

