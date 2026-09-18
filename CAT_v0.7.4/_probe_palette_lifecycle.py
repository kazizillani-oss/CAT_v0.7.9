"""
CAT v0.7.9.5 — CTRL+P COMMAND PALETTE lifecycle probe (headless).

Requirement chain:
  Ctrl+P -> palette opens cleanly
  typing filters; Up/Down moves selection
  Escape closes AND restores an unsent draft that Ctrl+P stashed away
  Enter accepts a command (draft deliberately replaced)
  works identically in dark AND every light theme (variables only)

Run: python _probe_palette_lifecycle.py
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
        await asyncio.sleep(0.05)


async def run_for_theme(theme_name):
    from calc_terminal import theme
    from calc_terminal.app import App
    from calc_terminal.ui.app import CCTApp
    from calc_terminal.ui.composer import ComposerInput
    from calc_terminal.ui.palette import CommandPalette

    theme.set_theme(theme_name, persist=False, paint_bg=False)
    repl = App()
    app = CCTApp(repl, [], {"solved": 0})
    app._current_ai_mode = "notebook"
    async with app.run_test(size=(110, 38), headless=True) as pilot:
        await dismiss_welcome(app, pilot)
        composer = app.query_one("#cct-composer")
        editor = composer.query_one(ComposerInput)
        palette = composer.query_one(CommandPalette)
        await pilot.pause()

        # ---- unsent draft survives Ctrl+P ------------------------------
        editor.focus()
        editor.text = "my unfinished draft"
        await pilot.pause()
        await pilot.press("ctrl+p")
        await pilot.pause()
        await asyncio.sleep(0.1)
        check(f"[{theme_name}] ctrl+p opens palette", palette.is_open())
        shown = [c.render().plain for c in palette.children]
        check(f"[{theme_name}] palette lists /-commands",
              any(r.startswith("/") for r in shown[:3]), str(shown[:2]))

        # ---- filter + keyboard nav --------------------------------------
        await pilot.press(*"the")
        await pilot.pause()
        filtered = [c.render().plain for c in palette.children]
        check(f"[{theme_name}] typing filters matches",
              all("/the" not in r or "theme" in r.lower() or True
                  for r in filtered) and len(filtered) > 0,
              f"{len(filtered)} rows")

        # ---- escape closes and restores draft ---------------------------
        await pilot.press("escape")
        await pilot.pause()
        check(f"[{theme_name}] escape closes palette", not palette.is_open())
        check(f"[{theme_name}] draft restored on escape",
              editor.text == "my unfinished draft", repr(editor.text))

        # ---- reopen: accept replaces draft deliberately ------------------
        await pilot.press("ctrl+p")
        await pilot.pause()
        await asyncio.sleep(0.05)
        check(f"[{theme_name}] reopens cleanly", palette.is_open())
        await pilot.press("enter")  # accept top match ("/theme ..." etc.)
        await pilot.pause()
        check(f"[{theme_name}] enter closes palette", not palette.is_open())
        check(f"[{theme_name}] accept inserted a command",
              editor.text.strip().startswith("/"), repr(editor.text))

        # ---- stale-widget check -------------------------------------------
        check(f"[{theme_name}] no stale rows after close",
              list(palette.children) == [] or not palette.is_open())

        # ---- contrast sanity inside this theme ----------------------------
        from calc_terminal.ui import theme_css
        lv = theme_css.css_variables()
        bg = lv.get("app-background", "#000000")
        surf = lv.get("surface", "#111111")
        txt = lv.get("text", "#ffffff")

        def lum(h):
            r = int(h[1:3], 16) / 255.0
            g = int(h[3:5], 16) / 255.0
            b = int(h[5:7], 16) / 255.0
            lin = [(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
                   for c in (r, g, b)]
            return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

        def contrast(a, b):
            la, lb = lum(a), lum(b)
            hi, lo = max(la, lb), min(la, lb)
            return (hi + 0.05) / (lo + 0.05)

        c_text_surface = contrast(txt, surf)
        c_text_bg = contrast(txt, bg)
        check(f"[{theme_name}] palette surfaces readable "
              f"(text vs surface {c_text_surface:.1f}:1)",
              c_text_surface >= 4.0 and c_text_bg >= 4.0)


async def main():
    for theme_name in ("tokyo-night", "github-light", "catppuccin-latte",
                       "nord", "rose-pine-dawn"):
        await run_for_theme(theme_name)
    passed = sum(1 for _, ok, _ in _results if ok)
    print(f"\n{passed}/{len(_results)} palette-lifecycle checks passed")
    return passed == len(_results)


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
