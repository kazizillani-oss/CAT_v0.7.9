"""
CAT v0.7.9.0 — startup-flow verification (spec: 'Dashboard and Welcome
Screen consistently available').

  1. Fresh launch shows the animated Welcome Screen FIRST (CAT block
     art + boot bar visible on the modal screen).
  2. It auto-continues into the Dashboard (modal pops itself; the
     dashboard is the main interface underneath — never duplicated).
  3. Dashboard composition: CAT art hero + version + ready line +
     live AI STATUS block.
  4. Starting a conversation hides the dashboard; a model request
     does NOT re-open any welcome screen or second dashboard.
  5. Simulated model restart/reload updates the SAME dashboard
     instance in place (object identity preserved).
  6. /clear restores the dashboard home (single instance).
  7. Centralized bootstrap: every entry point funnels through
     calc_terminal.cli.bootstrap (cct/cat/python -m/main.py/wizard).
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_results = []


def check(name, ok, detail=""):
    _results.append((name, bool(ok), detail))
    print(("[PASS] " if ok else "[FAIL] ") + name + (f" {detail}" if detail else ""))


async def dismiss_welcome(app, pilot, timeout=6.0):
    from calc_terminal.ui.welcome_modal import WelcomeModal
    t0 = __import__("time").time()
    while __import__("time").time() - t0 < timeout:
        if not any(isinstance(s, WelcomeModal) for s in app.screen_stack):
            return
        await pilot.press("escape")
        await pilot.pause()
        await asyncio.sleep(0.05)


async def main():
    from calc_terminal import aicore, projects as _projects, cli
    _projects.recent = lambda: []

    # ---- 7: centralized bootstrap --------------------------------------
    check("cli exposes ONE centralized bootstrap",
          callable(cli.bootstrap))
    check("_launch kept as alias of bootstrap (no divergent copy)",
          cli._launch is cli.bootstrap)
    import inspect
    model_src = open(os.path.join("calc_terminal", "model.py"),
                     encoding="utf-8-sig").read()
    check("model wizard finish path launches the primary UI too",
          "launch_chat_app" in model_src)

    orig = aicore._stream_ai_once

    def fake_transport(prompt, system_prompt=None, history=None,
                       config=None, attachments=None, **kw):
        yield "Hello from the fake model."
    aicore._stream_ai_once = fake_transport

    from calc_terminal.ui.app import CCTApp
    from calc_terminal.ui.dashboard import WelcomeDashboard
    from calc_terminal.ui.welcome_modal import WelcomeModal

    app = CCTApp(repl=None, history=[], stats={})
    async with app.run_test(size=(110, 40), headless=True) as pilot:
        conv = app.query_one("#cct-conversation")

        # ---- 1: Welcome Screen first -----------------------------------
        t0 = __import__("time").time()
        seen_welcome = False
        while __import__("time").time() - t0 < 4:
            await pilot.pause(); await asyncio.sleep(0.05)
            if any(isinstance(s, WelcomeModal) for s in app.screen_stack):
                seen_welcome = True
                break
        check("fresh launch shows the animated Welcome Screen first",
              seen_welcome)
        if seen_welcome:
            modal = next(s for s in app.screen_stack
                         if isinstance(s, WelcomeModal))
            try:
                # give the modal's on_mount one beat to paint logo/boot
                for _ in range(10):
                    await pilot.pause()
                    await asyncio.sleep(0.05)
                    logo_plain = str(getattr(
                        modal.query_one("#wm-logo").render(), "plain", ""))
                    if "█" in logo_plain:
                        break
                boot_plain = str(getattr(
                    modal.query_one("#wm-boot").render(), "plain", ""))
                check("Welcome Screen shows CAT block ASCII art",
                      "█" in logo_plain and "╚" in logo_plain)
                check("Welcome Screen shows staged boot/loading animation",
                      ("Initializing" in boot_plain)
                      or ("CAT ready" in boot_plain))
            except Exception as e:
                check("welcome content rendered", False, repr(e)[:60])

        # ---- 2: auto-continues into the Dashboard -----------------------
        t0 = __import__("time").time()
        while __import__("time").time() - t0 < 8:
            await pilot.pause(); await asyncio.sleep(0.1)
            if not any(isinstance(s, WelcomeModal) for s in app.screen_stack):
                break
        check("Welcome Screen auto-continues into the Dashboard",
              not any(isinstance(s, WelcomeModal)
                      for s in app.screen_stack))
        dash = conv._welcome
        check("Dashboard is the main interface after welcome",
              isinstance(dash, WelcomeDashboard), type(dash).__name__)

        # ---- 3: dashboard composition ------------------------------------
        try:
            art = str(getattr(dash.query_one("#cct-empty-art").render(),
                              "plain", ""))
            ver = str(getattr(dash.query_one("#cct-empty-version").render(),
                              "plain", ""))
            ai = str(getattr(dash.query_one("#cct-dash-ai-status").render(),
                             "plain", ""))
            check("dashboard shows CAT block art hero",
                  "█" in art and "╚" in art)
            check("dashboard shows version line",
                  ver.strip().startswith("CAT v"), ver.strip())
            check("dashboard shows live AI STATUS",
                  "AI STATUS" in ai, ai.strip())
        except Exception as e:
            check("dashboard composition rendered", False, repr(e)[:60])

        # ---- 4/5/6: model start / reload — no duplicates ------------------
        dash_id = id(dash)
        # simulate a model starting work mid-session
        app._set_ai_status("Initializing")
        await pilot.pause()
        app._set_ai_status("Ready")
        await pilot.pause()
        check("model start does NOT open another welcome screen",
              not any(isinstance(s, WelcomeModal)
                      for s in app.screen_stack))
        check("model start does NOT create another dashboard",
              conv._welcome is dash and isinstance(conv._welcome,
                                                   WelcomeDashboard))

        # simulated provider reload through the real handler
        app._on_provider_selected({"provider": "groq", "model": "fake"})
        await pilot.pause()
        check("model reload reuses the SAME dashboard instance",
              conv._welcome is dash)

        # ---- start chatting, then clear ----------------------------------
        editor = app.query_one("ComposerInput")
        editor.focus()
        await pilot.press(*"hello"); await pilot.press("enter")
        t0 = __import__("time").time()
        while __import__("time").time() - t0 < 15:
            await pilot.pause(); await asyncio.sleep(0.1)
            if not getattr(app, "_is_streaming", False):
                break
        check("chat starts normally; dashboard steps aside",
              conv._welcome is None
              and any(t.role == "assistant" for t in app.session.turns))

        editor.focus()
        await pilot.press(*"/clear"); await pilot.pause()
        await pilot.press("enter"); await pilot.pause()
        await pilot.press("enter")
        for _ in range(8):
            await pilot.pause(); await asyncio.sleep(0.1)
        check("/clear restores the dashboard home",
              isinstance(conv._welcome, WelcomeDashboard))
        check("still exactly ONE welcome-slot widget (no duplicates)",
              sum(1 for c in conv.children
                  if isinstance(c, WelcomeDashboard)) <= 1)

    aicore._stream_ai_once = orig

    fails = [r for r in _results if not r[1]]
    print(f"\n{len(_results) - len(fails)}/{len(_results)} startup-flow checks passed")
    if fails:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
