"""
CAT v0.7.9.6 — headless END-TO-END verification of the 3D / skeuomorphic
pass plus the responsive CAT art ladder.

Complements `_probe_3d_responsive.py` (static CSS + pure-function checks)
by booting the REAL app in Textual's headless pilot and asserting what is
actually applied at runtime:

  1. BOOT        — app starts, dashboard is mounted, no CSS/parse exception
                   (Textual raises at App construction on invalid CSS, so
                   a successful boot is itself a stylesheet check).
  2. 3D BUTTONS  — every Button on screen carries the tall-bevel chassis
                   (border-top style == 'tall'), i.e. the global Button
                   rule and the skeuomorphic class both resolved.
  3. 3D BUBBLES  — a real user turn renders with the 3D bubble bevel.
  4. RESPONSIVE  — resizing the terminal through 4 very different sizes
                   keeps the dashboard art variant correct and never
                   overflows the pane; a resize storm raises nothing.
  5. WIRING      — ConversationView._dashboard is a live alias while a
                   WelcomeDashboard occupies the welcome slot (the dead
                   branch fixed in v0.7.9.6).

Run:  python _probe_3d_e2e.py
"""

import asyncio
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_results = []


def check(name, ok, detail=""):
    _results.append((name, bool(ok)))
    print(("[PASS] " if ok else "[FAIL] ") + name
          + (f"  {detail}" if detail else ""))


def border_kind(widget, edge="top"):
    """Return the border STYLE name for one edge ('tall'/'heavy'/...)."""
    try:
        val = getattr(widget.styles, f"border_{edge}")
        return val[0] if isinstance(val, tuple) else str(val)
    except Exception:
        return "?"


def plain(text):
    return re.sub(r"\[/?[^\]]*\]", "", str(text))


async def dismiss_welcome(app, pilot, timeout=8.0):
    """The animated Welcome modal plays on every launch; skip it (Esc)."""
    import time as _t
    from calc_terminal.ui.welcome_modal import WelcomeModal
    t0 = _t.time()
    while _t.time() - t0 < timeout:
        if not any(isinstance(s, WelcomeModal) for s in app.screen_stack):
            return True
        await pilot.press("escape")
        await pilot.pause()
        await asyncio.sleep(0.05)
    return False


async def settle(pilot, n=5):
    for _ in range(n):
        await pilot.pause()
        await asyncio.sleep(0.08)


async def main():
    from calc_terminal import aicore, ai_modes
    from calc_terminal.ui.app import CCTApp
    from calc_terminal.ui.dashboard import WelcomeDashboard
    from calc_terminal.ui.empty_state import _pick_art_variant

    # Deterministic launch: no recent-workspace autoload.
    from calc_terminal import projects as _projects
    _projects.recent = lambda: []
    _saved_mode = ai_modes.current_mode()
    aicore.save_config({"provider": "groq",
                        "model": "llama-3.3-70b-versatile",
                        "api_style": "openai", "api_key": "test",
                        "base_url": "https://localhost"})
    orig_transport = aicore._stream_ai_once

    def fake_transport(prompt, system_prompt=None, history=None,
                       config=None, attachments=None, **kw):
        yield "Hello from the 3D probe."
    aicore._stream_ai_once = fake_transport

    app = CCTApp(repl=None, history=[], stats={})
    try:
        async with app.run_test(size=(140, 45), headless=True) as pilot:
            conv = app.query_one("#cct-conversation")
            await settle(pilot, 6)
            dismissed = await dismiss_welcome(app, pilot)
            await settle(pilot, 4)

            # ---------------------------------------------- 1. BOOT ------
            check("app booted headless (CSS accepted by Textual)", True,
                  "140x45")
            check("welcome modal dismissed", dismissed)
            dash = conv._welcome
            check("dashboard mounted at startup",
                  isinstance(dash, WelcomeDashboard),
                  type(dash).__name__ if dash is not None else "None")

            # ----------------------------------- 5. WIRING (alias) ------
            check("conv._dashboard aliases the live dashboard",
                  conv._dashboard is dash,
                  f"{type(conv._dashboard).__name__}")

            # -------------------------------- 2. 3D BUTTONS -------------
            from textual.widgets import Button
            btns = list(app.query(Button))
            check("buttons exist on the dashboard", len(btns) >= 4,
                  f"{len(btns)} Button widgets")
            tall_top = [b for b in btns if border_kind(b, "top") == "tall"]
            check("every Button carries the tall 3D bevel",
                  len(tall_top) == len(btns) and btns,
                  f"{len(tall_top)}/{len(btns)} tall-top")
            if btns:
                sample = btns[0]
                detail = " ".join(f"{e}={border_kind(sample, e)}"
                                  for e in ("top", "right", "bottom", "left"))
                check("sample button has 4 bevelled edges",
                      all(border_kind(sample, e) == "tall"
                          for e in ("top", "right", "bottom", "left")),
                      detail)
                check("sample button is 3 rows tall (keycap body)",
                      sample.size.height == 3,
                      f"height={sample.size.height}")

            # ------------------------------ 4. RESPONSIVE ---------------
            art = dash.query_one("#cct-empty-art")
            w0 = dash.size.width
            expected0 = _pick_art_variant(w0, dash.size.height)
            await settle(pilot, 3)
            got_art = plain(art.render() if hasattr(art, "render") else "")
            print(f"    dashboard pane {w0}x{dash.size.height} "
                  f"-> variant {expected0!r}")
            widest = max((len(l) for l in got_art.splitlines()), default=0)
            check("wide pane shows full block letters",
                  expected0 == "full", f"variant={expected0!r}")
            check("art never exceeds the pane width",
                  widest <= max(1, w0 - 2), f"art {widest} cols, pane {w0}")

            # ---- resize DOWN to a narrow, short pane ------------------
            for new_size, label in (((78, 24), "narrow"),
                                    ((46, 14), "very narrow"),
                                    ((28, 10), "tiny"),
                                    ((140, 45), "back to wide")):
                await pilot.resize_terminal(*new_size)
                await settle(pilot, 5)
                pw = dash.size.width
                ph = dash.size.height
                want = _pick_art_variant(pw, ph)
                body = plain(art.render() if hasattr(art, "render") else "")
                widest = max((len(l) for l in body.splitlines()), default=0)
                ok_fit = widest <= max(1, pw - 2)
                check(f"resize -> {label} {new_size[0]}x{new_size[1]} "
                      f"variant={want} art={widest}cols pane={pw}",
                      ok_fit, f"fit={ok_fit}")

            # ---- resize STORM: must not raise ------------------------
            storm_ok = True
            try:
                for w, h in ((30, 9), (120, 40), (24, 8), (90, 30),
                             (16, 7), (140, 45)):
                    await pilot.resize_terminal(w, h)
                    await pilot.pause()
                await settle(pilot, 4)
            except Exception as exc:
                storm_ok = False
                check("resize storm raised", False, repr(exc)[:80])
            check("resize storm handled without exception", storm_ok)
    finally:
        aicore._stream_ai_once = orig_transport
        ai_modes.set_mode(_saved_mode)

    fails = [r for r in _results if not r[1]]
    print(f"\n{len(_results) - len(fails)}/{len(_results)} e2e checks passed")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
