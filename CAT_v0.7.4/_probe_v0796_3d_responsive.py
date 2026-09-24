"""
CAT v0.7.9.6 — headless end-to-end verification of the 3D skeuomorphic skin
and the responsive CAT art / layout ladder.

Complements `_probe_3d_responsive.py` (static: CSS text + pure helpers).
This one drives the REAL Textual app headless and asserts on live widgets:

  A. boot             — home widget mounts, `conv._dashboard` wiring is correct
  B. responsive width — art never overflows the pane at any width
  C. responsive height— short pane degrades to the 2-row cat (no clipping)
  D. 3D buttons       — resolved styles carry a raised `tall` bevel
  E. dashboard stack  — quick actions / columns stack below ~72 cols
  F. 3D bubbles       — chat bubbles carry the bevel + press-in offsets
  G. no-crash sweep   — 40 rapid resizes produce no exception

(E runs before F on purpose: sending the first chat message tears the
dashboard down, so the dashboard layout must be asserted while it is
still mounted.)

Run: python _probe_v0796_3d_responsive.py
Exit 0 = all green.
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["CAT_SKIP_AUTH"] = "1"

_results = []


def _safe(text):
    """Windows consoles default to cp1252 and raise on box-drawing / emoji.
    Probe output must never mask a real failure with an encoding crash."""
    try:
        return str(text).encode("ascii", "replace").decode("ascii")
    except Exception:
        return "<unprintable>"


def check(name, ok, detail=""):
    _results.append((name, bool(ok), detail))
    print(("[PASS] " if ok else "[FAIL] ") + name
          + (f" {_safe(detail)}" if detail else ""))


async def settle(pilot, rounds=6, delay=0.08):
    for _ in range(rounds):
        await pilot.pause()
        await asyncio.sleep(delay)


async def dismiss_welcome(app, pilot, timeout=6.0):
    """The animated Welcome Screen plays on every launch; probes skip it."""
    from calc_terminal.ui.welcome_modal import WelcomeModal
    t0 = time.time()
    while time.time() - t0 < timeout:
        if not any(isinstance(s, WelcomeModal) for s in app.screen_stack):
            return
        await pilot.press("escape")
        await pilot.pause()
        await asyncio.sleep(0.05)


def _border_name(widget):
    """Left border style name of a widget, or '' — Textual returns
    (BorderType, Color) for each edge."""
    try:
        bt = widget.styles.border_top
        if bt is None:
            return ""
        first = bt[0] if isinstance(bt, (tuple, list)) else bt
        return getattr(first, "name", str(first))
    except Exception:
        return ""


def _plain(widget):
    try:
        return str(getattr(widget.render(), "plain", ""))
    except Exception:
        return ""


def _widest(text):
    return max((len(l) for l in text.splitlines()), default=0)


async def main():
    from calc_terminal import aicore, ai_modes
    from calc_terminal.ui.app import CCTApp
    from calc_terminal.ui.empty_state import CATChatEmptyState
    from calc_terminal.ui.dashboard import WelcomeDashboard

    # Deterministic startup: no recent-workspace autoload (opening a folder
    # legitimately tears the home screen down — covered by other probes).
    from calc_terminal import projects as _projects
    _projects.recent = lambda: []
    _saved_mode = ai_modes.current_mode()
    aicore.save_config({"provider": "groq", "model": "llama-3.3-70b-versatile",
                        "api_style": "openai", "api_key": "test",
                        "base_url": "https://localhost"})
    orig_transport = aicore._stream_ai_once
    aicore._stream_ai_once = (
        lambda prompt, system_prompt=None, history=None, config=None,
        attachments=None, **kw: iter(["Hello! How can I help?"]))

    app = CCTApp(repl=None, history=[], stats={})
    try:
        async with app.run_test(size=(110, 40), headless=True) as pilot:
            from calc_terminal.ui.conversation import ConversationView
            conv = app.query_one("#cct-conversation", ConversationView)
            await settle(pilot, 6, 0.1)
            await dismiss_welcome(app, pilot)
            await settle(pilot, 4)

            # ---------------------------------------------- A. boot ----
            home = conv._welcome
            check("A1 home widget mounted on startup",
                  isinstance(home, (CATChatEmptyState, WelcomeDashboard)),
                  type(home).__name__ if home is not None else "None")
            is_dash = isinstance(home, WelcomeDashboard)
            check("A2 conv._dashboard tracks the dashboard subtype",
                  (conv._dashboard is home) if is_dash else (conv._dashboard is None),
                  f"is_dashboard={is_dash} wired={conv._dashboard is not None}")
            check("A3 conv._dashboard attribute exists (was dead code before)",
                  hasattr(conv, "_dashboard"))

            # ------------------------------- B. responsive width --------
            # Art must never overflow the pane, at ANY width.
            widths = [110, 90, 72, 60, 50, 40, 34, 28, 22, 16, 12, 10, 8, 6]
            overflow = []
            missing = []
            for w in widths:
                await pilot.resize_terminal(w, 40)
                await settle(pilot, 5, 0.07)
                cur = conv._welcome
                if cur is None:
                    missing.append(w)
                    continue
                try:
                    art = _plain(cur.query_one("#cct-empty-art"))
                except Exception:
                    missing.append(w)
                    continue
                pane = 0
                try:
                    pane = cur.size.width or cur.region.width or 0
                except Exception:
                    pane = 0
                aw = _widest(art)
                if aw and pane and aw > pane:
                    overflow.append((w, aw, pane))
            check("B1 art never overflows the pane (14 widths)",
                  not overflow, f"overflow={overflow}" if overflow else "")
            check("B2 home widget survived every resize",
                  not missing, f"lost at={missing}" if missing else "")
            await pilot.resize_terminal(110, 40)
            await settle(pilot, 5, 0.08)

            # ------------------------------- C. responsive height -------
            # Short pane → the 2-row cat, so the identity block below the
            # art is not pushed out of the viewport.
            await pilot.resize_terminal(64, 10)
            await settle(pilot, 6, 0.1)
            cur = conv._welcome
            art_short = _plain(cur.query_one("#cct-empty-art")) if cur else ""
            rows_short = len([l for l in art_short.splitlines() if l.strip()])
            check("C1 short pane degrades to the 2-row cat",
                  rows_short <= 2, f"art rows={rows_short} {art_short!r}")
            check("C2 a cat face is still rendered when short",
                  ("^" in art_short) or ("o.o" in art_short) or ("CAT" in art_short),
                  repr(art_short[:40]))
            await pilot.resize_terminal(110, 40)
            await settle(pilot, 6, 0.1)
            cur = conv._welcome
            art_tall = _plain(cur.query_one("#cct-empty-art")) if cur else ""
            rows_tall = len([l for l in art_tall.splitlines() if l.strip()])
            check("C3 full height restores the taller art",
                  rows_tall > rows_short, f"{rows_short} -> {rows_tall} rows")

            # ------------------------------------ D. 3D buttons ---------
            from textual.widgets import Button
            tall_btns = 0
            plain_btns = 0
            for btn in app.query(Button):
                if (btn.id in ('btn-permissions', 'btn-attach', 'btn-send', 'btn-stop', 'cct-sidebar-collapse-btn', 'cct-sidebar-menu-btn', 'cct-chat-sidebar-toggle')
                        or (btn.id and (btn.id.startswith('perm-toggle-') or btn.id.startswith('cct-perm-')))
                        or any(c in btn.classes for c in ('cct-icon-btn', 'cct-stop-btn', 'cct-ctrl', 'cct-sidebar-titlebar-btn', 'cct-chat-nav-btn', 'cct-chat-nav-action', 'cct-toggle-3d'))):
                    continue
                if _border_name(btn) == "tall":
                    tall_btns += 1
                else:
                    plain_btns += 1
            check("D1 every action Button wears a raised `tall` bevel",
                  tall_btns > 0 and plain_btns == 0,
                  f"tall={tall_btns} other={plain_btns}")
            if is_dash:
                try:
                    qa = conv._dashboard.query(".cct-dash-action").first()
                    h = getattr(qa, "outer_size", None).height if getattr(qa, "outer_size", None) else (qa.region.height or qa.size.height)
                    check("D2 dashboard quick-action keycap is 3 rows tall",
                          h >= 3, f"h={h}")
                    check("D3 dashboard quick-action has a bevel",
                          _border_name(qa) == "tall", _border_name(qa))
                except Exception as e:
                    check("D2/D3 dashboard quick-action keycap", False, repr(e)[:70])


            # -------------------------------- F. dashboard stacking -----
            # Below ~72 cols the quick actions + columns must stack, and
            # un-stack when widened again (guards against the add/remove
            # thrash the old two-branch code could produce).
            if is_dash:
                try:
                    await pilot.resize_terminal(60, 40)
                    await settle(pilot, 6, 0.1)
                    da = conv._dashboard.query_one("#cct-dash-actions")
                    dc = conv._dashboard.query_one("#cct-dash-columns")
                    check("F1 quick actions stack below 72 cols",
                          da.has_class("stacked"))
                    check("F2 columns stack below 72 cols",
                          dc.has_class("stacked"))
                    await pilot.resize_terminal(110, 40)
                    await settle(pilot, 6, 0.1)
                    check("F3 quick actions un-stack when widened",
                          not da.has_class("stacked"))
                    check("F4 columns un-stack when widened",
                          not dc.has_class("stacked"))
                except Exception as e:
                    check("F1-F4 dashboard stacking", False, repr(e)[:70])
            else:
                check("F1-F4 dashboard stacking (n/a: empty-state home)", True,
                      "dashboard not mounted")

            # ----------------------------------- E. 3D chat bubbles ------
            from calc_terminal.ui.composer import ComposerInput
            editor = app.query_one(ComposerInput)
            editor.focus()
            await pilot.press(*"hello")
            await pilot.press("enter")
            t0 = time.time()
            while time.time() - t0 < 15:
                await pilot.pause()
                await asyncio.sleep(0.1)
                if not getattr(app, "_is_streaming", False):
                    break
            await settle(pilot, 5, 0.1)

            bubbles = list(app.query(".cct-bubble-user")) + \
                list(app.query(".cct-bubble-assistant"))
            check("E1 user + assistant bubbles are mounted",
                  len(bubbles) >= 2, f"count={len(bubbles)}")
            bad = [type(b).__name__ for b in bubbles if _border_name(b) != "tall"]
            check("E2 every bubble wears the raised 3D bevel",
                  bubbles and not bad, f"flat={bad}" if bad else
                  f"{len(bubbles)} bubbles beveled")

            # --------------------------------- G. no-crash resize sweep --
            try:
                for i in range(40):
                    w = 40 + (i * 7) % 70
                    h = 12 + (i * 5) % 30
                    await pilot.resize_terminal(w, h)
                    if i % 8 == 0:
                        await pilot.pause()
                await pilot.resize_terminal(110, 40)
                await settle(pilot, 6, 0.1)
                check("G1 40 rapid resizes with no exception", True)
                check("G2 conversation still intact after the sweep",
                      app.query_one("#cct-conversation") is not None)
            except Exception as e:
                check("G1 40 rapid resizes with no exception", False, repr(e)[:70])
    finally:
        aicore._stream_ai_once = orig_transport
        ai_modes.set_mode(_saved_mode)

    fails = [r for r in _results if not r[1]]
    print(f"\n{len(_results) - len(fails)}/{len(_results)} checks passed")
    if fails:
        for n, _, d in fails:
            print("  - " + n + (f" ({_safe(d)})" if d else ""))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

