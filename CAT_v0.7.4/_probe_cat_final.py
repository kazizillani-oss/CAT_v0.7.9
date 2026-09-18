"""Final integration spot-checks for CAT v0.7.9.0."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

results = []


def check(name, ok, extra=""):
    results.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {extra}")


# 1. identity fast-path answers use CAT branding
from calc_terminal import identity
ans = identity.answer_for("what are you?", None)
check("identity answer branded CAT", ans is not None and "CAT" in ans,
      (ans or "")[:90])
ans2 = identity.answer_for("who built cct?", None)
check("legacy 'who built cct' still answered",
      ans2 is not None and "Kazi Zillani" in ans2)

# 2. version constants coherent
from calc_terminal import app as backend_app
from calc_terminal.ui import welcome_modal as wm
from calc_terminal.cli import _version
check("VERSION == 0.7.9.0", backend_app.VERSION == "0.7.9.0",
      backend_app.VERSION)
check("cli version 0.7.9.0", _version() == "0.7.9.0", _version())
check("welcome modal version matches", wm._VERSION == "0.7.9.0", wm._VERSION)
logo = "\n".join(backend_app.LOGO)
# CAT block mark: 6(C)+5(A)+8(T) filled blocks on the top row.
check("LOGO is the new CAT block mark",
      len(backend_app.LOGO) == 6
      and backend_app.LOGO[0].count("\u2588") == 19,
      f"blocks={backend_app.LOGO[0].count(chr(0x2588))}")




async def dismiss_welcome(app, pilot, timeout=6.0):
    """v0.7.9.0: the animated Welcome Screen plays on EVERY launch and
    auto-continues into the Dashboard. Probes skip it deterministically
    (Esc) so they exercise the layers underneath."""
    import asyncio as _aio
    from calc_terminal.ui.welcome_modal import WelcomeModal
    t0 = __import__("time").time()
    while __import__("time").time() - t0 < timeout:
        if not any(isinstance(s, WelcomeModal) for s in app.screen_stack):
            return
        await pilot.press("escape")
        await pilot.pause()
        await _aio.sleep(0.05)


async def ui_checks():
    from calc_terminal.ui.app import CCTApp
    from calc_terminal.ui.welcome_modal import WelcomeModal
    from textual.widgets import DirectoryTree

    class _FakeRepl:
        VERSION = "0.7.9.0"

    app = CCTApp(_FakeRepl(), [], {})
    async with app.run_test(size=(110, 34)) as pilot:
        await pilot.pause()
        await dismiss_welcome(app, pilot)
        # 3. submit pipeline + REAL animation lifecycle. This machine
        #    has an AI provider configured, so the submit runs a genuine
        #    model request — exactly what spec section 31 wants tested.
        conv = app.conversation
        composer = app.composer
        from calc_terminal.ui.composer import ComposerInput
        inp = composer.query_one("#cct-input", ComposerInput)
        inp.text = "reply with exactly one short sentence"
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        turns = [t.role for t in app.session.turns]
        check("user turn created on submit", "user" in turns, str(turns))
        # animation must appear while the request runs
        t0 = asyncio.get_event_loop().time()
        appeared = False
        while asyncio.get_event_loop().time() - t0 < 6:
            await asyncio.sleep(0.15)
            await pilot.pause()
            if conv._agent_indicator is not None:
                appeared = True
                break
        check("animation appears on real model request", appeared)
        if conv._agent_indicator is not None:
            # Sample several timer periods: any distinct frame pair proves
            # the animation is ticking during the live request.
            frame_a = str(conv._agent_indicator.render())
            seen = {frame_a}
            t_eye = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - t_eye < 1.2:
                await asyncio.sleep(0.12)
                await pilot.pause()
                if conv._agent_indicator is None:
                    break
                seen.add(str(conv._agent_indicator.render()))
            check("eyes animate during real request", len(seen) >= 2,
                  f"{len(seen)} distinct frame(s)")
        else:
            check("eyes animate during real request", False,
                  "(turn finished too fast to sample)")
        # animation must stop when the response completes
        t0 = asyncio.get_event_loop().time()
        stopped = False
        while asyncio.get_event_loop().time() - t0 < 90:
            await asyncio.sleep(0.3)
            await pilot.pause()
            if conv._agent_indicator is None:
                stopped = True
                break
        check("animation stops when work ends", stopped,
              f"(waited {asyncio.get_event_loop().time()-t0:.0f}s)")
        check("composer cleared after send", not inp.text.strip())

        # 4. welcome modal branding
        modal = WelcomeModal()
        await app.push_screen(modal)
        await pilot.pause()
        title = str(modal.query_one("#wm-title").render())
        check("welcome modal says CAT v0.7.9.0",
              "Welcome to CAT v0.7.9.0" in title, repr(title))
        modal.dismiss(None)
        await pilot.pause()
        await asyncio.sleep(0.1)

        # 5. explorer tree functional (file selected event wiring)
        ws = r"C:\Users\ADMIN\Downloads\compressed"
        os.makedirs(ws, exist_ok=True)
        probe = os.path.join(ws, "branding_probe.txt")
        with open(probe, "w") as f:
            f.write("x")
        await app._open_folder(ws)
        await pilot.pause()
        await asyncio.sleep(0.8)
        await pilot.pause()
        body = app.query_one("#cct-sidebar-body")
        trees = body.query(DirectoryTree)
        found = any(True for _ in trees) if trees else False
        check("directory tree mounted for workspace", found)
        try:
            os.remove(probe)
        except OSError:
            pass


asyncio.run(ui_checks())
print(f"\n{sum(results)}/{len(results)} final checks passed")
sys.exit(0 if all(results) else 1)
