import asyncio, sys
sys.path.insert(0, '.')
from calc_terminal import projects as _projects
_projects.recent = lambda: []
sys.stdout.reconfigure(encoding='utf-8', errors='replace')


async def main():
    from calc_terminal.ui.app import CCTApp
    from calc_terminal.ui.welcome_modal import WelcomeModal
    app = CCTApp(repl=None, history=[], stats={})
    async with app.run_test(size=(110, 40), headless=True) as pilot:
        modal = None
        t0 = __import__('time').time()
        while __import__('time').time() - t0 < 4:
            await pilot.pause(); await asyncio.sleep(0.05)
            modal = next((s for s in app.screen_stack if isinstance(s, WelcomeModal)), None)
            if modal: break
        print('modal found:', bool(modal))
        if modal:
            await pilot.pause(); await asyncio.sleep(0.3)
            logo = str(getattr(modal.query_one('#wm-logo').render(), 'plain', ''))
            boot = str(getattr(modal.query_one('#wm-boot').render(), 'plain', ''))
            print('LOGO repr head:', repr(logo[:60]))
            print('BOOT repr:', repr(boot[:80]))
            print('logo children count:', len(modal.query('#wm-logo')))

asyncio.run(main())
